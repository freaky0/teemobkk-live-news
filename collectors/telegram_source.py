"""Telegram channels as sources: market headlines and on-chain whale alerts.

whale-alert.io is a paid dashboard and the X API has no free read path, but both
publish publicly readable channels:

    WalterBloomberg   DeItaone-style market squawk (Fed speakers, data, geopolitics)
    whale_alert_io    Whale Alert's own alerts, each with a whale-alert.io transaction link

The channel web preview (t.me/s/<handle>) is a static page, one message per block with
`data-post="<handle>/<id>"` and an exact `<time datetime>` stamp, so no account, key or
client is involved.

Transport: this machine cannot reach t.me (Thailand blocks it) and the CI runner does
not get usable messages either, so the request goes straight to the r.jina.ai reader
with `X-Return-Format: html`. That returns the original markup - ids and exact stamps
included - instead of markdown, which carried only a posting date. A direct attempt is
still made first in case a future host can reach the site, and it is skipped for half
an hour after a failure so no cycle waits on a connect timeout.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

SOURCE_TYPE = "social"
MAX_ITEMS = 30
TITLE_MAX = 180
DIRECT_TIMEOUT = 15
PROXY_TIMEOUT = 50
PROXY = "https://r.jina.ai/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Whale alerts smaller than this, and routine treasury issuance below the second figure,
# are dropped: the channel posts dozens a day and the feed does not need all of them.
MIN_USD = 50_000_000
MINT_MIN_USD = 500_000_000

CHANNELS = (
    {"name": "Walter Bloomberg", "handle": "WalterBloomberg", "kind": "headline"},
    {"name": "Whale Alert", "handle": "whale_alert_io", "kind": "whale"},
)

_direct_failures = 0
_direct_retry_after = 0.0

ALERT_USD = re.compile(r"\(([\d,]+)\s*USD\)", re.I)
DETAILS = re.compile(r"https://whale-alert\.io/transaction/[^\s)\"'<]+")
ROUTINE = re.compile(r"(minted|burned) at .*treasury", re.I)


def clean(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Emoji runs (🚨🔥💵 …) are decoration; the words carry the meaning.
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", " ", text)
    text = re.sub(r"\(\s*@\w+\s*\)", " ", text)   # trailing channel credit
    text = re.sub(r"\*+", "", text)               # urgent-headline asterisks
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def money(text: str) -> int:
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else 0


def parse_html(html: str) -> list[dict[str, Any]]:
    """Every message on the page: id, exact stamp, text."""
    out: list[dict[str, Any]] = []
    pattern = re.compile(r'data-post="([^"]+)"(.*?)(?=data-post="|</section>|$)', re.S)
    for match in pattern.finditer(html):
        post, block = match.group(1), match.group(2)
        text = re.search(r'js-message_text[^>]*>(.*?)</div>', block, re.S)
        when = re.search(r"datetime=\"([^\"]+)\"", block)
        if not post or not text:
            continue
        body = clean(text.group(1))
        if not body:
            continue
        handle, _, ident = post.partition("/")
        out.append({
            "handle": handle,
            "id": ident,
            "text": body,
            "when": when.group(1) if when else "",
            "link": "https://t.me/%s/%s" % (handle, ident) if ident else "",
        })
    return out


def proxy_fetch(url: str) -> bytes:
    import urllib.request

    request = urllib.request.Request(
        PROXY + url,
        headers={"User-Agent": UA, "X-Return-Format": "html", "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=PROXY_TIMEOUT) as response:
        return response.read()


def fetch_html(core: Any, handle: str) -> tuple[str, str, str]:
    """Return (html, transport, error). Direct first, then the reader proxy."""
    global _direct_failures, _direct_retry_after
    url = "https://t.me/s/%s" % handle
    error = ""
    if time.time() >= _direct_retry_after:
        try:
            html = core.fetch_bytes(url, timeout=DIRECT_TIMEOUT).decode("utf-8", errors="replace")
            if parse_html(html):
                _direct_failures = 0
                return html, "direct", ""
            error = "direct page held no messages"
        except Exception as exc:
            error = str(exc)[:80]
        _direct_failures += 1
        _direct_retry_after = time.time() + 1800
    try:
        return proxy_fetch(url).decode("utf-8", errors="replace"), "proxy", error
    except Exception as exc:
        return "", "none", ("%s | %s" % (error, str(exc)[:80]))[:170]


def to_article(core: Any, channel: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    title = row["text"]
    if not title:
        return None
    if channel["kind"] == "whale":
        usd = ALERT_USD.search(title)
        amount = money(usd.group(1)) if usd else 0
        if amount and amount < MIN_USD:
            return None
        if ROUTINE.search(title) and amount < MINT_MIN_USD:
            return None
        details = DETAILS.search(row["text"])
        link = details.group(0) if details else row["link"]
        summary = title
    else:
        link = row["link"]
        summary = ""
    title = title[:TITLE_MAX] + ("…" if len(title) > TITLE_MAX else "")
    when = row.get("when") or ""
    if not when:
        when = datetime.now(timezone.utc).isoformat()
    return core.make_article(title, link, summary, core.parse_date(when),
                             channel["name"], SOURCE_TYPE)


def fetch_into(status: dict[str, Any], core: Any = None) -> list[dict[str, Any]]:
    if core is None:  # imported late so the collector can call us during its own import
        import live_news_dashboard as core
    hours = int(getattr(core, "RETENTION_HOURS", 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        known = core.existing_links(hours=hours)
    except Exception:
        known = set()

    output: list[dict[str, Any]] = []
    for channel in CHANNELS:
        html, transport, error = fetch_html(core, channel["handle"])
        if not html:
            status[channel["name"]] = {"ok": False, "count": 0, "url":
                                       "https://t.me/s/" + channel["handle"], "error": error}
            continue
        rows = parse_html(html)
        published = 0
        for row in rows:
            link = row["link"]
            if channel["kind"] == "whale":
                details = DETAILS.search(row["text"])
                if details:
                    link = details.group(0)
            if not link or link in known:
                continue
            article = to_article(core, channel, row)
            if not article:
                continue
            try:
                stamp = datetime.fromisoformat(str(article.get("published_at")).replace("Z", "+00:00"))
            except ValueError:
                stamp = datetime.now(timezone.utc)
            if stamp < cutoff:
                continue
            known.add(link)
            output.append(article)
            published += 1
            if published >= MAX_ITEMS:
                break
        status[channel["name"]] = {"ok": True, "count": published, "scanned": len(rows),
                                   "transport": transport,
                                   "url": "https://t.me/s/" + channel["handle"]}
        if transport == "proxy" and error:
            status[channel["name"]]["note"] = "proxy (%s)" % error
    return output
