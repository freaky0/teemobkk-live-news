#!/usr/bin/env python3
"""Write the public JSON files that the hosted page reads.

Runs once (no server, no long-lived database) so a scheduler can call it.
Data is split by region so a visitor only downloads the tab they open.
The window is merged with the files already committed in the repo, so one
missed run does not leave a hole in the published list.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import live_news_dashboard as core  # noqa: E402  (path is set just above)

DOCS = ROOT / "docs"
INDEX_FILE = DOCS / "index.json"
REGION_FILES = {core.GLOBAL_REGION: DOCS / "global.json", core.THAI_REGION: DOCS / "thai.json"}
KEEP_HOURS = 24
MAX_PER_REGION = 1500
PAGE_SIZE = 1000
FIELDS = (
    "title", "link", "summary", "published_at", "collected_at",
    "source", "source_type", "region", "category", "asset", "priority",
)


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {key: row.get(key) for key in FIELDS}
    out["priority"] = int(out.get("priority") or 3)
    return out


def read_articles(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("articles")
    return items if isinstance(items, list) else []


def fetch_window() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while len(rows) < MAX_PER_REGION * 2:
        batch, _total, _regions = core.query_articles(hours=core.RETENTION_HOURS, limit=PAGE_SIZE, offset=offset)
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows



def normalize_link(article: dict[str, Any]) -> dict[str, Any]:
    """Fix stock items stored before the feed-specific path existed.

    CoinNess sends no link for either feed, so older stock rows were written with
    the breaking-news path. Keep this guard so the committed history stays clean.
    """
    if article.get("source") == "CoinNess Stock":
        prefix = "https://coinness.com/news/"
        link = str(article.get("link") or "")
        if link.startswith(prefix):
            ident = link[len(prefix):].split("/")[0].split("?")[0]
            if ident.isdigit():
                article["link"] = "https://coinness.com/stock-news/" + ident + "/quote"
    return article


def merge(previous: list[dict[str, Any]], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=KEEP_HOURS)).isoformat()
    by_link: dict[str, dict[str, Any]] = {}
    for article in [normalize_link(a) for a in list(previous)] + list(fresh):
        link = str(article.get("link") or "")
        published = str(article.get("published_at") or "")
        if not link or published < cutoff:
            continue
        by_link[link] = article
    ordered = sorted(
        by_link.values(),
        key=lambda item: (str(item.get("published_at") or ""), int(item.get("priority") or 0)),
        reverse=True,
    )
    return ordered[:MAX_PER_REGION]


def write_json(path: Path, payload: dict[str, Any]) -> int:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))



THAI_DIR = DOCS / "thai"
PAGE_FILE = DOCS / "index.html"
FAVICON_FIXES = (
    ('href="favicon.ico"', 'href="../favicon.ico"'),
    ('href="favicon-32.png"', 'href="../favicon-32.png"'),
    ('href="favicon-16.png"', 'href="../favicon-16.png"'),
    ('href="apple-touch-icon.png"', 'href="../apple-touch-icon.png"'),
)


def write_thai_page() -> int:
    """Publish the same page one level deeper so /thai/ opens the Thailand tab.

    The copy is generated, never hand edited: index.html stays the only source.
    The page itself detects the /thai/ path and switches both the tab and the
    directory it reads data from, so only the icon paths need rewriting here.
    """
    html = PAGE_FILE.read_text(encoding="utf-8")
    for old, new in FAVICON_FIXES:
        if html.count(old) != 1:
            raise RuntimeError("favicon anchor not found exactly once: " + old)
        html = html.replace(old, new, 1)
    THAI_DIR.mkdir(parents=True, exist_ok=True)
    target = THAI_DIR / "index.html"
    target.write_text(html, encoding="utf-8", newline="\n")
    return len(html.encode("utf-8"))

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    core.init_db()
    core.collect_news()
    fresh = [public_row(row) for row in fetch_window()]
    DOCS.mkdir(parents=True, exist_ok=True)

    region_counts: dict[str, int] = {}
    total = 0
    for region, path in REGION_FILES.items():
        mine = [row for row in fresh if str(row.get("region") or core.GLOBAL_REGION) == region]
        articles = merge(read_articles(path), mine)
        size = write_json(path, {"region": region, "articles": articles})
        region_counts[region] = len(articles)
        total += len(articles)
        logging.info("%s: %d articles (%d bytes)", path.name, len(articles), size)

    now = datetime.now(timezone.utc)
    write_json(INDEX_FILE, {
        "updated_at": now.isoformat(),
        "updated_at_ict": now.astimezone(core.ICT).strftime("%Y-%m-%d %H:%M"),
        "window_hours": KEEP_HOURS,
        "article_count": total,
        "region_counts": region_counts,
    })
    logging.info("thai page: %d bytes", write_thai_page())
    logging.info("wrote %s: %d articles total", INDEX_FILE.name, total)
    print("total=%d %s" % (total, region_counts))


if __name__ == "__main__":
    main()
