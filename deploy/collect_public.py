#!/usr/bin/env python3
"""Write the public JSON files that the hosted page reads.

Runs once (no server, no long-lived database) so a scheduler can call it.
Data is split by region so a visitor only downloads the tab they open.
The window is merged with the files already committed in the repo, so one
missed run does not leave a hole in the published list.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import category_rules  # noqa: E402
import live_news_dashboard as core  # noqa: E402  (path is set just above)
import page_build  # noqa: E402

DOCS = ROOT / "docs"
INDEX_FILE = DOCS / "index.json"
REGION_FILES = {core.GLOBAL_REGION: DOCS / "global.json", core.THAI_REGION: DOCS / "thai.json"}
KEEP_HOURS = 24
MAX_PER_REGION = 1500
# The page opens on 25 rows but "더 보기" can walk the whole window, so each region is
# published twice: a small recent file the page loads first, and the full file it only
# fetches once the reader actually pages past the recent set.
RECENT_PER_REGION = 300
PAGE_SIZE = 1000
FIELDS = (
    "title", "link", "summary", "published_at",
    "source", "source_type", "category", "categories", "priority",
)


SUMMARY_CHARS = 240


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {key: row.get(key) for key in FIELDS}
    out["priority"] = int(out.get("priority") or 3)
    # Every published row leaves here with a list, so the page never has to fall back to a single
    # value - and with names passed through the retirer, so a row merged forward from a file written
    # before a rename cannot put a name on screen that no pill offers any more.
    labels = category_rules.split_categories(out.get("categories"), out.get("category"))
    out["category"] = labels[0]
    out["categories"] = labels
    # The page clamps a summary to three lines (~220 chars) and trims it only when it
    # is longer than that, so shipping the full 800-char text wasted most of the file.
    # Trimming here cut global.json from 936KB to about half, with nothing lost on screen.
    summary = str(out.get("summary") or "")
    if len(summary) > SUMMARY_CHARS:
        out["summary"] = summary[:SUMMARY_CHARS].rstrip() + "…"
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
    # FinancialJuice variants are collapsed here too so the committed history stays clean.
    article["link"] = core.canonical_link(str(article.get("link") or ""))
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


def digest_of(articles: list[dict[str, Any]]) -> str:
    """A stamp that changes only when the published rows change.

    The page polls index.json with this value in hand and skips the regional download
    when it matches, so an idle poll costs about 200 bytes instead of the whole file.
    """
    hasher = hashlib.sha1()
    for article in articles:
        hasher.update(str(article.get("link")).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()[:16]


def recent_path(path: Path) -> Path:
    return path.with_name(path.stem + "-recent.json")


def write_json(path: Path, payload: dict[str, Any]) -> int:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))



def write_thai_page() -> int:
    """Regenerate the published pages and report the Thailand copy's size.

    Both public pages now come from page_build, so a markup or style change can never
    land on only one of them. (The old /thai/ copy was a find-and-replace of
    docs/index.html, and a CSS class rename once reached only one of the two.)
    """
    sizes = page_build.build_public()
    return sizes["docs/thai/index.html"]

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    core.init_db()
    core.collect_news()
    rows = fetch_window()
    DOCS.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    region_counts: dict[str, int] = {}
    regions: dict[str, dict[str, Any]] = {}
    total = 0
    for region, path in REGION_FILES.items():
        mine = [public_row(row) for row in rows if str(row.get("region") or core.GLOBAL_REGION) == region]
        # Trim again after the merge: rows kept from the previous file were written
        # before the cap existed and would otherwise keep their full-length summaries.
        articles = [public_row(row) for row in merge(read_articles(path), mine)]
        recent = articles[:RECENT_PER_REGION]
        write_json(path, {
            "region": region,
            "stamp": digest_of(articles),
            "count": len(articles),
            "articles": articles,
        })
        size = write_json(recent_path(path), {
            "region": region,
            "stamp": digest_of(recent),
            "count": len(recent),
            "articles": recent,
        })
        region_counts[region] = len(articles)
        regions[region] = {
            "count": len(articles),
            "stamp": digest_of(articles),
            "recent_count": len(recent),
            "recent_stamp": digest_of(recent),
        }
        total += len(articles)
        logging.info("%s: %d articles, recent %d (%d bytes)", path.name, len(articles), len(recent), size)

    write_json(INDEX_FILE, {
        "updated_at": now.isoformat(),
        "updated_at_ict": now.astimezone(core.ICT).strftime("%Y-%m-%d %H:%M"),
        "window_hours": KEEP_HOURS,
        "article_count": total,
        "region_counts": region_counts,
        "regions": regions,
    })
    logging.info("thai page: %d bytes", write_thai_page())
    logging.info("wrote %s: %d articles total", INDEX_FILE.name, total)
    print("total=%d %s" % (total, region_counts))


if __name__ == "__main__":
    main()
