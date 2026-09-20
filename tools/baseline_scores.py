"""Separate pre-existing score drift from a score change this taxonomy edit caused.

A stored score can differ from a fresh computation for reasons that have nothing to do with the
current change: the formula has been edited before, and the collector added bonuses that cannot be
recovered from a stored row. So before blaming the new rules, this recomputes every row twice -
once with the core as it is now, once with the previous core kept from before the edit - and
reports both differences against the stored value.

    python tools/baseline_scores.py [--old PATH_TO_PREVIOUS_CORE]
"""
import argparse
import importlib.util
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import live_news_dashboard as new_core  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.modules.setdefault(name + "_dir", module)
    spec.loader.exec_module(module)
    return module


def score(module, row):
    fresh = module.make_article(row["title"] or "", "https://baseline.invalid/", row["summary"] or "",
                                row["published_at"] or "", row["source"] or "",
                                row["source_type"] or "", row["region"] or new_core.GLOBAL_REGION)
    return int(fresh["priority"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(ROOT, "news.db"))
    parser.add_argument("--old", required=True, help="a copy of live_news_dashboard.py from before "
                                                     "the taxonomy edit")
    args = parser.parse_args()

    old_core = load(args.old, "old_core")

    connection = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT link, title, summary, source, source_type, region, category, priority, published_at "
        "FROM articles").fetchall()
    connection.close()

    drift = 0
    caused = 0
    examples = []
    for row in rows:
        stored = int(row["priority"] or 0)
        was = score(old_core, row)
        now = score(new_core, row)
        if was != stored:
            drift += 1
        if was != now:
            caused += 1
            if len(examples) < 8:
                examples.append((row["link"], row["category"], stored, was, now))

    print("rows: %d" % len(rows))
    print("stored score differs from the previous core's computation: %d  (pre-existing drift)" % drift)
    print("this taxonomy edit moves the score: %d" % caused)
    for link, category, stored, was, now in examples:
        print("   stored=%s old=%s new=%s  [%s]  %s" % (stored, was, now, category, link[:58]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
