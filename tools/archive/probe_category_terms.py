"""Attribute each split-axis capture to the keyword that caused it.

Read-only. Answers "which term is pulling this row in" so a bad keyword shows up
as a number instead of hiding behind a plausible-looking category count.
"""
import importlib.util
import re
import sqlite3
import sys
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "live_news_dashboard.py")

spec = importlib.util.spec_from_file_location("core", CORE)
sys.path.insert(0, ROOT)
core = importlib.util.module_from_spec(spec)
sys.modules["core"] = core
spec.loader.exec_module(core)

CURRENT = core.CATEGORY_RULES
BOUNDARY = core.BOUNDARY_TERMS

AXES = [
    ("유동성", ["liquidity", "repo", "reverse repo", "qt", "qe", "treasury cash",
                "bank reserves", "pboc", "interbank", "유동성", "역레포"]),
    ("금리", ["interest rate", "real yield", "central bank", "ecb", "금리",
              "기준금리", "rate cut", "rate hike", "fed funds"]),
    ("달러·국채", ["treasury yield", "bond yield", "10-year", "dxy", "dollar index",
                  "greenback", "국채", "달러 인덱스", "미 국채", "treasury"]),
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

print(f"window rows: {len(rows)}\n")
for axis, terms in AXES:
    matched = []
    for title, summary, stored in rows:
        text = f"{title} {summary}".lower()
        why = [t for t in terms if hits(text, t)]
        if why:
            matched.append((stored, why, title[:58]))
    from collections import Counter as C2
    bycat = C2(m[0] for m in matched)
    terms_used = C2(t for m in matched for t in m[1])
    print(f"--- {axis}: {len(matched)} rows ---")
    print("   from:", dict(bycat.most_common(6)))
    print("   terms:", dict(terms_used.most_common(6)))
    for stored, why, title in matched[:3]:
        print(f"     [{stored}] {why} :: {title}")
    print()
