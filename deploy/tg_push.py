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
import html
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
import jev_gate  # noqa: E402
import google_news  # noqa: E402

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
BODY_CHARS = env_int("TG_BODY_CHARS", 240)
# `foreign` rewrites only what is not in Korean; `always` puts every post through the editor, so
# the body/note/tag lines read the same whether the source was Korean or not. The channel format
# is fixed, and a post that skips the editor is visibly a different shape from the rest.
REWRITE_MODE = (os.environ.get("TG_REWRITE") or "always").strip().lower()
# The footer carries the channel's own link, and the link is part of the frozen shape: a post
# whose footer has no link reads as a different format, so an unset TG_CHANNEL_LINK falls back to
# the channel page instead of dropping the link.
DEFAULT_CHANNEL_LINK = "https://teemobkk.io/news/"
_raw_channel_link = os.environ.get("TG_CHANNEL_LINK", "").strip() or DEFAULT_CHANNEL_LINK
CHANNEL_LINK = _raw_channel_link.rstrip("/") + "/"
# The channel contract is ICT. Keep the old environment switch out of the renderer so a stale
# host .env cannot create a second timestamp format.
TZ_NAME = "ICT"
STAMP_ZONE = ICT

SYSTEM_PROMPT = (
    "너는 한국어 텔레그램 속보 채널의 편집자다. 주어진 제목과 요약만 근거로 게시물을 쓴다. 규칙: "
    "① 사실과 숫자는 원문에 있는 것만 쓴다. 없는 수치·기관·인과를 만들지 않는다. "
    "② title: 40자 이내, 사실만. 과장·낚시·이모지 금지. 원문이 한국어면 표현을 살린다. "
    "③ body: 1~2문장. 원문에 있는 숫자를 그대로 살려 구체적으로 쓴다. 해석·전망은 넣지 않는다. "
    "④ note: 시장·정책 함의를 한 줄(60자 이내). 원문 수치에 근거해 구체적으로 쓰고 단정하지 않는다"
    "('~할 수 있다'). 시장과 무관한 사건이면 그 사건이 이어질 다음 단계를 사실에 근거해 짚는다. "
    "⑤ tags: 사건·주제·지역을 나타내는 한국어 단어 3개. '#' 없이 단어만. "
    "⑥ 한자·한문을 쓰지 않는다. 회사·기관·인명은 통용 표기. "
    "⑦ 출력은 다른 말 없이 JSON 하나만: {\"title\": \"...\", \"body\": \"...\", \"note\": \"...\", "
    "\"tags\": [\"가\", \"나\", \"다\"]}"
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
    connection.execute(
        "CREATE TABLE IF NOT EXISTS jev_runs ("
        "run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, mode TEXT NOT NULL, "
        "candidate_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS jev_decisions ("
        "run_id TEXT NOT NULL, link TEXT NOT NULL, importance TEXT, "
        "duplicate_confidence REAL, freshness TEXT, blocked INTEGER NOT NULL DEFAULT 0, "
        "fallback INTEGER NOT NULL DEFAULT 0, raw_json TEXT, created_at TEXT NOT NULL, "
        "PRIMARY KEY (run_id, link))"
    )
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


def persist_jev(connection: sqlite3.Connection, batch: jev_gate.Batch,
                items: list[dict[str, Any]], now: datetime) -> None:
    """Persist only auditable JEV metadata; never persist the API key or request headers."""
    status = "fallback" if batch.fallback else ("ok" if batch.decisions else "empty")
    connection.execute(
        "INSERT OR REPLACE INTO jev_runs "
        "(run_id, started_at, mode, candidate_count, status, error) VALUES (?,?,?,?,?,?)",
        (batch.run_id, now.isoformat(), jev_gate.MODE, len(items), status, batch.error or None),
    )
    for item in items:
        link = str(item.get("link") or "")
        decision = batch.decisions.get(link)
        connection.execute(
            "INSERT OR REPLACE INTO jev_decisions "
            "(run_id, link, importance, duplicate_confidence, freshness, blocked, fallback, raw_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                batch.run_id,
                link,
                decision.importance if decision else None,
                decision.duplicate_confidence if decision else None,
                decision.freshness if decision else None,
                0,
                1 if batch.fallback else 0,
                json.dumps(decision.raw if decision else {"error": batch.error}, ensure_ascii=False),
                now.isoformat(),
            ),
        )
    connection.commit()


