"""Merge the database this host has been collecting into an uploaded one.

Direction matters: the uploaded file carries the longer history (days), the host's own file
carries the minutes since it was installed. Both are keyed by link, so inserting the host's rows
into the uploaded file and swapping the result in keeps everything and drops nothing.

Run on the host with the service stopped. The old file is kept as news.db.replaced-<stamp>.
"""
import shutil
import sqlite3
import sys
import time

BASE = "/opt/teemo-live-news"
INCOMING = BASE + "/news_local.db"
CURRENT = BASE + "/news.db"


def tables(connection):
    return [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]


def columns(connection, table):
    return [r[1] for r in connection.execute("PRAGMA table_info(%s)" % table).fetchall()]


def merge(target_path, source_path):
    target = sqlite3.connect(target_path)
    source = sqlite3.connect("file:%s?mode=ro" % source_path, uri=True)
    report = []
    for table in tables(source):
        if table not in tables(target):
            report.append("  %-14s skipped (not in the uploaded database)" % table)
            continue
        shared = [c for c in columns(source, table) if c in columns(target, table)]
        if not shared:
            continue
        before = target.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        rows = source.execute("SELECT %s FROM %s" % (", ".join(shared), table)).fetchall()
        target.executemany(
            "INSERT OR IGNORE INTO %s (%s) VALUES (%s)"
            % (table, ", ".join(shared), ", ".join("?" * len(shared))), rows)
        target.commit()
        after = target.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        report.append("  %-14s %6d -> %6d  (+%d new, %d already there)"
                      % (table, before, after, after - before, len(rows) - (after - before)))
    target.close()
    source.close()
    return report


print("merging the host's rows into the uploaded database")
for line in merge(INCOMING, CURRENT):
    print(line)

stamp = time.strftime("%Y%m%d-%H%M%S")
shutil.move(CURRENT, "%s.replaced-%s" % (CURRENT, stamp))
shutil.move(INCOMING, CURRENT)
print("  swapped in; previous file kept as news.db.replaced-%s" % stamp)

check = sqlite3.connect(CURRENT)
total = check.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
low, high = check.execute("SELECT MIN(published_at), MAX(published_at) FROM articles").fetchone()
print("  articles: %d rows, %s .. %s" % (total, str(low)[:16], str(high)[:16]))
for region, count in check.execute(
        "SELECT region, COUNT(*) FROM articles GROUP BY region").fetchall():
    print("    %s %d" % (region, count))
check.close()
