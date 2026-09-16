"""Bluesky source: posts from official, domain-verified accounts.

X and Truth Social have no free read path. Measured on this host: Nitter mirrors
and RSS bridges answer 451/403/404 or time out, and Truth Social answers 403 from
Cloudflare. Bluesky's public API needs no key, so it is the social source that can
actually be collected.

Handles use custom domains, which only the domain owner can set, so they are
self-verifying. Posts are turned into the same article shape the rest of the
collector uses (core.make_article), so dedupe, windows and storage are unchanged.
"""
from __future__ import annotations

import json
from typing import Any

HANDLES = (
    # official policy and institutions
    "federalreserve.gov",
    "ecb.europa.eu",
    # wire services - high volume, kept for coverage; the source chip filters them
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    # crypto
    "coindesk.com",
    "decrypt.co",
    "protos.com",
    # markets and business, chosen for low daily volume so the feed does not drown
    "axios.com",
    "theinformation.com",
    "marketwatch.com",
    "barrons.com",
)
FEED_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=%s&limit=15&filter=posts_no_replies"
WEB_URL = "https://bsky.app/profile/%s/post/%s"
SOURCE = "Bluesky"
SOURCE_TYPE = "social"
TITLE_MAX = 140
REPOST = "#reasonRepost"


def post_link(handle: str, uri: str) -> str:
    return WEB_URL % (handle, str(uri).rsplit("/", 1)[-1])


def title_of(text: str) -> str:
    first = (text or "").strip().splitlines()[0] if text else ""
    return (first[:TITLE_MAX] + "…") if len(first) > TITLE_MAX else first


def fetch_into(status: dict[str, Any], core: Any = None, region: str | None = None) -> list[dict[str, Any]]:
    """Return articles for every handle and record per-account status."""
    if core is None:  # imported late so the collector can call us during its own import
        import live_news_dashboard as core
    region = region or core.GLOBAL_REGION
    articles: list[dict[str, Any]] = []
    for handle in HANDLES:
        label = "%s · %s" % (SOURCE, handle)
        try:
            payload = json.loads(core.fetch_bytes(FEED_URL % handle))
            feed = payload.get("feed") or []
        except Exception as exc:  # one dead account must not stop the rest
            status[label] = {"ok": False, "count": 0, "error": str(exc)[:160]}
            continue
        kept = 0
        for entry in feed:
            if REPOST in str((entry.get("reason") or {}).get("$type", "")):
                continue
            post = entry.get("post") or {}
            record = post.get("record") or {}
            text = str(record.get("text") or "").strip()
            uri = str(post.get("uri") or "")
            created = str(record.get("createdAt") or "")
            if not text or not uri or record.get("reply"):
                continue
            articles.append(core.make_article(
                title_of(text), post_link(handle, uri), text, created, label, SOURCE_TYPE, region))
            kept += 1
        status[label] = {"ok": True, "count": kept, "url": FEED_URL % handle}
    return articles
