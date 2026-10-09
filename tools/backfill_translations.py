#!/usr/bin/env python3
"""Backfill Korean titles and summaries, newest incomplete articles first.

Example:
  TG_TRANSLATE_PROVIDER=openai-codex python tools/backfill_translations.py \
    --db /opt/teemo-live-news/news.db --batch-size 20 --throttle 1.0
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import live_news_dashboard as core  # noqa: E402
from pipeline import translate_ko  # noqa: E402


PENDING_SQL = (
    "((COALESCE(TRIM(title), '') <> '' AND COALESCE(TRIM(title_ko), '') = '') "
    "OR (COALESCE(TRIM(summary), '') <> '' AND COALESCE(TRIM(summary_ko), '') = ''))"
)


def _connect() -> sqlite3.Connection:
    with core.DB_LOCK:
        return core.db_connect()


def pending_count() -> int:
    connection = _connect()
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM articles WHERE {PENDING_SQL}").fetchone()
        return int(row[0])
    finally:
        connection.close()


def pending_batch(limit: int) -> list[tuple[str, str]]:
    """Return the newest incomplete rows as (published_at, link)."""
    if limit <= 0:
        return []
    connection = _connect()
    try:
        rows = connection.execute(
            f"SELECT COALESCE(published_at, ''), link FROM articles "
            f"WHERE {PENDING_SQL} "
            "ORDER BY COALESCE(published_at, '') DESC, link DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(str(row[0] or ""), str(row[1])) for row in rows]
    finally:
        connection.close()


def validate_database(db_path: Path) -> Path:
    """Require an existing SQLite database with the expected article columns."""
    try:
        resolved = db_path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"database does not exist: {db_path}") from exc
    if not resolved.is_file():
        raise ValueError(f"database is not a file: {resolved}")

    uri = f"{resolved.as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=10) as connection:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            if "articles" not in tables:
                raise ValueError(f"database has no articles table: {resolved}")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    except sqlite3.Error as exc:
        raise ValueError(f"cannot read database {resolved}: {exc}") from exc

    required = {"link", "title", "summary", "published_at", "title_ko", "summary_ko"}
    missing = sorted(required - columns)
    if missing:
        raise ValueError(f"database is missing required articles columns: {', '.join(missing)}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True,
                        help="existing SQLite database to update; no repo-local default")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--max-rows", type=int, default=0,
                        help="stop after this many selected rows; 0 means all pending rows")
    parser.add_argument("--throttle", type=float, default=1.0,
                        help="seconds between translated articles (default: 1)")
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.max_rows < 0:
        parser.error("--max-rows cannot be negative")
    if args.throttle < 0:
        parser.error("--throttle cannot be negative")

    try:
        db_path = validate_database(args.db)
    except ValueError as exc:
        parser.error(str(exc))

    batch_size = min(args.batch_size, translate_ko.MAX_BATCH)
    throttle = args.throttle
    core.DB_FILE = str(db_path)
    # Force Codex-only behavior regardless of the caller's environment.
    os.environ["TG_TRANSLATE_PROVIDER"] = "openai-codex"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    initial_pending = pending_count()
    logging.info(
        "Backfill started: db=%s provider=openai-codex model=gpt-6-luna pending=%d "
        "batch_size=%d max_rows=%d throttle=%.2fs",
        db_path, initial_pending, batch_size, args.max_rows, throttle,
    )

    scanned = translated = 0
    started_at = time.monotonic()
    while args.max_rows == 0 or scanned < args.max_rows:
        next_limit = batch_size
        if args.max_rows:
            next_limit = min(next_limit, args.max_rows - scanned)
        batch = pending_batch(next_limit)
        if not batch:
            break

        links = [link for _, link in batch]
        pending_before = pending_count()
        try:
            changed = translate_ko.translate_pending(
                limit=len(links),
                links=links,
                throttle_seconds=throttle,
            )
        except Exception:
            logging.exception(
                "Backfill halted: Codex translation failed; no model/API fallback is allowed. "
                "scanned=%d translated=%d pending=%d",
                scanned, translated, pending_count(),
            )
            return 1

        scanned += len(batch)
        translated += changed
        pending_after = pending_count()
        elapsed = time.monotonic() - started_at
        logging.info(
            "Backfill progress: scanned=%d translated=%d pending=%d elapsed=%.1fs "
            "oldest_batch=%s newest_batch=%s",
            scanned, translated, pending_after, elapsed,
            batch[-1][0] or "unknown", batch[0][0] or "unknown",
        )
        if changed == 0 and pending_after >= pending_before:
            logging.error("Backfill made no progress; stopping to avoid an infinite loop.")
            return 1

    remaining = pending_count()
    elapsed = time.monotonic() - started_at
    status = "row limit reached" if args.max_rows and scanned >= args.max_rows and remaining else "complete"
    logging.info(
        "Backfill %s: scanned=%d translated=%d pending=%d elapsed=%.1fs",
        status, scanned, translated, remaining, elapsed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