def mark_jev_blocked(connection: sqlite3.Connection, run_id: str, link: str) -> None:
    connection.execute(
        "UPDATE jev_decisions SET blocked = 1 WHERE run_id = ? AND link = ?",
        (run_id, link),
    )
    connection.commit()


def is_single_alt_notice(item: dict[str, Any]) -> bool:
    """Return true for routine news about low-impact altcoins."""
    return jev_gate.is_single_alt_notice(item)


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
    """The bracket tag on the first line. One tag only, and the same five words the channel uses."""
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
    if is_single_alt_notice(item):
        return False, "altcoin-noise"
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


def clean_body(text: Any, limit: int) -> str:
    """Normalize spaces without flattening deliberate paragraph breaks."""
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", str(text or "")):
        clean = re.sub(r"[ \t]+", " ", paragraph).strip()
        if clean:
            paragraphs.append(clean)
    return "\n\n".join(paragraphs)[:limit]


def brief(item: dict[str, Any], title: str, summary: str) -> dict[str, Any] | None:
    """The channel post's parts, written from the stored headline and summary.

    title, body, note and tags are produced together on purpose: the body has to stay factual while
    the note is an interpretation, and asking for them in one call is what keeps the line between
    the two where the format says it is.
    """
    url, key_name, default_model = PROVIDERS.get(TRANSLATE_PROVIDER, PROVIDERS["openai"])
    key = os.environ.get(key_name, "").strip()
    if not TRANSLATE or not key:
        return None
    if REWRITE_MODE == "foreign" and has_korean(title):
        return None
    payload_body = {
        "model": TRANSLATE_MODEL or default_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "제목: %s\n요약: %s" % (title, summary[:700])},
        ],
        "temperature": 0,
        "max_tokens": 500,
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload_body).encode("utf-8"),
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
    out = {
        "title": str(data.get("title") or "").strip()[:80],
        "body": clean_body(data.get("body"), BODY_CHARS),
        "note": re.sub(r"\s+", " ", str(data.get("note") or "")).strip()[:120],
        "tags": [str(tag).strip().lstrip("#") for tag in (data.get("tags") or []) if str(tag).strip()],
    }
    if not out["title"]:
        return None
    return out


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
    return stamp.astimezone(STAMP_ZONE).strftime("%Y-%m-%d %H:%M:%S")


def fallback_tags(item: dict[str, Any]) -> list[str]:
    """Tags when the editor call failed: the stored categories, which are already Korean topics."""
    categories = item.get("categories") or item.get("category") or []
    if isinstance(categories, str):
        # The stored column is a comma-joined string; the reader turns it into a list, and a row
        # read straight from the table still carries the raw value - one tag per category, never
        # one tag that contains the commas.
        categories = categories.split(",")
    tags = [str(value).replace("·", "").replace(" ", "") for value in categories if value]
    return [tag for tag in tags if tag][:3]


def merge_tags(written: list[str], stored: list[str],
               minimum: int = 2, maximum: int = 4) -> list[str]:
    """The tag line of the frozen shape carries 2~4 hashtags.

    The editor's words come first because they describe the story best. The stored categories are
    only used to reach the minimum - a one-word answer must not leave a thin tag line, and a full
    answer must not collect extra tags it did not ask for.
    """
    out: list[str] = []
    for tag in written:
        clean = str(tag).strip().lstrip("#").replace("·", "").replace(" ", "")
        if clean and clean not in out:
            out.append(clean)
    for tag in stored:
        if len(out) >= minimum:
            break
        clean = str(tag).strip().lstrip("#").replace("·", "").replace(" ", "")
        if clean and clean not in out:
            out.append(clean)
    return out[:maximum]


