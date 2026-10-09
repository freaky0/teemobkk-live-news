"""Middle East RSS collectors: IRNA, Mehr News, ISNA, Saudi Gazette, Al Jazeera.

Each feed is standard RSS 2.0. Parsed with xml.etree (no feedparser on the
collector host). Articles are built with core.make_article so categories,
priorities, dedupe and storage stay identical to the other collectors.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

FEEDS: tuple[tuple[str, str], ...] = (
    ("IRNA", "https://en.irna.ir/rss"),
    ("Mehr News", "https://en.mehrnews.com/rss"),
    ("ISNA", "https://en.isna.ir/rss"),
    ("Saudi Gazette", "https://saudigazette.com.sa/rssFeed/74"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
)

SOURCE_TYPE = "breaking"
MAX_ITEMS_PER_FEED = 25

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = unescape(text or "")
    text = _TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_pubdate(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_rss(payload: str) -> list[tuple[str, str, str, str]]:
    """Return (url, title, description, pubdate_raw) for each <item>."""
    out: list[tuple[str, str, str, str]] = []
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return out
    for item in root.iter("item"):
        link = item.findtext("link") or ""
        title = item.findtext("title") or ""
        desc = item.findtext("description") or ""
        pub = item.findtext("pubDate") or item.findtext("pubdate") or ""
        link = link.strip()
        if not link:
            continue
        out.append((link, _clean(title), _clean(desc), pub.strip()))
    return out


def fetch_into(status: dict[str, Any], core: Any = None) -> list[dict[str, Any]]:
    """Return fresh articles from all five feeds and record each source's status."""
    if core is None:  # imported late so the collector can call us during its own import
        from server import live_news_dashboard as core
    hours = int(getattr(core, "RETENTION_HOURS", 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        known = core.existing_links(hours=hours)
    except Exception:
        known = set()

    output: list[dict[str, Any]] = []
    for source, url in FEEDS:
        try:
            payload = core.fetch_bytes(url, timeout=30).decode("utf-8", errors="replace")
            items = parse_rss(payload)
        except Exception as exc:
            status[source] = {"ok": False, "count": 0, "url": url, "error": str(exc)[:180]}
            continue
        fresh: list[tuple[str, str, str, str]] = []
        for link, title, desc, pub_raw in items:
            if link in known or not title:
                continue
            stamp = _parse_pubdate(pub_raw)
            if stamp is not None and stamp < cutoff:
                continue
            fresh.append((link, title, desc, pub_raw))
        fresh = fresh[:MAX_ITEMS_PER_FEED]
        added = 0
        for link, title, desc, pub_raw in fresh:
            try:
                output.append(core.make_article(
                    title, link, desc, core.parse_date(pub_raw), source, SOURCE_TYPE))
                added += 1
            except Exception:
                continue
        status[source] = {"ok": True, "count": added, "scanned": len(items), "url": url}
    return output
