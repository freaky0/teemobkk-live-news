"""SBHNews "open news": posts they aggregate from X, Instagram, Al Jazeera and similar.

SBHNews republishes social posts with a Korean headline and summary under the label
"오픈 뉴스" (badge `오픈 뉴스`, source line `X (formerly Twitter)`). The homepage and the
/news listing ship the rows inside the Next.js flight payload as flat JSON objects:

    {"title": "...", "source": "user-news", "sourceUrl": "https://x.com/<user>/status/<id>",
     "sourceName": "X (formerly Twitter)", "isUserNews": true, "publishedAt": "...", ...}

so the original post URL is available without touching X itself - which matters because
X has no free read path (see the hand-off note). robots.txt allows these pages
(`User-agent: * / Allow: /`); only /api/ is disallowed, and that is not used here.

The row's link points at the *original post*, which is what "X (formerly Twitter) 원문
보기" means on their card. Volume is modest - roughly a dozen social rows per page load,
usually one or two of them from X - so this supplements the article feed rather than
replacing it. Titles and summaries are their Korean translations; the source chip keeps
provenance visible.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

PAGES = (
    "https://www.sbhnews.com/",
    "https://www.sbhnews.com/news",
)
SOURCE = "오픈 소스"
SOURCE_TYPE = "social"
MAX_ITEMS = 20
TITLE_MAX = 160


def payload(html: str) -> str:
    """Join the RSC chunks and undo one level of escaping so the JSON is readable."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\s*\]\)', html)
    joined = "".join(chunks)
    return joined.replace('\\"', '"').replace('\\n', ' ').replace('\\\\', '\\')


def social_rows(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in re.finditer(r'\{[^{}]*"sourceUrl"[^{}]*\}', payload(html)):
        try:
            row = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("title") and row.get("sourceUrl"):
            out.append(row)
    return out


def unescape(text: str) -> str:
    for old, new in (("&apos;", "'"), ("&#39;", "'"), ("&quot;", '"'), ("&amp;", "&"),
                     ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(old, new)
    return text


def to_article(core: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    link = str(row.get("sourceUrl") or "").strip()
    title = unescape(str(row.get("title") or "").strip())
    if not link or not title:
        return None
    title = re.sub(r"\s+", " ", title)
    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX] + "…"
    summary = re.sub(r"\s+", " ", unescape(str(row.get("summary") or ""))).strip()
    where = unescape(str(row.get("sourceName") or "").strip()) or "social post"
    location = unescape(str(row.get("locationName") or "").strip())
    note = "출처 %s" % where
    if location:
        note += " · %s" % location
    summary = (summary + " (" + note + ")") if summary else note
    when = str(row.get("publishedAt") or "")
    article = core.make_article(title, link, summary, core.parse_date(when), SOURCE, SOURCE_TYPE)
    return article


def fetch_into(status: dict[str, Any], core: Any = None) -> list[dict[str, Any]]:
    if core is None:  # imported late so the collector can call us during its own import
        import live_news_dashboard as core
    hours = int(getattr(core, "RETENTION_HOURS", 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        known = core.existing_links(hours=hours)
    except Exception:
        known = set()

    rows: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    scanned = 0
    for page in PAGES:
        try:
            html = core.fetch_bytes(page, timeout=25).decode("utf-8", errors="replace")
        except Exception as exc:  # one dead page must not stop the other
            errors.append("%s: %s" % (page, str(exc)[:80]))
            continue
        found = social_rows(html)
        scanned += len(found)
        for row in found:
            link = str(row.get("sourceUrl") or "")
            when = str(row.get("publishedAt") or "")
            if link and link not in rows:
                rows[link] = row

    output: list[dict[str, Any]] = []
    for link, row in sorted(rows.items(), key=lambda kv: str(kv[1].get("publishedAt") or ""), reverse=True):
        if str(row.get("publishedAt") or "") < cutoff.isoformat()[:19]:
            continue
        if link in known:
            continue
        article = to_article(core, row)
        if article:
            output.append(article)
        if len(output) >= MAX_ITEMS:
            break

    status[SOURCE] = {
        "ok": not errors or bool(rows),
        "count": len(output),
        "scanned": scanned,
        "url": PAGES[0],
    }
    if errors and not rows:
        status[SOURCE]["error"] = " | ".join(errors)[:180]
    return output