"""Compare candidate rule sets for splitting a combined category.

Read-only. Re-classifies the current window with each variant and reports, for
every split axis, how many rows it captures and how many of those came from an
unrelated stored category (the false-positive signal: a money amount like
"2 million dollar" must not drag a whale-liquidation story into a rates axis).
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

LIQ_TIGHT = ["liquidity", "repo", "reverse repo", "qt", "qe", "treasury cash",
             "bank reserves", "pboc", "interbank", "유동성", "역레포", "자금 유동"]
RATE_TIGHT = ["interest rate", "real yield", "central bank", "ecb", "금리",
              "기준금리", "rate cut", "rate hike", "fed funds"]
USD_TIGHT = ["treasury yield", "bond yield", "10-year", "dxy", "dollar index",
             "greenback", "국채", "달러 인덱스", "미 국채", "treasury"]

TRUMP_TIGHT = ["trump", "트럼프", "미국 대통령"]
POLICY_TIGHT = ["white house", "tariff", "executive order", "strategic reserve",
                "관세", "백악관"]

VARIANTS = {
    "now (unsplit)": [],
    "A: 3-way axes + 2-way policy": [
        ("유동성", LIQ_TIGHT), ("금리", RATE_TIGHT), ("달러·국채", USD_TIGHT),
        ("트럼프", TRUMP_TIGHT), ("미국 정책", POLICY_TIGHT),
    ],
    "B: 유동성/금리 only (no dollar axis)": [
        ("유동성", LIQ_TIGHT), ("금리", RATE_TIGHT),
        ("트럼프", TRUMP_TIGHT), ("미국 정책", POLICY_TIGHT),
    ],
}

# Anything a split axis pulls in from these categories is a term that is too loose.
UNRELATED = {"일반", "시장·가격", "온체인·기관", "파생상품·청산", "ETF·수급",
             "스테이블코인", "이더리움·알트", "채굴", "X 발언", "주식·원자재"}


def hits(text, term):
    term = term.strip()
    if not term:
        return False
    if term in BOUNDARY:
        return re.search(r"\b" + re.escape(term) + r"s?\b", text) is not None
    return term in text


def build(insert):
    rules = {}
    placed = not insert
    for name, terms in CURRENT.items():
        if name in ("유동성·금리", "미국 정책·트럼프"):
            if not placed:
                for new_name, new_terms in insert:
                    rules[new_name] = new_terms
                placed = True
            continue
        rules[name] = terms
    return rules


def classify(text, rules):
    for name, terms in rules.items():
        if any(hits(text, t) for t in terms):
            return name
    return "일반"


con = sqlite3.connect(f"file:{os.path.join(ROOT, 'news.db')}?mode=ro", uri=True)
rows = list(con.execute("""
    SELECT title, summary, category FROM articles
    WHERE published_at > datetime('now', '-24 hours') AND region <> '태국'
"""))

SPLIT = {"유동성", "금리", "달러·국채", "트럼프", "미국 정책"}
for label, insert in VARIANTS.items():
    rules = CURRENT if not insert else build(insert)
    dist = Counter()
    grabbed = Counter()
    samples = {}
    for title, summary, stored in rows:
        fresh = classify(f"{title} {summary}".lower(), rules)
        dist[fresh] += 1
        if insert and fresh in SPLIT and stored in UNRELATED:
            grabbed[fresh] += 1
            samples.setdefault(fresh, (stored, title[:64]))
    print(f"=== {label} ===")
    for name, n in dist.most_common(8):
        print(f"  {n:5d}  {name}")
    if insert:
        print("  -- pulled out of an unrelated category --")
        for name in SPLIT:
            if grabbed[name]:
                stored, sample = samples[name]
                print(f"  {grabbed[name]:5d}  {name}  (was {stored})  e.g. {sample}")
    print()
