"""Whale Alert's own alert feed, read from their Telegram channel.

whale-alert.io itself is a paid dashboard ($14.95/$29.95 a month after a 7 day trial)
and its API needs a key from developer.whale-alert.io, so nothing is fetched from the
site. The company publishes the same alerts, one message each, on Telegram:

    https://t.me/s/whale_alert_io

Each message reads

    🚨🚨🚨 29,425 $ETH (73,818,222 USD) transferred from unknown wallet to
    Coinbase Institutional
    Details  ->  https://whale-alert.io/transaction/ethereum/0x...

so the row links straight to their transaction page and needs no API key.

Two transports, because this machine cannot reach t.me (Thailand blocks it) while the
CI runner can:

    direct  https://t.me/s/<channel>            HTML, exact <time datetime> stamps
    proxy   https://r.jina.ai/https://t.me/...  markdown, date-only stamps

Only transfers of MIN_USD or more are published: the channel posts dozens a day and a
news feed does not need every $12M stablecoin shuffle.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

CHANNEL = "whale_alert_io"
DIRECT = "https://t.me/s/" + CHANNEL
PROXY = "https://r.jina.ai/" + DIRECT
# This machine cannot reach t.me (Thailand blocks it), so once the direct transport has
# failed twice the proxy is used straight away - without it every local cycle would sit
# on a 25 second connect timeout before falling back.
_direct_failures = 0
_direct_retry_after = 0.0
SOURCE = "Whale Alert"
SOURCE_TYPE = "social"
MIN_USD = 50_000_000
MINT_MIN_USD = 500_000_000
MAX_ITEMS = 25
TITLE_MAX = 170

ALERT = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*\$([A-Z0-9]{2,10})\s*\(([\d,]+)\s*USD\)"
    r"\s*(?:transferred|minted|burned)?\s*(?:from\s+(.+?))?\s*(?:to\s+(.+?))?\s*$",
    re.I)
DETAILS = re.compile(r"https://whale-alert\.io/transaction/[^\s)\"']+")
STAMP = re.compile(r"datetime=\"([^\"]+)\"")


def money(text: str) -> int:
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else 0


def clean(text: str) -> str:
    text = re.sub(r"(\*|_|#|\\)+", "", text)
    text = re.sub(r"🚨|⚠️|🐋", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_html(html: str) -> list[dict[str, Any]]:
    """Direct t.me HTML: message blocks carry an exact timestamp."""
    out: list[dict[str, Any]] = []
    blocks = re.split(r'<div class="tgme_widget_message[ _"]', html)
    for block in blocks[1:]:
        link = DETAILS.search(block.replace("&amp;", "&"))
        text = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        when = re.search(r"datetime=\"([^\"]+)\"", block)
        if not link or not text:
            continue
        out.append({
            "text": clean(text.group(1)),
            "link": link.group(0),
            "when": when.group(1) if when else "",
        })
    return out


def parse_markdown(body: str) -> list[dict[str, Any]]:
    """Fallback via r.jina.ai: the alert text and its Details link sit on separate
    lines and each message ends with a date-only stamp, so they are paired up here."""
    out: list[dict[str, Any]] = []
    stamp = ""
    pending = ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        day = re.fullmatch(r"([A-Z][a-z]+ \d{1,2})", line)
        if day:
            stamp = day.group(1)
            continue
        link = DETAILS.search(line)
        if link:
            if pending:
                out.append({"text": pending, "link": link.group(0), "when": stamp})
            pending = ""
            continue
        if line.startswith("[") or line.startswith("Title:") or line.startswith("URL Source:"):
            continue
        candidate = clean(line)
        if "USD" in candidate and ("transferred" in candidate.lower() or "minted" in candidate.lower()
                                   or "burned" in candidate.lower()):
            pending = candidate
    return out


def to_article(core: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    match = ALERT.search(row["text"])
    usd = money(match.group(3)) if match else 0
    if usd and usd < MIN_USD:
        return None
    title = re.sub(r"\s+", " ", row["text"]).strip()
    if not title:
        return None
    # Routine treasury issuance runs several times a day at the same size; only the
    # unusually large ones are worth a slot in the feed.
    if re.search(r"minted at .*treasury", title, re.I) and usd < MINT_MIN_USD:
        return None
    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX] + "…"
    when = row.get("when") or ""
    note = ""
    if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}", when):
        # The proxy transport only gives a posting date. Anchor it at midday so the row
        # is not pushed out of the 24 hour window by a whole day, and say so in the text
        # rather than implying a precision the source does not have.
        try:
            parsed = datetime.strptime(when + " %d" % datetime.now(timezone.utc).year, "%B %d %Y")
            when = parsed.replace(hour=12, tzinfo=timezone.utc).isoformat()
            note = "게시 날짜 기준(시각 미상)"
        except ValueError:
            when = ""
    published = core.parse_date(when) if when else datetime.now(timezone.utc).isoformat()
    if len(title) > TITLE_MAX - 30:
        title = title[:TITLE_MAX - 30] + "…"
    summary = title + ((" · " + note) if note else "")
    return core.make_article(title, row["link"], summary, published, SOURCE, SOURCE_TYPE)


def fetch_into(status: dict[str, Any], core: Any = None) -> list[dict[str, Any]]:
    if core is None:  # imported late so the collector can call us during its own import
        import live_news_dashboard as core
    hours = int(getattr(core, "RETENTION_HOURS", 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows: list[dict[str, Any]] = []
    transport = "direct"
    error = ""
    global _direct_failures, _direct_retry_after
    import time
    skip_direct = time.time() < _direct_retry_after
    try:
        if skip_direct:
            raise RuntimeError("direct transport cooling down")
        html = core.fetch_bytes(DIRECT, timeout=20).decode("utf-8", errors="replace")
        rows = parse_html(html)
        if not rows:
            raise RuntimeError("no messages parsed from direct HTML")
        _direct_failures = 0
        _direct_retry_after = 0.0
    except Exception as exc:
        error = str(exc)[:90]
        transport = "proxy"
        if not skip_direct:
            _direct_failures += 1
            # Cool down after the first failure: this host cannot reach t.me at all, and
            # waiting 20 seconds every cycle to rediscover that is pure waste. The CI
            # runner gets a fresh process each run, so it still tries direct first.
            _direct_retry_after = time.time() + 1800
        try:
            body = core.fetch_bytes(PROXY, timeout=45).decode("utf-8", errors="replace")
            rows = parse_markdown(body)
        except Exception as exc2:
            status[SOURCE] = {"ok": False, "count": 0, "url": DIRECT,
                              "error": ("%s | %s" % (error, str(exc2)[:90]))[:180]}
            return []

    try:
        known = core.existing_links(hours=hours)
    except Exception:
        known = set()

    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        link = row["link"]
        if link in seen or link in known:
            continue
        seen.add(link)
        article = to_article(core, row)
        if not article:
            continue
        try:
            stamp = datetime.fromisoformat(str(article.get("published_at")).replace("Z", "+00:00"))
        except ValueError:
            stamp = datetime.now(timezone.utc)
        if stamp < cutoff:
            continue
        output.append(article)
        if len(output) >= MAX_ITEMS:
            break

    status[SOURCE] = {"ok": True, "count": len(output), "scanned": len(rows),
                      "transport": transport, "url": DIRECT}
    # Logged so the CI transcript shows which transport ran: the runner can reach t.me
    # directly while this machine cannot, and that difference is invisible otherwise.
    import logging
    logging.info("Whale Alert: %d published from %d messages via %s",
                 len(output), len(rows), transport)
    if transport != "direct":
        status[SOURCE]["note"] = "proxy (%s)" % error
    return output