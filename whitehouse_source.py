"""White House feeds as an official source.

X and Truth Social have no free read path, so the closest first-hand substitute for
"what the administration just said" is the White House's own RSS: announcements,
proclamations, executive orders and fact sheets, posted the moment they are
published - ahead of any wire story about them.

Both feeds are published by whitehouse.gov for syndication: no key, no login, no
paywall, and their terms page does not restrict feed use.

Parsing is delegated to the collector's own `parse_rss`, so categories, assets,
priorities, windows and storage stay identical to every other RSS source.
"""
from __future__ import annotations

from typing import Any

# "White House" mirrors /news/, which also carries what /presidential-actions/ posts,
# so the two feeds overlap. dedupe() in the collector drops the repeats by link.
FEEDS = (
    ("White House", "https://www.whitehouse.gov/news/feed/"),
    ("White House Actions", "https://www.whitehouse.gov/presidential-actions/feed/"),
)
SOURCE_TYPE = "official"


def fetch_into(status: dict[str, Any], core: Any = None) -> list[dict[str, Any]]:
    """Return articles for every feed and record per-feed status."""
    if core is None:  # imported late so the collector can call us during its own import
        import live_news_dashboard as core
    articles: list[dict[str, Any]] = []
    for name, url in FEEDS:
        try:
            payload = core.fetch_bytes(url, timeout=25)
            items = core.parse_rss(payload, name, SOURCE_TYPE)
        except Exception as exc:  # one dead feed must never break the cycle
            status[name] = {"ok": False, "error": str(exc)[:140], "count": 0}
            continue
        status[name] = {"ok": True, "count": len(items)}
        articles.extend(items)
    return articles