def attach_original_link(connection: sqlite3.Connection, item: dict[str, Any]) -> str:
    """Add a verified publisher URL for display without changing the stored story identity."""
    link = str(item.get("link") or "").strip()
    if not google_news.is_aggregator(link):
        return link
    original = google_news.original_for(link, google_news.load(connection))
    if original == link:
        resolved = google_news.resolve(link)
        if resolved:
            google_news.remember(connection, {link: resolved})
            original = resolved
    if original != link:
        item["original_link"] = original
    return original


def render(item: dict[str, Any], title: str, body: str, note: str,
           tags: list[str]) -> str:
    """Render the single approved channel shape.

    The channel uses one format only:

        [기사] 제목

        본문 1
        본문 2

        Teemo's Note
        해석 한 줄

        관련 : #태그1 #태그2
        출처 (@url:`<원문>`) | YYYY-MM-DD HH:MM:SS ICT
        TeemoBKK 라이브 뉴스 (@url:`<채널 링크>`)

    The old markdown, raw-URL, separate ticker, and separate hashtag-line renderers are deliberately
    gone. A missing editor note gets a visible fallback sentence so the timer cannot create a second
    shape when the rewrite provider is unavailable.
    """
    safe_title = html.escape(title, quote=False)
    safe_body = html.escape(body, quote=False)
    safe_note = html.escape(note.strip() or "원문 추가 확인 필요", quote=False)
    clean_tags = [str(tag).strip().lstrip("#") for tag in tags if str(tag).strip()]
    lines = ["%s %s" % (pick_tag(item), safe_title)]
    if safe_body:
        lines.extend(["", safe_body])
    lines.extend(["", NOTE_LABEL, safe_note])
    if clean_tags:
        lines.extend(["", "관련 : " + " ".join("#" + html.escape(tag, quote=False) for tag in clean_tags[:4])])
    stamp = when(item)
    link = str(item.get("link") or "").strip() or "원문 확인 필요"
    safe_link = html.escape(link, quote=True)
    if stamp:
        lines.append('출처: <a href="%s">출처</a> | %s %s' % (safe_link, stamp, TZ_NAME))
    else:
        lines.append('출처: <a href="%s">출처</a>' % safe_link)
    safe_channel_link = html.escape(CHANNEL_LINK, quote=True)
    lines.append('<a href="%s">TeemoBKK 라이브 뉴스</a>' % safe_channel_link)
    return "\n".join(lines)[:LINK_CHARS]


def escape(text: str) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ----------------------------------------------------------------------------- shape check

# The channel contract is fixed. Do not let a stale environment variable or a separate editor skill
# select a second note label or link shape.
TITLE_LINE = re.compile(r"^\[(속보|기사|지표|카더라|분석|티모의 선택)\] \S")
NOTE_LABEL = "Teemo's Note"
NOTE_HEAD = re.compile(r"^%s$" % re.escape(NOTE_LABEL))
RELATED_LINE = re.compile(r"^관련 : #\S+(?: #\S+){0,3}$")
SOURCE_LINE = re.compile(
    r'^출처: <a href="[^"]+">(?:출처|구글 뉴스\(원문 미확인\))</a> \| \d{4}-\d{2}-\d{2} '
    r'\d{2}:\d{2}:\d{2} ICT$'
)
# Reject legacy markdown, raw URL wrappers, and the old English footer.
BANNED_SHAPES = (
    (re.compile(r"\]\(\s*https?://"), "markdown link"),
    (re.compile(r"@url:"), "visible URL wrapper"),
    (re.compile(r"^#\S+ "), "hash-tag first line"),
    (re.compile(r"^출처:\s*https?://", re.M), "raw source URL"),
    (re.compile(r"TeemoBKK Live News"), "old English footer"),
)


