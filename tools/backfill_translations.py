#!/usr/bin/env python3
"""Gradually backfill Korean titles and summaries in the existing database.

Run: python tools/backfill_translations.py --batch-size 20 --throttle 1.0
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import live_news_dashboard as core  # noqa: E402
import translate_ko  # noqa: E402


def pending_links(after_link: str, limit: int) -> list[str]:
    with core.DB_LOCK:
        connection = core.db_connect()
        try:
            return [str(row[0]) for row in connection.execute(
                "SELECT link FROM articles WHERE title_ko IS NULL AND link > ? "
                "ORDER BY link ASC LIMIT ?", (after_link, limit))]
        finally:
            connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--throttle", type=float, default=1.0,
                        help="seconds between translated articles (default: 1)")
    args = parser.parse_args()
    batch_size = max(1, min(args.batch_size, translate_ko.MAX_BATCH))
    throttle = max(0.0, args.throttle)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    core.init_db()

    after_link = ""
    scanned = translated = 0
    while True:
        links = pending_links(after_link, batch_size)
        if not links:
            break
        translated += translate_ko.translate_pending(
            limit=len(links), throttle_seconds=throttle, after_link=after_link)
        scanned += len(links)
        after_link = links[-1]
        logging.info("Backfill scanned=%d translated=%d", scanned, translated)

    remaining = pending_links("", 1)
    logging.info("Backfill finished: scanned=%d translated=%d pending=%s",
                 scanned, translated, "yes" if remaining else "no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
