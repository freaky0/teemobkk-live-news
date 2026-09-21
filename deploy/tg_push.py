#!/usr/bin/env python3
"""Push the stories that matter to the Telegram channel, one tick at a time.

The collector already decides what a story is worth and the read path already hides what the
operator does not want, so this script owns only the part in between: which stored rows are
eligible for the channel, which of those are actually new, how the message reads, and the pacing
that keeps a burst from flooding the channel. Selection goes through `query_articles` on purpose -
a hidden story, a story a filter rule caught and a switched-off source are absent here for exactly
the same reason they are absent on the page, and hiding one story teaches both surfaces at once.

Run it from a systemd timer (one tick a minute). It is safe to run by hand with --dry-run, and
--replay walks a past window through the same rules to show what would have been posted.

Environment (systemd EnvironmentFile, never on the command line):
    TELEGRAM_BOT_TOKEN   required - the bot that posts
    TELEGRAM_CHAT_ID     required - the channel or supergroup id
    DEEPSEEK_API_KEY     optional - enables the Korean rewrite of non-Korean items
    TG_MIN_PRIORITY      default 4
    TG_COOLDOWN_SECONDS  default 180   - shortest gap between two non-breaking posts
    TG_MAX_PER_HOUR      default 12
    TG_WINDOW_HOURS      default 3     - how stale a candidate may be and still be posted
    TG_TRANSLATE         default 1
    TG_DRY_RUN           default 0
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import live_news_dashboard as core  # noqa: E402  (path is set just above)

ICT = timezone(timedelta(hours=7), name="ICT")
BOT_API = "https://api.telegram.org/bot%s/%s"
STATE_TABLE = "tg_posted"
LOCK_FILE = Path(os.environ.get("TG_LOCK_FILE") or (Path(tempfile.gettempdir()) / "teemo-tg-push.lock"))
LINK_CHARS = 4096

# Stories that are technically "important" by score but are noise in a channel: tick-by-tick price
# alerts, the aggregator's own promo posts, and the English SEO pieces that ride a price move.
# Tuned against a 24h replay; keep it short, and prefer a pattern over a source ban so a real story
# from the same feed still gets through.
NOISE_PATTERNS = (
    r"지난\s*\d+\s*(분|시간)\s*간",
    r"주간\s*(인기글|인기\s*키워드|에어드롭|요약)",
    r"'?\s*인기\s*키워드",
    r"^BTC\s*\$[\d,]+(\.\d+)?\s*(상회|하회|돌파|하락)$",
    r"price prediction|price target|can it keep rising|how to buy|how high",
    r"casino|presale|airdrop|meme coin|to the moon",
    r"pepeto|pepe unchained|dogecoin price",
    r"best .{0,20}(sites|reviews)",
    r"crypto\s*giveaway",
    # English SEO explainers that keyword-match an ETF or a coin and carry no news at all.
    r"what is .{0,45}(etf|stock|fund)|how .{0,25}works",
    r"^\s*top \d+|things to know|here'?s why",
    r"deep dive|explained:|everything you need to know",
)

# A single alt coin's own move is not the channel's subject. The story still goes out when it is
# breaking or the operator picked it - a regulator acting on one token is news, its price is not.
ALT_ONLY = re.compile(
    r"\b(solana|sol\b|xrp|ripple|dogecoin|doge|cardano|ada\b|zcash|zec|sei\b|pepe|toncoin|"
    r"avalanche|avax|shiba|bonk|chainlink|polygon|matic|arbitrum|optimism|aptos|sui\b|"
    r"litecoin|ltc|tron|trx|stellar|xlm|near\b|injective|polkadot|dot\b|cosmos|atom\b|"
    r"filecoin|uniswap|aave|lido|jupiter|worldcoin|ondo|hyperliquid|bittensor|celestia|"
    r"kaspa|render|fetch\.ai|stargate|ethena|pendle|aerodrome|jto|pyth|sei network)\b", re.I)

# Culture and celebrity ride the same feeds and score the same keywords a market story does.
CELEBRITY = re.compile(
    r"\b(sheeran|taylor swift|beyonc|kardashian|bts\b|blackpink|netflix series|box office|"
    r"premiere|movie|actor|actress|singer|album|concert|celebrity|royal family)\b", re.I)

# Words that appear in almost every headline of this feed: they carry no identity, and keeping
# them would make two unrelated stories look like the same one.
STOPWORDS = {
    "the", "and", "for", "with", "after", "amid", "says", "said", "will", "has", "have", "its",
    "from", "that", "this", "are", "was", "were", "over", "into", "not", "but", "more", "than",
    "about", "new", "top", "how", "why", "what", "who", "out", "off", "up", "down", "you", "your",
    "bitcoin", "btc", "crypto", "cryptocurrency", "market", "markets", "price", "news", "report",
    "reports", "reuters", "bloomberg", "coinness", "today", "week", "month", "year", "could",
    "would", "may", "might", "still", "also", "first", "amid", "as", "at", "in", "on", "to",
    "비트코인", "코인", "가상자산", "시장", "뉴스", "기자", "보도", "관련", "오늘", "지난",
}

# The same market update is rewritten all day by every aggregator ("Bitcoin holds above $80,000 as
# ETF inflows...", "Bitcoin shrugs off headwinds to reclaim $81,000..."). Character similarity does
# not catch those - the words differ - so a recap-shaped headline is rate-limited instead: one per
# window, and a bigger move that actually breaks the pattern still gets through.
MARKET_RECAP = re.compile(
    r"\$\d{2,3},\d{3}|\$\d{2,3}k\b|market trends|crypto overview|(daily|weekly) (market )?"
    r"(recap|wrap|report)|(bitcoin|btc|이더리움|eth)\b.{0,30}"
    r"(holds?|reclaims?|returns?|surges?|eases|steadies|touches|rebounds?|shrugs|climbs|dips|"
    r"slips|rallies|retreats|gains?|rises?|falls?|closes|주춤|반등|하락|상승)", re.I)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


MIN_PRIORITY = env_int("TG_MIN_PRIORITY", 4)
COOLDOWN_SECONDS = env_int("TG_COOLDOWN_SECONDS", 180)
MAX_PER_HOUR = env_int("TG_MAX_PER_HOUR", 12)
WINDOW_HOURS = env_int("TG_WINDOW_HOURS", 3)
MAX_PER_TICK = env_int("TG_MAX_PER_TICK", 3)
CANDIDATE_LIMIT = env_int("TG_CANDIDATE_LIMIT", 600)
# A channel posts what is new, not what is interesting in hindsight: after an outage the window
# still holds hours of eligible stories, and posting them would read as stale news to everyone
# already following the feed. An old story is dropped rather than queued.
MAX_AGE_MINUTES = env_int("TG_MAX_AGE_MINUTES", 90)
RECAP_COOLDOWN_MINUTES = env_int("TG_RECAP_COOLDOWN_MINUTES", 120)
EVENT_WINDOW_MINUTES = env_int("TG_EVENT_WINDOW_MINUTES", 180)
TRANSLATE = env_flag("TG_TRANSLATE", True)
DRY_RUN = env_flag("TG_DRY_RUN", False)

# Both providers speak the same chat-completions shape, so the keys are the only difference. The
# default is whichever account actually has credit - measured, not assumed: the DeepSeek key in
# this setup answered HTTP 402 (balance 0.00) while the OpenAI key answered normally.
PROVIDERS = {
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", "deepseek-flash"),
}
TRANSLATE_PROVIDER = (os.environ.get("TG_TRANSLATE_PROVIDER") or "openai").strip().lower()
TRANSLATE_MODEL = os.environ.get("TG_TRANSLATE_MODEL", "").strip()
SUMMARY_CHARS = env_int("TG_SUMMARY_CHARS", 180)

SYSTEM_PROMPT = (
    "너는 영어·중국어·일본어 뉴스를 한국어 채널 게시물로 옮기는 편집자다. 규칙: "
    "① 원문에 있는 사실과 숫자만 쓴다. 추측·전망·해석을 덧붙이지 않는다. "
    "② 제목은 40자 이내 한 줄, 요약은 두 줄(각 60자 이내)로 줄인다. "
    "③ 한자·한문을 쓰지 않는다. 회사·기관·인명은 통상 표기를 쓴다. "
    "④ 인용은 원문의 발화자를 밝힌 채로 유지한다. "
    "⑤ 출력은 다른 말 없이 JSON 하나만: {\"title\": \"...\", \"summary\": \"...\"}."
)


# ----------------------------------------------------------------------------- state

def db_path() -> Path:
    """The database the collector writes, resolved the same way the collector resolves it."""
    return Path(getattr(core, "DB_FILE", HERE.parent / "news.db"))


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path()), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS %s ("
        "link TEXT PRIMARY KEY, message_id INTEGER, posted_at TEXT NOT NULL, "
        "priority INTEGER, tag TEXT, title TEXT, title_key TEXT, source TEXT, mode TEXT, "
        "recap INTEGER DEFAULT 0, chat_id TEXT)" % STATE_TABLE
    )
    # The table is written by a timer on two hosts, so a row from an earlier revision can be
    # waiting here when a new column arrives: add it instead of failing the whole tick.
    columns = {row[1] for row in connection.execute("PRAGMA table_info(%s)" % STATE_TABLE)}
    for name, ddl in (("recap", "INTEGER DEFAULT 0"), ("title_key", "TEXT"), ("chat_id", "TEXT")):
        if name not in columns:
            connection.execute("ALTER TABLE %s ADD COLUMN %s %s" % (STATE_TABLE, name, ddl))
    return connection


def posted(connection: sqlite3.Connection, hours: int = 24) -> list[sqlite3.Row]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return list(connection.execute(
        "SELECT * FROM %s WHERE posted_at >= ? ORDER BY posted_at" % STATE_TABLE, (cutoff,)))


def last_post_at(connection: sqlite3.Connection) -> datetime | None:
    row = connection.execute("SELECT MAX(posted_at) AS t FROM %s" % STATE_TABLE).fetchone()
    if not row or not row["t"]:
        return None
    try:
        return datetime.fromisoformat(row["t"])
    except ValueError:
        return None


def posts_within(connection: sqlite3.Connection, now: datetime, seconds: int) -> int:
    cutoff = (now - timedelta(seconds=seconds)).isoformat()
    row = connection.execute(
        "SELECT COUNT(*) AS n FROM %s WHERE posted_at >= ?" % STATE_TABLE, (cutoff,)).fetchone()
    return int(row["n"] if row else 0)


def last_recap_at(connection: sqlite3.Connection) -> datetime | None:
    row = connection.execute(
        "SELECT MAX(posted_at) AS t FROM %s WHERE recap = 1" % STATE_TABLE).fetchone()
    if not row or not row["t"]:
        return None
    try:
        return datetime.fromisoformat(row["t"])
    except ValueError:
        return None


def already_posted(connection: sqlite3.Connection, link: str, keep: set[str]) -> bool:
    if link in keep:
        return True
    row = connection.execute("SELECT 1 FROM %s WHERE link = ?" % STATE_TABLE, (link,)).fetchone()
    return row is not None


def recently_posted(stamp: str, now: datetime) -> bool:
    try:
        when_posted = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return False
    if when_posted.tzinfo is None:
        when_posted = when_posted.replace(tzinfo=timezone.utc)
    return (now - when_posted).total_seconds() <= EVENT_WINDOW_MINUTES * 60


# ----------------------------------------------------------------------------- selection

def is_noise(title: str) -> str:
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, title, re.I):
            return pattern
    return ""


def candidates(connection: sqlite3.Connection, window_hours: int) -> list[dict[str, Any]]:
    """The rows eligible for the channel, newest first.

    Two reads, because a pick outranks the star score rather than adding to it: the operator's
    judgement is a deliberate act on one story, and the story it lands on has to reach the channel
    even when the keywords scored it low. Picked rows are taken regardless of region - a pick in
    the Thailand tab is still the operator saying "this one".
    """
    seen: dict[str, dict[str, Any]] = {}
    reads = (
        {"region": core.GLOBAL_REGION, "minimum_priority": MIN_PRIORITY, "picked_only": False},
        {"region": "", "minimum_priority": 0, "picked_only": True},
    )
    for read in reads:
        rows, _total, _counts = core.query_articles(hours=window_hours, limit=CANDIDATE_LIMIT, **read)
        for row in rows:
            item = dict(row)
            item["channel_pick"] = bool(item.get("picked")) or read["picked_only"]
            seen.setdefault(item["link"], item)
    ordered = sorted(seen.values(), key=lambda item: (item.get("published_at") or ""), reverse=True)
    return ordered


def pick_tag(item: dict[str, Any]) -> str:
    if item.get("channel_pick"):
        return "[티모의 선택]"
    return "[속보]" if int(item.get("priority") or 0) >= 5 else "[기사]"


def age_minutes(item: dict[str, Any], now: datetime) -> float | None:
    raw = str(item.get("published_at") or "")
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (now - stamp).total_seconds() / 60.0


def worth_posting(item: dict[str, Any], now: datetime | None = None) -> tuple[bool, str]:
    title = item.get("title") or ""
    if is_noise(title):
        return False, "noise"
    if CELEBRITY.search(title):
        return False, "culture"
    if not (item.get("link") or "").strip():
        return False, "no link"
    if now is not None:
        age = age_minutes(item, now)
        if age is not None and age > MAX_AGE_MINUTES:
            return False, "stale (%.0f min)" % age
    if not (item.get("channel_pick") or int(item.get("priority") or 0) >= 5) and ALT_ONLY.search(title):
        return False, "alt-specific"
    return True, ""


def is_recap(title: str) -> bool:
    return bool(MARKET_RECAP.search(title or ""))


def tokens(title: str) -> set[str]:
    """The identifying words of a headline, with the boilerplate of this feed removed."""
    out: set[str] = set()
    for token in re.findall(r"[0-9A-Za-z가-힣]+", (title or "").lower()):
        if len(token) < 2 or token in STOPWORDS or re.fullmatch(r"[0-9]+", token):
            continue
        out.add(token)
    return out


def _shared_tokens(left: set[str], right: set[str]) -> int:
    """Shared tokens, counting a prefix match (발사 / 발사체) as the same word."""
    shared = 0
    for one in left:
        for other in right:
            if one == other or (len(one) >= 3 and len(other) >= 3 and
                                (one.startswith(other) or other.startswith(one))):
                shared += 1
                break
    return shared


def same_event(one: set[str], other: set[str]) -> bool:
    """Whether two headlines are the same story told twice.

    Character similarity catches a rewrite; this catches the same event arriving from a second
    source with different wording - "국회의장" against "의회의장", or an English rewrite of the
    same missile launch - which is what a channel actually gets punished for. It is only applied
    inside a short window, because two different stories about the same subject a day apart are
    not a duplicate.
    """
    if not one or not other:
        return False
    shared = _shared_tokens(one, other)
    if shared < 2:
        return False
    union = len(one) + len(other) - shared
    return shared >= 3 or (union and shared / union >= 0.5)


# ----------------------------------------------------------------------------- text

def has_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))


def rewrite(title: str, summary: str) -> tuple[str, str] | None:
    """Korean title and two-line summary for a story that is not in Korean."""
    url, key_name, default_model = PROVIDERS.get(TRANSLATE_PROVIDER, PROVIDERS["openai"])
    key = os.environ.get(key_name, "").strip()
    if not TRANSLATE or not key:
        return None
    body = {
        "model": TRANSLATE_MODEL or default_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "제목: %s\n요약: %s" % (title, summary[:600])},
        ],
        "temperature": 0,
        "max_tokens": 400,
    }
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
    except Exception as exc:  # a failed rewrite must not cost the story
        logging.warning("rewrite failed: %s", str(exc)[:120])
        return None
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    title_ko = str(data.get("title") or "").strip()
    summary_ko = str(data.get("summary") or "").strip()
    if not title_ko:
        return None
    return title_ko, summary_ko


def aggregator(link: str) -> bool:
    host = urllib.parse.urlsplit(link).netloc.lower()
    return host.endswith("news.google.com")


def when(item: dict[str, Any]) -> str:
    raw = str(item.get("published_at") or "")
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return ""
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(ICT).strftime("%H:%M")


def render(item: dict[str, Any], title: str, summary: str, original_title: str = "") -> str:
    tag = pick_tag(item)
    lines = ["<b>%s</b> %s" % (tag, escape(title))]
    if original_title:
        lines.append("<i>%s</i>" % escape(original_title))
    note = str(item.get("pick_note") or "").strip()
    if note:
        lines.append("🍄 <b>티모의 선택</b> · %s" % escape(note))
    if summary:
        lines.append("")
        lines.append(escape(summary))
    categories = item.get("categories") or []
    if isinstance(categories, str):
        categories = [categories]
    meta = [str(item.get("source") or ""), " · ".join([c for c in categories[:2] if c])]
    meta.append("★%d" % int(item.get("priority") or 0))
    lines.append("")
    lines.append(escape(" · ".join([part for part in meta if part])))
    stamp = when(item)
    if stamp:
        lines.append("발행 %s ICT" % stamp)
    link = str(item.get("link") or "")
    if aggregator(link):
        lines.append('<a href="%s">집계 링크 (구글뉴스)</a>' % escape(link))
    else:
        lines.append('<a href="%s">원문 보기</a>' % escape(link))
    return "\n".join(lines)[:LINK_CHARS]


def escape(text: str) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ----------------------------------------------------------------------------- telegram

def telegram(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(BOT_API % (token, method), data=data)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def send(text: str, preview: bool) -> dict[str, Any]:
    return telegram("sendMessage", {
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": json.dumps({"is_disabled": not preview, "prefer_small_media": True}),
        "disable_notification": "false",
    })


# ----------------------------------------------------------------------------- one tick

def eligible(item: dict[str, Any], now: datetime, last: datetime | None, in_hour: int) -> tuple[bool, str]:
    """Pacing: a breaking story never waits, an ordinary one waits its turn."""
    if item.get("channel_pick") or int(item.get("priority") or 0) >= 5:
        if in_hour >= MAX_PER_HOUR:
            return False, "hourly cap"
        return True, ""
    if in_hour >= MAX_PER_HOUR:
        return False, "hourly cap"
    if last is not None and (now - last).total_seconds() < COOLDOWN_SECONDS:
        return False, "cooldown"
    return True, ""


def tick(connection: sqlite3.Connection, now: datetime | None = None, limit: int = 0,
         quiet: bool = False) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    items = candidates(connection, WINDOW_HOURS)
    recent = posted(connection, 24)
    keys = [row["title_key"] or "" for row in recent]
    keep: set[str] = {row["link"] for row in recent}
    events = [(row["posted_at"], tokens(row["title"] or "")) for row in recent]
    last = last_post_at(connection)
    in_hour = posts_within(connection, now, 3600)
    last_recap = last_recap_at(connection)
    out: list[dict[str, Any]] = []
    sent = 0

    for item in items:
        if limit and sent >= limit:
            break
        link = str(item.get("link") or "")
        if already_posted(connection, link, keep):
            continue
        ok, why = worth_posting(item, now)
        if not ok:
            logging.info("skip (%s): %s", why, (item.get("title") or "")[:70])
            continue
        title_now = str(item.get("title") or "")
        key = core.normalize_title(title_now)
        sig = tokens(title_now)
        if key and any(core._similar_title(key, old) for old in keys if old):
            logging.info("skip (duplicate of an earlier post): %s", title_now[:70])
            continue
        if any(same_event(sig, old) for stamp, old in events if recently_posted(stamp, now)):
            logging.info("skip (same story as an earlier post): %s", title_now[:70])
            continue
        recap = is_recap(item.get("title") or "")
        if recap and last_recap is not None and \
                (now - last_recap).total_seconds() < RECAP_COOLDOWN_MINUTES * 60 and \
                not item.get("channel_pick"):
            logging.info("hold (market recap cooldown): %s", (item.get("title") or "")[:70])
            continue
        ok, why = eligible(item, now, last, in_hour)
        if not ok:
            logging.info("hold (%s): %s", why, (item.get("title") or "")[:70])
            continue

        title = str(item.get("title") or "")
        summary = re.sub(r"\s+", " ", str(item.get("summary") or "")).strip()
        if not has_korean(title):
            rewritten = rewrite(title, summary)
            if rewritten:
                summary = rewritten[1] or summary
                title = rewritten[0]
            else:
                # The Korean rewrite is the requested form; when it fails the reader still gets the
                # story, in the language it was published in, rather than nothing at all.
                title = title[:120] + ("…" if len(title) > 120 else "")
        if len(summary) > SUMMARY_CHARS:
            # A channel post is read on a phone: the source feed's own summary is often longer than
            # the whole message should be.
            summary = summary[:SUMMARY_CHARS].rstrip() + "…"
        text = render(item, title, summary)

        if DRY_RUN or quiet:
            out.append({"link": link, "text": text, "priority": item.get("priority"),
                        "tag": pick_tag(item), "title": title, "recap": recap})
            keep.add(link)
            keys.append(key)
            events.append((now.isoformat(), sig))
            if recap:
                last_recap = now
            sent += 1
            continue
        try:
            response = send(text, preview=not aggregator(link))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            logging.error("telegram refused (%s): %s", exc.code, detail)
            if exc.code == 429:
                break  # a rate limit is a signal to stop this tick, not to hammer the API
            continue
        except Exception as exc:
            logging.error("send failed: %s", str(exc)[:160])
            continue
        message_id = (response.get("result") or {}).get("message_id")
        connection.execute(
            "INSERT OR REPLACE INTO %s (link, message_id, posted_at, priority, tag, title, title_key,"
            " source, mode, recap, chat_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)" % STATE_TABLE,
            (link, message_id, now.isoformat(), int(item.get("priority") or 0), pick_tag(item),
             title, key, str(item.get("source") or ""),
             "pick" if item.get("channel_pick") else "star", 1 if recap else 0,
             os.environ.get("TELEGRAM_CHAT_ID", "")))
        connection.commit()
        keep.add(link)
        keys.append(key)
        events.append((now.isoformat(), sig))
        if recap:
            last_recap = now
        last = now
        in_hour += 1
        sent += 1
        logging.info("posted %s (%s): %s", pick_tag(item),
                     item.get("source"), title[:70])
    return out


def replay(connection: sqlite3.Connection, hours: int, step_seconds: int = 60) -> list[dict[str, Any]]:
    """Walk a past window through the same rules, a simulated minute at a time.

    This is the acceptance check for the pacing: it says how many messages the channel would have
    received, not how many stories scored high enough.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    stamps: list[datetime] = []
    cursor = start
    while cursor <= end:
        stamps.append(cursor)
        cursor += timedelta(seconds=step_seconds)

    items = candidates(connection, hours)
    by_time = sorted(items, key=lambda item: item.get("published_at") or "")
    taken: set[str] = set()
    keys: list[str] = []
    events: list[tuple[str, set[str]]] = []
    last: datetime | None = None
    last_recap: datetime | None = None
    hour_count = 0
    hour_anchor = start
    out: list[dict[str, Any]] = []

    for now in stamps:
        if (now - hour_anchor).total_seconds() >= 3600:
            hour_anchor = now
            hour_count = 0
        for item in by_time:
            link = str(item.get("link") or "")
            if link in taken:
                continue
            published = item.get("published_at") or ""
            if published and published > now.isoformat():
                continue
            ok, _why = worth_posting(item, now)
            if not ok:
                taken.add(link)
                continue
            key = core.normalize_title(item.get("title") or "")
            sig = tokens(str(item.get("title") or ""))
            if key and any(core._similar_title(key, old) for old in keys if old):
                taken.add(link)
                continue
            if any(same_event(sig, old) for stamp, old in events if recently_posted(stamp, now)):
                taken.add(link)
                continue
            recap = is_recap(item.get("title") or "")
            if recap and last_recap is not None and not item.get("channel_pick") and \
                    (now - last_recap).total_seconds() < RECAP_COOLDOWN_MINUTES * 60:
                continue
            if item.get("channel_pick") or int(item.get("priority") or 0) >= 5:
                if hour_count >= MAX_PER_HOUR:
                    continue
            else:
                if hour_count >= MAX_PER_HOUR:
                    continue
                if last is not None and (now - last).total_seconds() < COOLDOWN_SECONDS:
                    continue
            taken.add(link)
            keys.append(key)
            events.append((now.isoformat(), sig))
            if recap:
                last_recap = now
            last = now
            hour_count += 1
            out.append({"at": now.astimezone(ICT).strftime("%H:%M"), "tag": pick_tag(item),
                        "source": item.get("source"), "priority": item.get("priority"),
                        "recap": recap, "title": (item.get("title") or "")[:80]})
    return out