def validate_post(text: str) -> list[str]:
    """Return every violation of the one approved channel shape."""
    problems: list[str] = []
    lines = [line.rstrip() for line in (text or "").split("\n")]
    if not text:
        return ["empty post"]
    if len(text) > LINK_CHARS:
        problems.append("over %d characters" % LINK_CHARS)
    if not lines[0] or not TITLE_LINE.match(lines[0]):
        problems.append("first line is not '[태그] 제목'")
    notes = [i for i, line in enumerate(lines) if NOTE_HEAD.match(line)]
    if len(notes) != 1:
        problems.append("expected exactly one '%s' line, found %d" % (NOTE_LABEL, len(notes)))
    if notes:
        note_index = notes[0]
        if note_index + 1 >= len(lines) or not lines[note_index + 1].strip():
            problems.append("note body is missing")
    related = [i for i, line in enumerate(lines) if RELATED_LINE.match(line)]
    if len(related) != 1:
        problems.append("expected one '관련 : #tag ...' line, found %d" % len(related))
    sources = [i for i, line in enumerate(lines) if SOURCE_LINE.match(line)]
    if len(sources) != 1:
        problems.append("expected one ICT source line, found %d" % len(sources))
    footer = '<a href="%s">TeemoBKK 라이브 뉴스</a>' % html.escape(CHANNEL_LINK, quote=True)
    if lines[-1].strip() != footer:
        problems.append("footer line is not '%s'" % footer)
    if notes and related and sources and not (notes[0] < related[0] < sources[0]):
        problems.append("line order is not note -> related -> source")
    for pattern, label in BANNED_SHAPES:
        if pattern.search(text):
            problems.append("carries %s" % label)
    return problems


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
        "link_preview_options": json.dumps({"prefer_small_media": True}),
        "disable_notification": "false",
    })


# ----------------------------------------------------------------------------- agent path

# The second pipeline - the VPS agent that picks stories with a model - posts through the functions
# below instead of writing the message itself. Two renderers writing one channel is how the channel
# ended up with two formats: a post whose link style depends on which model run wrote it. Here the
# agent brings words and a verified link, this script brings the shape, and the shape check above
# decides whether the post may go out at all.

def article_row(connection: sqlite3.Connection, link: str) -> dict[str, Any]:
    """The stored row the shape's ticker, source and stamp lines are read from."""
    row = connection.execute(
        "SELECT link, title, summary, source, asset, priority, published_at, categories "
        "FROM articles WHERE link = ?", (link,)).fetchone()
    return dict(row) if row else {}


def operator_note(connection: sqlite3.Connection, link: str) -> str:
    row = connection.execute("SELECT note FROM picked_links WHERE link = ?", (link,)).fetchone()
    return str(row["note"] or "") if row else ""


def post_parts(connection: sqlite3.Connection, parts: dict[str, Any],
               now: datetime | None = None, quiet: bool = False) -> tuple[bool, str]:
    """Post one story the agent picked, through the same render() the timer uses."""
    now = now or datetime.now(timezone.utc)
    link = str(parts.get("link") or "").strip()
    if not link:
        return False, "no link"
    item = article_row(connection, link)
    if not item:
        return False, "link is not in news.db - verify the original before posting"
    attach_original_link(connection, item)
    note_here = operator_note(connection, link)
    item["channel_pick"] = bool(parts.get("pick")) or bool(note_here)
    # The same alt-notice gate protects the outbox path. Picks bypass the filter.
    if is_single_alt_notice(item):
        return False, "altcoin-noise"
    title = str(parts.get("title") or "").strip()
    if not title:
        return False, "no title"
    body = clean_body(parts.get("body"), BODY_CHARS)
    note = re.sub(r"\s+", " ", str(parts.get("note") or "")).strip()[:120] or note_here
    if not note:
        return False, "no note"
    tags = merge_tags(parts.get("tags") or [], fallback_tags(item))
    text = render(item, title[:80], body, note, tags)
    problems = validate_post(text)
    if problems:
        return False, "shape check failed: " + "; ".join(problems)
    if already_posted(connection, link, set()):
        return False, "already posted"
    if DRY_RUN or quiet:
        return True, text
    try:
        response = send(text, preview=not aggregator(link))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        return False, "telegram refused (%s): %s" % (exc.code, detail)
    except Exception as exc:
        return False, "send failed: %s" % str(exc)[:160]
    connection.execute(
        "INSERT OR REPLACE INTO %s (link, message_id, posted_at, priority, tag, title, title_key,"
        " source, mode, recap, chat_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)" % STATE_TABLE,
        (link, (response.get("result") or {}).get("message_id"), now.isoformat(),
         int(item.get("priority") or 0), pick_tag(item), title,
         core.normalize_title(str(item.get("title") or title)), str(item.get("source") or ""),
         "agent", 1 if is_recap(str(item.get("title") or "")) else 0,
         os.environ.get("TELEGRAM_CHAT_ID", "")))
    connection.commit()
    return True, text


