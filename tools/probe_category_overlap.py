"""Measure how the split axes overlap, and what multi-label would look like.

Read-only. Tells you two things before you pick single-label or multi-label:
how many rows match two split axes at once (so a priority order silently drops a
label) and how many rows would carry two or more labels if axes stacked.
"""
import importlib.util
import re
import sqlite3
import sys
import os
from collections import Counter
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "live_news_dashboard.py")

spec = importlib.util.spec_from_file_location("core", CORE)
sys.path.insert(0, ROOT)
core = importlib.util.module_from_spec(spec)
sys.modules["core"] = core
spec.loader.exec_module(core)

BOUNDARY = core.BOUNDARY_TERMS

AXES = [
    ("유동성", ["liquidity", "repo", "reverse repo", "qt", "qe", "treasury cash",
                "bank reserves", "pboc", "interbank", "유동성", "역레포"]),
    ("금리", ["interest rate", "real yield", "central bank", "ecb", "금리",
              "기준금리", "rate cut", "rate hike", "fed funds"]),
    ("달러·국채", ["treasury yield", "bond yield", "10-year yield", "dxy",
                  "dollar index", "greenback", "국채", "달러 인덱스", "미 국채"]),
    ("트럼프", ["trump", "트럼프", "미국 대통령"]),
    ("미국 정책", ["white house", "tariff", "executive order", "strategic reserve",
                  "관세", "백악관"]),
]


def hits(text, term):
    term = term.strip()
    if not term:
        return False
    if term in BOUNDARY:
        return re.search(r"\b" + re.escape(term) + r"s?\b", text) is not None
    return term in text


con = sqlite3.connect(f"file:{os.path.join(ROOT, 'news.db')}?mode=ro", uri=True)
rows = list(con.execute("""
    SELECT title, summary, category FROM articles
    WHERE published_at > datetime('now', '-24 hours') AND region <> '태국'
"""))

labels = []
for title, summary, stored in rows:
    text = f"{title} {summary}".lower()
    labels.append(tuple(name for name, terms in AXES if any(hits(text, t) for t in terms)))

print(f"window rows: {len(rows)}")
print("rows matching no split axis:", sum(1 for l in labels if not l))
print("rows matching exactly one:", sum(1 for l in labels if len(l) == 1))
print("rows matching two or more:", sum(1 for l in labels if len(l) > 1))

print("\n--- pairwise overlap (a story counted on both axes) ---")
for a, b in combinations([n for n, _ in AXES], 2):
    n = sum(1 for l in labels if a in l and b in l)
    if n:
        print(f"{n:5d}  {a} + {b}")

print("\n--- axis totals if labels stack ---")
for name, _ in AXES:
    print(f"{sum(1 for l in labels if name in l):5d}  {name}")

print("\n--- first rows carrying two labels ---")
shown = 0
for (title, summary, stored), l in zip(rows, labels):
    if len(l) > 1 and shown < 6:
        print(f"  {list(l)} :: {title[:66]}")
        shown += 1
