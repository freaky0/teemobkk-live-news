"""SBHNews articles, read from the site's news sitemap instead of the full one.

The collector used to pull https://www.sbhnews.com/sitemap.xml - 3.5 MB of every
article URL ever published - keep the 223 newest, and then open article pages just to
learn each one's date. The site also declares a Google-News style news sitemap:

    https://www.sbhnews.com/news-sitemap.xml   223 KB, 6.4% of the full sitemap

It carries the last ~48 hours with <news:title> and <news:publication_date>, so the
time window can be applied *before* any article page is fetched, the date comes from
the feed rather than a URL slug, and a page that fails to load can still be published
from the sitemap's own title. robots.txt allows this path (`User-agent: * / Allow: /`)
and lists the sitemap itself; /api/ is disallowed and is not used.

Page parsing and article construction are delegated to the collector, so categories,
priorities, dedupe and storage stay identical to the previous path.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

NEWS_SITEMAP = "https://www.sbhnews.com/news-sitemap.xml"
SOURCE = "SBHNews"
SOURCE_TYPE = "breaking"
MAX_PAGES = 12
WORKERS = 6


def entries(payload: str) -> list[tuple[str, str, str]]:
    """Return (url, title, publication time) for each <url> block in the sitemap."""
    out: list[tuple[str, str, str]] = []
    for block in re.findall(r"<url>(.*?)</url>", payload, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not loc:
            continue
        url = loc.group(1).strip()
        if "/news/" not in url:
            continue
        title = re.search(r"<news:title>(.*?)</news:title>", block, re.S)
        when = re.search(r"<news:publication_date>([^<]+)</news:publication_date>", block)
        out.append((
            url,
            unescape(title.group(1).strip()) if title else "",
            when.group(1).strip() if when else "",
        ))
    return out


def unescape(text: str) -> str:
    for old, new in (("&apos;", "'"), ("&#39;", "'"), ("&quot;", '"'), ("&amp;", "&"),
                     ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(old, new)
    return text


def recent(payload: str, hours: int) -> list[tuple[str, str, str]]:
    """Newest first, limited to the retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    keep: list[tuple[datetime, str, str, str]] = []
    for url, title, when in entries(payload):
        try:
            stamp = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            continue
        if stamp >= cutoff:
            keep.append((stamp, url, title, when))
    keep.sort(reverse=True)
    return [(url, title, when) for _, url, title, when in keep]


def fetch_into(status: dict[str, Any], core: Any = None) -> list[dict[str, Any]]:
    """Return fresh articles and record this source's status."""
    if core is None:  # imported late so the collector can call us during its own import
        import live_news_dashboard as core
    hours = int(getattr(core, "RETENTION_HOURS", 24))
    try:
        payload = core.fetch_bytes(NEWS_SITEMAP, timeout=30).decode("utf-8", errors="replace")
        items = recent(payload, hours)
    except Exception as exc:
        status[SOURCE] = {"ok": False, "count": 0, "url": NEWS_SITEMAP, "error": str(exc)[:180]}
        return []
    try:
        known = core.existing_links(hours=hours)
    except Exception:
        known = set()
    pending = [item for item in items if item[0] not in known][:MAX_PAGES]

    def load(item: tuple[str, str, str]) -> tuple[str, str, str, str]:
        url, title, when = item
        try:
            headline, description, published = core._sbh_parse_page(core.fetch_bytes(url, timeout=12))
        except Exception:
            headline, description, published = "", "", ""
        return url, (headline or title), description, (published or when)

    output: list[dict[str, Any]] = []
    if pending:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for url, headline, description, published in pool.map(load, pending):
                if headline:
                    output.append(core.make_article(
                        headline, url, description, core.parse_date(published), SOURCE, SOURCE_TYPE))
    status[SOURCE] = {
        "ok": True,
        "count": len(output),
        "scanned": len(items),
        "pending": len(pending),
        "url": NEWS_SITEMAP,
    }
    return output