def drain_outbox(connection: sqlite3.Connection, outbox: Path) -> tuple[int, int]:
    """Post what the VPS agent queued, through the same render() the timer uses.

    The agent cannot call this script: it runs in a container that has only its own data directory
    mounted, and that directory is where it writes the JSON parts. The host sees them under the
    mount, and this drain is what turns them into posts.

    A file that cannot be posted moves to `failed/` rather than staying in the queue. It has to:
    the queue directory is what the path unit watches, so a file that is never taken out keeps the
    unit triggering until systemd's start limit stops it (measured - one refused file produced four
    service starts in 34 seconds and failed both units). The file is kept, the reason is in the
    log, and a human decides what to do with it.
    """
    posted = 0
    held = 0
    done = outbox / "done"
    failed = outbox / "failed"
    for path in sorted(outbox.glob("*.json")):
        try:
            parts = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("outbox: unreadable %s: %s", path.name, str(exc)[:120])
            held += 1
            _set_aside(path, failed, "unreadable")
            continue
        ok, detail = post_parts(connection, parts)
        if not ok:
            logging.error("outbox: %s could not be posted: %s", path.name, detail)
            held += 1
            _set_aside(path, failed, detail)
            continue
        posted += 1
        logging.info("outbox: posted %s", parts.get("link", ""))
        if DRY_RUN:
            print("-" * 60)
            print(detail)
        else:
            _set_aside(path, done, "")
    return posted, held


