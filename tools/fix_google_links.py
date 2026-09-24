#!/usr/bin/env python3
"""Fill the Google News resolution cache, so the pages can link to the publisher.

Dry run by default - it reports what is stored and what it could resolve, and writes nothing:

    python tools/fix_google_links.py                 # report only
    python tools/fix_google_links.py --apply --limit 200

The cache table (`link_resolutions`) lives in the collector database. The article rows are
never modified: a Google News link is the primary key of the row it came in on, and the
operator's hide/pick lists and the push history all address a story by that key, so
rewriting it would fork one story into two and orphan the history. The pages read the cache
and send the reader to the publisher; the row keeps the link it was filed under.

Only URLs Google itself returns are stored - nothing is derived from a title, a source name
or the article id, and an answer pointing back at a Google host is refused.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import google_news  # noqa: E402


def aggregator_links(connection: sqlite3.Connection, limit: int | None = None) -> list[str]:
    """Stored links that still point at Google News, newest first."""
    sql = ("SELECT link FROM articles WHERE link LIKE '%news.google.com%' "
           "ORDER BY published_at DESC")
    rows = connection.execute(sql).fetchall()
    links = [str(row[0]) for row in rows]
    return links[:limit] if limit else links


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "news.db"))
    parser.add_argument("--apply", action="store_true", help="resolve and store (default: report only)")
    parser.add_argument("--limit", type=int, default=200, help="how many links to try in this run")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    connection = sqlite3.connect(args.db, timeout=15)
    try:
        google_news.ensure_table(connection)
        cached = google_news.load(connection)
        stored = aggregator_links(connection)
        pending = [link for link in stored if link not in cached]
        print("database      %s" % args.db)
        print("aggregator    %d stored links" % len(stored))
        print("cached        %d resolved" % len(cached))
        print("pending       %d waiting" % len(pending))
        if not args.apply:
            print("dry run: nothing written. add --apply to resolve up to %d links." % args.limit)
            return
        if not pending:
            return
        target = pending[:args.limit]
        print("resolving     %d links with %d workers (started %s UTC)"
              % (len(target), args.workers, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        found = google_news.resolve_many(target, workers=args.workers)
        written = google_news.remember(connection, found)
        failed = len(target) - len(found)
        print("resolved      %d" % len(found))
        print("stored        %d rows in %s" % (written, google_news.TABLE))
        print("unresolved    %d (Google did not answer with a publisher URL; retried next run)" % failed)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
