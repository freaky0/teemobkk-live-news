"""Verify the new taxonomy file against the one it replaces, by exact string comparison.

Non-ASCII text has silently lost or swapped characters on write before, so this compares the new
tables against the tables in the core *from before the split* - an independent file - instead of
trusting a read-back of the same write path. Category names are compared by exact set equality with
the combined categories they replace, so both a lost term and an added one are reported: an added
term changes behaviour too, by pulling a story off the category that earned its impact bonus.

The reference has to be a copy taken before the edit, because the core no longer holds the old
tables. Before committing the split:

    git show HEAD:live_news_dashboard.py > /tmp/core_before_taxonomy.py
    python tools/verify_taxonomy.py --old /tmp/core_before_taxonomy.py
"""
import argparse
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

parser = argparse.ArgumentParser()
parser.add_argument("--old", required=True,
                    help="a copy of live_news_dashboard.py from before the split")
args = parser.parse_args()

spec = importlib.util.spec_from_file_location("core", args.old)
core = importlib.util.module_from_spec(spec)
sys.modules["core"] = core
spec.loader.exec_module(core)

import category_rules  # noqa: E402

old_global = core.CATEGORY_RULES
new_global = dict(category_rules.GLOBAL_RULES)
old_thai = core.THAI_CATEGORY_RULES
new_thai = dict(category_rules.THAI_RULES)

problems = []

for name, terms in old_thai.items():
    if name not in new_thai:
        problems.append("thai category missing: " + name)
    elif new_thai[name] != terms:
        problems.append("thai terms changed: " + name)

REPLACED = {}
for name in old_global:
    if "·" in name and name not in new_global:
        REPLACED[name] = [part for part in name.split("·")]

for name, terms in old_global.items():
    if name in new_global:
        if new_global[name] != terms:
            problems.append("global terms changed: " + name)
    elif name in REPLACED:
        # Expected: the two combined names are the point of the change. A combined name may split
        # into axes or be merged into one, so the requirement is not "every part exists" - it is
        # that at least one of its words is now a category and that none of its vocabulary was
        # dropped. Parts come from the old key itself, so nothing here is hand-typed.
        parts = REPLACED[name]
        present = [part for part in parts if part in new_global]
        if not present:
            problems.append("no replacement became a category: " + name)
        # Exact set equality, not just "nothing was lost": an *added* term changes behaviour too -
        # it can pull a story off the category that earned its impact bonus. Comparing the sets is
        # also the byte-level check that the Korean and Thai terms survived the write intact.
        carried = [term for part in present for term in new_global[part]]
        lost = sorted(set(terms) - set(carried))
        added = sorted(set(carried) - set(terms))
        if lost:
            problems.append("vocabulary lost from %s: %s" % (name, ", ".join(lost)))
        if added:
            problems.append("vocabulary added by %s: %s" % (name, ", ".join(added)))
        print("  %s -> %s (%d terms, %d added, %d lost)"
              % (name, ", ".join(present) or "(none)", len(set(carried)), len(added), len(lost)))
        # A renamed category stays behind in stored rows, published files and caches. Those are
        # only normalised if the retirer recognises the old name, and this is the one place that
        # still has it: the table it was read from.
        retired_to = category_rules.retire(name)
        if retired_to not in new_global:
            problems.append("retire(%s) -> %s, which is not a category" % (name, retired_to))
        else:
            print("  retire(%s) -> %s" % (name, retired_to))
    else:
        problems.append("global category gone: " + name)

# Nothing may contain a comma: the column is comma-joined, so a comma inside a value would make
# one category look like two.
for name in list(new_global) + list(new_thai):
    if "," in name:
        problems.append("category name contains a comma: " + name)

bad_chars = 0
for path in ("category_rules.py",):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        bad_chars += handle.read().count("\ufffd")

print("global categories: %d -> %d" % (len(old_global), len(new_global)))
print("thai categories:   %d -> %d" % (len(old_thai), len(new_thai)))
print("replacement character U+FFFD in file:", bad_chars)
print("global order:", ", ".join(name for name, _ in category_rules.GLOBAL_RULES))
if bad_chars:
    problems.append("U+FFFD found in category_rules.py")
if problems:
    print("\nPROBLEMS")
    for item in problems:
        print("  -", item)
    sys.exit(1)
print("\nOK: every carried-over name and term matches the file it replaced")
