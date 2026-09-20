"""Recompute stored categories with the current rule table.

Changing the taxonomy leaves the archive holding the previous vocabulary, so the same window would
answer with two sets of names for a while. This walks every stored row, re-derives the list from the
title and summary, and reports what would change before it changes anything.

The score is *not* rewritten. It is recomputed alongside only to prove the split did not move it -
the bonus a story earns comes from its first category, and the new axes occupy the same positions
in the table as the combined ones they replace. A non-zero difference is a finding, not something
to overwrite.

    python tools/retag_categories.py                 # report only
    python tools/retag_categories.py --apply         # back up, then rewrite
    python tools/retag_categories.py --db PATH --apply
"""
import argparse
import io
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import category_rules as taxonomy  # noqa: E402
import live_news_dashboard as core  # noqa: E402


def recategorize(title, summary, region, source, source_type, published_at):
    """What make_article would decide for this row today."""
    fresh = core.make_article(title or "", "https://recategorize.invalid/", summary or "",
                              published_at or "", source or "", source_type or "", region or core.GLOBAL_REGION)
    return fresh["categories"], fresh["priority"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(ROOT, "news.db"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print("no database at %s" % args.db)
        return 1

    connection = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT link, title, summary, source, source_type, region, category, categories, priority, published_at "
        "FROM articles").fetchall()
    connection.close()

    before = Counter()
    after = Counter()
    label_counts = Counter()
    pairs = Counter()
    score_moved = []
    updates = []
    for row in rows:
        old_list = taxonomy.split_categories(row["categories"], row["category"])
        new_list, new_priority = recategorize(row["title"], row["summary"], row["region"],
                                              row["source"], row["source_type"], row["published_at"])
        before[row["category"]] += 1
        after[new_list[0]] += 1
        label_counts[min(len(new_list), 3)] += 1
        for i, first in enumerate(new_list):
            for second in new_list[i + 1:]:
                pairs[(first, second)] += 1
        if int(row["priority"] or 0) != int(new_priority or 0):
            score_moved.append((row["link"], row["priority"], new_priority))
        if taxonomy.join_categories(new_list) != (row["categories"] or ""):
            updates.append((taxonomy.join_categories(new_list), new_list[0], row["link"]))

    print("rows: %d" % len(rows))
    print("\n--- labels per row (how many chips a card would carry) ---")
    for n in sorted(label_counts):
        label = "%d label" % n if n < 3 else "3 or more"
        print("  %6d  %s" % (label_counts[n], label))
    print("\n--- most common label pairs ---")
    for (a, b), n in pairs.most_common(8):
        print("  %6d  %s + %s" % (n, a, b))
    print("\n--- first category: stored -> recomputed ---")
    names = sorted(set(before) | set(after))
    for name in names:
        if before[name] or after[name]:
            print("  %6d -> %-6d  %s" % (before[name], after[name], name))
    print("\n--- rows whose stored list would change: %d ---" % len(updates))
    for stored, first, link in updates[:5]:
        print("   %-28s %s" % (stored, link[:70]))
    print("\n--- rows whose score would change: %d ---" % len(score_moved))
    for link, was, now in score_moved[:5]:
        print("   %s: %s -> %s" % (link[:60], was, now))

    if not args.apply:
        print("\nreport only. Re-run with --apply to write (%d rows would change)." % len(updates))
        return 0

    if not updates:
        print("\nnothing to write.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = "%s.retag-%s.bak" % (args.db, stamp)
    # VACUUM INTO, not a file copy: the live database runs in WAL mode, and a copied main file
    # alone restores as "database disk image is malformed".
    with sqlite3.connect(args.db) as source:
        source.execute("VACUUM INTO ?", (backup,))
    print("\nbackup: %s" % backup)

    with sqlite3.connect(args.db) as target:
        target.executemany("UPDATE articles SET category = ?, categories = ? WHERE link = ?",
                           [(first, stored, link) for stored, first, link in updates])
        changed = target.total_changes
        check = target.execute("PRAGMA integrity_check").fetchone()[0]
    print("updated %d rows, integrity_check: %s" % (changed, check))
    return 0


if __name__ == "__main__":
    sys.exit(main())
