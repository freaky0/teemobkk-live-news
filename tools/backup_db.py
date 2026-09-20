#!/usr/bin/env python3
"""Back up the collector's database, and prune old copies.

The database is one file, which makes this short: the sqlite3 backup API copies a live database
safely, including anything still in the write-ahead log. Copying the file with `cp` while the
collector is running is the thing this avoids - it can capture a database whose WAL was not folded
in, which restores as a database missing its newest rows (or as a corrupt one).

    python tools/backup_db.py --keep 7                 # default: 7 copies, beside the database
    python tools/backup_db.py --dir /opt/teemo-backup --keep 7
    python tools/backup_db.py --verify <copy.db>       # check a copy the way a restore would
"""
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEEP = 7


def backup(source: Path, target: Path) -> int:
    """Write a consistent copy of a possibly-live database. Returns the copy's size in bytes."""
    source_uri = "file:%s?mode=ro" % source.as_posix()
    origin = sqlite3.connect(source_uri, uri=True)
    try:
        copy = sqlite3.connect(str(target))
        try:
            origin.backup(copy)
        finally:
            copy.close()
    finally:
        origin.close()
    return target.stat().st_size


def verify(path: Path) -> tuple[bool, str]:
    """What a restore would ask: does it open, is it intact, does it hold rows, can the app read it."""
    if not path.is_file():
        return False, "no file at %s" % (path or "(없음)")
    connection = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
    try:
        state = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if state != "ok":
            return False, "integrity_check: %s" % state
        rows = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        newest = connection.execute("SELECT MAX(published_at) FROM articles").fetchone()[0]
        tables = sorted(row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"))
    except sqlite3.Error as error:
        return False, "unreadable: %s" % error
    finally:
        connection.close()
    if not rows:
        return False, "opens and is intact but holds no articles"
    detail = "%d articles, newest %s, tables: %s" % (rows, newest, ", ".join(tables))

    # The copy must also satisfy the application, not just sqlite. A schema the app cannot query
    # - a missing column, a renamed one - passes integrity_check and still restores into a site
    # that answers nothing, and that is the failure a rehearsal exists to catch. The window is
    # widened past the retention period because a copy is often checked days after it was made.
    sys.path.insert(0, str(ROOT))
    import live_news_dashboard as core
    core.DB_FILE = path
    articles, total, _counts = core.query_articles(hours=24 * 90, limit=3)
    if not articles:
        return False, "%s, but the application reads 0 rows from it" % detail
    return True, "%s | app query: %d of %d rows, newest from %s" % (
        detail, len(articles), total, articles[0].get("source", "?"))


def prune(directory: Path, keep: int) -> list[Path]:
    copies = sorted(directory.glob("news-*.db"), key=lambda p: p.name)
    removed = []
    for old in copies[:-keep] if keep > 0 else copies:
        old.unlink()
        removed.append(old)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "news.db"))
    parser.add_argument("--dir", default="", help="where the copies go (default: beside the database)")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument("--verify", default=None,
                        help="check an existing copy and exit (a path is required)")
    args = parser.parse_args()

    # An empty --verify used to fall through to the backup branch, which wrote a copy into the
    # repository root. A missing path is a usage error, not an instruction to take a backup.
    if args.verify is not None:
        ok, detail = verify(Path(args.verify))
        print("  %s %s" % ("OK " if ok else "BAD", detail))
        return 0 if ok else 1

    source = Path(args.db)
    if not source.exists():
        print("no database at %s" % source)
        return 1
    directory = Path(args.dir) if args.dir else source.parent
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = directory / ("news-%s.db" % stamp)
    size = backup(source, target)
    ok, detail = verify(target)
    print("  backup %s (%.1f MB)" % (target, size / 1048576))
    print("  %s %s" % ("OK " if ok else "BAD", detail))
    for old in prune(directory, args.keep):
        print("  pruned %s" % old.name)
    # A copy that does not verify is worse than no copy: it is mistaken for a backup.
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
