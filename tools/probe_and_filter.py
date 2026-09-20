"""Measure what an AND (intersection) keyword filter would actually return.

Read-only against the public API. The question this answers before anything is built: if a reader
selects three things at once and only stories carrying *all* of them are shown, how many stories
are left? A combination that returns nothing is a filter that looks broken.

Two matching semantics are measured side by side, because the API's `q` is a plain substring:

  * substring - what the API does today (title or summary contains the letters)
  * word      - the letters as a whole word, which is what a reader means by "AI"

    python tools/probe_and_filter.py [--url https://teemobkk.io] [--hours 24]
"""
import argparse
import json
import re
import urllib.parse
import urllib.request
from collections import Counter

UA = {"User-Agent": "Mozilla/5.0 (teemo-measure)"}


def fetch_window(base, hours, cap=20000):
    """Every row in the window, plus the total the API reports.

    Returning the reported total matters: a silent truncation here would make a thin intersection
    look thinner than it is, and the measurement would be wrong in the direction that changes the
    design.
    """
    rows, offset, total = [], 0, None
    while len(rows) < cap:
        query = urllib.parse.urlencode({"hours": hours, "limit": 1000, "offset": offset})
        request = urllib.request.Request("%s/api/news?%s" % (base, query), headers=UA)
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        batch = payload.get("articles") or []
        total = payload.get("total", total)
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows, total


def text_of(row):
    return ("%s %s" % (row.get("title") or "", row.get("summary") or "")).lower()


def matches(rows, condition):
    """condition: ('source', name) | ('category', name) | ('word', text) | ('substr', text)"""
    kind, value = condition
    value = value.lower()
    if kind == "source":
        return {row["link"] for row in rows if (row.get("source") or "").lower().startswith(value)}
    if kind == "category":
        return {row["link"] for row in rows
                if value in [str(c).lower() for c in (row.get("categories") or [row.get("category")])]}
    if kind == "substr":
        return {row["link"] for row in rows if value in text_of(row)}
    if kind == "word":
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])")
        return {row["link"] for row in rows if pattern.search(text_of(row))}
    raise ValueError(kind)


def show(rows, label, conditions):
    sets = [matches(rows, c) for c in conditions]
    each = " · ".join("%s=%d" % (c[1], len(s)) for c, s in zip(conditions, sets))
    every = set.intersection(*sets) if sets else set()
    print("  %-58s %s  ->  AND=%d" % (label, each, len(every)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://teemobkk.io")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--hours2", type=int, default=0, help="a second window to compare")
    args = parser.parse_args()

    windows = [args.hours] + ([args.hours2] if args.hours2 else [])
    for hours in windows:
        rows, total = fetch_window(args.url, hours)
        print("=== window %sh: fetched %d of %s rows ===\n" % (hours, len(rows), total))
        report(rows)
    return 0


def report(rows):
    print("--- one condition at a time (substring vs whole word) ---")
    for value in ("ai", "trump", "tariff", "bitcoin", "etf", "fed", "iran", "stablecoin"):
        print("  %-12s substring=%4d  whole word=%4d  (noise x%.1f)"
              % (value, len(matches(rows, ("substr", value))), len(matches(rows, ("word", value))),
                 len(matches(rows, ("substr", value))) / max(1, len(matches(rows, ("word", value))))))

    print("\n--- two at a time ---")
    for a, b in (("trump", "tariff"), ("trump", "ai"), ("fed", "yield"), ("bitcoin", "etf"),
                 ("iran", "oil"), ("stablecoin", "usdt")):
        show(rows, "word:%s + word:%s" % (a, b), [("word", a), ("word", b)])

    print("\n--- a source plus keywords ---")
    show(rows, "source:FinancialJuice + word:trump", [("source", "FinancialJuice"), ("word", "trump")])
    show(rows, "source:FinancialJuice + word:tariff", [("source", "FinancialJuice"), ("word", "tariff")])
    show(rows, "category:트럼프 + word:tariff", [("category", "트럼프"), ("word", "tariff")])
    show(rows, "category:트럼프 + category:미국 정책", [("category", "트럼프"), ("category", "미국 정책")])

    print("\n--- three at a time (the shape the reader described) ---")
    show(rows, "source:FinancialJuice + word:trump + word:tariff",
         [("source", "FinancialJuice"), ("word", "trump"), ("word", "tariff")])
    show(rows, "trump + tariff + bitcoin", [("word", "trump"), ("word", "tariff"), ("word", "bitcoin")])
    show(rows, "fed + inflation + bitcoin", [("word", "fed"), ("word", "inflation"), ("word", "bitcoin")])
    show(rows, "iran + israel + oil", [("word", "iran"), ("word", "israel"), ("word", "oil")])

    print("\n--- how thin does a triple get on the words the strip actually counts? ---")
    words = Counter()
    stop = set("the and for with from that this will have has are was were its not you your says said "
               "about after over into more than they their them out new one two can could would there "
               "here what when who why how all any our his her but his its".split())
    for row in rows:
        for token in re.findall(r"[a-z가-힣]{2,}", text_of(row)):
            if token not in stop and not token.isdigit():
                words[token] += 1
    top = [w for w, _ in words.most_common(12)]
    print("  top words:", ", ".join(top))
    pairs = Counter()
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            n = len(matches(rows, ("word", a)) & matches(rows, ("word", b)))
            pairs[(a, b)] = n
    for (a, b), n in pairs.most_common(6):
        print("  pair %-14s + %-14s AND=%d" % (a, b, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