def _set_aside(path: Path, directory: Path, reason: str) -> None:
    """Move a queued file out of the watch directory; a dry run never touches the queue."""
    if DRY_RUN:
        return
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path.replace(directory / path.name)
        if reason:
            logging.error("outbox: %s moved to %s/ (%s)", path.name, directory.name, reason[:80])
    except OSError as exc:
        logging.error("outbox: could not move %s: %s", path.name, str(exc)[:80])


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
    jev_items: list[dict[str, Any]] = []
    for candidate in items:
        if len(jev_items) >= jev_gate.BATCH_SIZE:
            break
        link = str(candidate.get("link") or "")
        if already_posted(connection, link, {row["link"] for row in recent}):
            continue
        ok, _why = worth_posting(candidate, now)
        if not ok:
            continue
        probe = dict(candidate)
        probe["_age_minutes"] = age_minutes(candidate, now)
        jev_items.append(probe)
    jev_batch = jev_gate.evaluate(
        jev_items,
        [str(row["title"] or "") for row in recent if row["title"]],
        now,
    )
    if jev_gate.MODE != "off":
        persist_jev(connection, jev_batch, jev_items, now)
        if jev_batch.fallback:
            logging.warning("JEV fallback: %s", jev_batch.error or "no decision")
        else:
            logging.info("JEV evaluated %d candidates (%s)", len(jev_batch.decisions), jev_batch.run_id)
    keys = [row["title_key"] or "" for row in recent]
    keep: set[str] = {row["link"] for row in recent}
    events = [(row["posted_at"], tokens(row["title"] or "")) for row in recent]
    # Keep signatures for candidates seen in this tick too. A candidate that is skipped because it
    # duplicates an older post must still block the next rewrite of the same event; otherwise the
    # second wording can slip through one minute later.
    tick_events: list[set[str]] = [signature for stamp, signature in events
                                    if recently_posted(stamp, now)]
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
        jev_decision = jev_batch.decisions.get(link)
        if jev_decision and jev_gate.MODE == "live" and jev_gate.should_block_duplicate(
                jev_decision, int(item.get("priority") or 0), bool(item.get("channel_pick"))):
            logging.info(
                "skip (JEV same-event %.2f): %s",
                jev_decision.duplicate_confidence,
                title_now[:70],
            )
            mark_jev_blocked(connection, jev_batch.run_id, link)
            tick_events.append(sig)
            continue
        if key and any(core._similar_title(key, old) for old in keys if old):
            logging.info("skip (duplicate of an earlier post): %s", title_now[:70])
            tick_events.append(sig)
            continue
        if any(same_event(sig, old) for old in tick_events):
            logging.info("skip (same story as an earlier candidate/post): %s", title_now[:70])
            tick_events.append(sig)
            continue
        # Reserve the event before pacing and writing. If this candidate is held by cooldown, a
        # second source for the same event must not become the post merely because it is next.
        tick_events.append(sig)
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

        raw_title = str(item.get("title") or "")
        raw_summary = clean_body(item.get("summary"), SUMMARY_CHARS)
        written = brief(item, raw_title, raw_summary)
        if written:
            title = written["title"]
            body = written["body"] or raw_summary[:BODY_CHARS]
            tags = merge_tags(written["tags"], fallback_tags(item))
            note = written["note"]
        else:
            # The editor call is what makes the body/note/tag lines; without it the post still goes
            # out in the same shape, with the stored text and the stored categories as tags.
            title = raw_title[:120] + ("…" if len(raw_title) > 120 else "")
            body = raw_summary[:SUMMARY_CHARS] + ("…" if len(raw_summary) > SUMMARY_CHARS else "")
            tags = fallback_tags(item)
            note = ""
        if item.get("channel_pick") and str(item.get("pick_note") or "").strip():
            # A pick carries the operator's own sentence; that outranks a written note.
            note = str(item["pick_note"]).strip()
        attach_original_link(connection, item)
        text = render(item, title, body, note, tags)
        problems = validate_post(text)
        if problems:
            # Fail closed: a post that does not match the frozen shape stays out of the channel.
            # In a dry run the text is still printed, with the reason, so the operator can see both.
            logging.error("shape check failed for %s: %s", link, "; ".join(problems))
            if DRY_RUN or quiet:
                out.append({"link": link, "text": text, "priority": item.get("priority"),
                            "tag": pick_tag(item), "title": title, "recap": recap,
                            "problems": problems})
                sent += 1
                continue
            continue

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
                keys.append(key)
                events.append((now.isoformat(), sig))
                continue
            if any(same_event(sig, old) for stamp, old in events if recently_posted(stamp, now)):
                taken.add(link)
                events.append((now.isoformat(), sig))
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
    parser.add_argument("--agent-json", metavar="PATH",
                        help="post one story the VPS agent wrote: JSON with link, title, body, "
                             "note, tags - rendered here, so both pipelines write one shape")
    parser.add_argument("--shape-check", metavar="PATH",
                        help="print the shape problems of a saved post file, exit 1 if it has any")
    parser.add_argument("--drain-outbox", metavar="DIR",
                        help="post every queued JSON the VPS agent wrote into DIR, then archive it "
                             "under DIR/done; a file that cannot be posted stays where it is")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global DRY_RUN
    if args.dry_run:
        DRY_RUN = True

    if args.shape_check:
        text = Path(args.shape_check).read_text(encoding="utf-8")
        problems = validate_post(text)
        for problem in problems:
            print("problem:", problem)
        print("shape: %s" % ("ok" if not problems else "broken"))
        sys.exit(1 if problems else 0)

    connection = connect()
    try:
        if args.drain_outbox:
            posted, held = drain_outbox(connection, Path(args.drain_outbox))
            print("outbox: %d posted, %d held" % (posted, held))
            return
        if args.agent_json:
            parts = json.loads(Path(args.agent_json).read_text(encoding="utf-8"))
            ok, detail = post_parts(connection, parts)
            if ok:
                print(detail if DRY_RUN else "posted: %s" % parts.get("link", ""))
                return
            logging.error("agent post refused: %s", detail)
            sys.exit(2)
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
                for problem in row.get("problems") or ():
                    print("PROBLEM:", problem)
                print(row["text"])
    finally:
        connection.close()


if __name__ == "__main__":
    main()
