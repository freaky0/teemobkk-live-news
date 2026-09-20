#!/usr/bin/env python3
"""Check whether candidate feeds are actually usable, before adding them to the collector.

Alive means: the body parses, it holds items, and the newest item is recent. A feed can answer 200
with a bot-block page or with a fully-formed cache from months ago, so the status code alone says
nothing (the same rule the collector's own health line follows).

    python tools/probe_sources.py <url> [<url> ...]
    python tools/probe_sources.py --listed        # probe the sources already in the collector
"""
from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import live_news_dashboard as core  # noqa: E402


def newest_age_days(items):
    stamps = [a.get("published_at") for a in items if a.get("published_at")]
    if not stamps:
        return None
    newest = max(stamps)
    try:
        moment = datetime.datetime.fromisoformat(newest.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return (datetime.datetime.now(datetime.timezone.utc) - moment).total_seconds() / 86400


def probe(source, url, kind="crypto", region="글로벌"):
    try:
        payload = core.fetch_bytes(url, timeout=15)
    except Exception as error:
        return source, url, "unreachable", str(error)[:60], None, None
    try:
        items = core.parse_rss(payload, source, kind, region)
    except Exception as error:
        return source, url, "unparsable", str(error)[:60], 0, None
    age = newest_age_days(items)
    return source, url, "ok" if items else "empty", "", len(items), age


def listed():
    pairs = [(name, url) for name, _kind, url in core.RSS_SOURCES]
    pairs += [(name, url) for name, _kind, url in core.THAI_RSS_SOURCES]
    return pairs


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--listed":
        jobs = listed()
    else:
        jobs = [(url.split("//", 1)[-1].split("/", 1)[0], url) for url in args]
    ok = 0
    for source, url in jobs:
        name, target, state, note, count, age = probe(source, url)
        when = "-" if age is None else ("%.2f일 전" % age)
        print("  %-9s %-34s %-11s %s  항목 %s  최신 %s"
              % (state, name[:34], note, url[:58], "-" if count is None else count, when))
        if state == "ok":
            ok += 1
    print("\n  %d/%d 살아 있음" % (ok, len(jobs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