def lock() -> bool:
    try:
        stamp = LOCK_FILE.read_text().strip()
        if time.time() - float(stamp) < 180:
            return False
    except (OSError, ValueError):
        pass
    try:
        LOCK_FILE.write_text(str(time.time()))
    except OSError:
        return True  # an unwritable /tmp must not stop the channel
    return True


def unlock() -> None:
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Push important stories to the Telegram channel")
    parser.add_argument("--dry-run", action="store_true", help="print what would be posted")
    parser.add_argument("--replay", type=int, metavar="HOURS",
                        help="walk a past window through the same rules and print the result")
    parser.add_argument("--limit", type=int, default=0, help="stop after N messages")
    parser.add_argument("--skip-lock", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global DRY_RUN
    if args.dry_run:
        DRY_RUN = True

    connection = connect()
    try:
        if args.replay:
            rows = replay(connection, args.replay)
            print("replay %dh: %d messages" % (args.replay, len(rows)))
            for row in rows:
                print("  %s %-14s %s ★%s  %s" % (row["at"], row["tag"], row["source"],
                                                 row["priority"], row["title"]))
            return
        if not args.skip_lock and not lock():
            logging.info("another run is in progress")
            return
        try:
            rows = tick(connection, limit=args.limit)
        finally:
            unlock()
        if args.dry_run:
            print("dry run: %d messages" % len(rows))
            for row in rows:
                print("-" * 60)
                print(row["text"])
    finally:
        connection.close()


if __name__ == "__main__":
    main()
