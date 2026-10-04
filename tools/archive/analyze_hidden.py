"""숨긴 기사를 분석해 '등록 전에 거를 수 있는 규칙'의 실체를 본다.

읽기 전용. 계산은 로컬(파이썬)에서 하고 토큰은 쓰지 않는다.

판단하려는 것:
  1. 숨긴 기사가 어느 소스에 몰려 있는가 (소스 단위로 이미 해결되는 문제인가)
  2. 제목 낱말로 갈리는가 (숨긴 쪽에만 잘 나오는 낱말이 있는가)
  3. 그 낱말을 규칙으로 삼으면 남은 기사를 얼마나 잘못 잡는가 (거짓 양성)
"""
import collections
import os
import re
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "news.db"
if not os.path.exists(DB):
    sys.exit("  DB 없음: %s" % DB)

c = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c.row_factory = sqlite3.Row

total = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
hidden = c.execute("SELECT COUNT(*) FROM hidden_links").fetchone()[0]
print("  DB %s" % os.path.basename(DB))
print("  전체 기사 %d · 숨긴 링크 %d (%.1f%%)" % (total, hidden, 100.0 * hidden / max(total, 1)))

# ── 1. 소스별로 몰려 있는가 ─────────────────────────────────────────────
rows = c.execute("""
    SELECT COALESCE(a.source,'(없음)') AS src,
           COUNT(*) AS hidden_n,
           (SELECT COUNT(*) FROM articles b WHERE b.source = a.source) AS all_n
      FROM hidden_links h LEFT JOIN articles a ON a.link = h.link
     GROUP BY src ORDER BY hidden_n DESC""").fetchall()
print("\n  [1] 숨김이 몰린 소스 (상위 12)")
print("      %-28s %6s %7s %7s" % ("소스", "숨김", "전체", "숨김률"))
for r in rows[:12]:
    rate = 100.0 * r["hidden_n"] / max(r["all_n"], 1)
    print("      %-28s %6d %7d %6.1f%%" % (r["src"][:28], r["hidden_n"], r["all_n"], rate))

# ── 2. 제목 낱말로 갈리는가 ─────────────────────────────────────────────
TOK = re.compile(r"[0-9A-Za-z]{3,}|[가-힣]{2,}")
def toks(s):
    return [t.lower() for t in TOK.findall(s or "")]

hid_titles = [r[0] or "" for r in c.execute(
    "SELECT COALESCE(NULLIF(h.title,''), a.title, '') FROM hidden_links h "
    "LEFT JOIN articles a ON a.link = h.link")]
all_titles = [r[0] or "" for r in c.execute("SELECT title FROM articles")]

hcount = collections.Counter()
for t in hid_titles:
    hcount.update(set(toks(t)))
acount = collections.Counter()
for t in all_titles:
    acount.update(set(toks(t)))

cand = []
for w, hn in hcount.items():
    if hn < 3:
        continue
    an = acount.get(w, 0)
    rate = hn / max(an, 1)
    if rate >= 0.5:
        cand.append((hn, rate, an, w))
cand.sort(reverse=True)

print("\n  [2] 숨긴 제목에만 잘 나오는 낱말 (숨김 3건 이상 · 숨김률 50% 이상)")
if not cand:
    print("      없음 — 낱말로는 갈리지 않는다")
for hn, rate, an, w in cand[:20]:
    print("      %-24s 숨김 %3d / 전체 %3d  (%.0f%% 숨김)" % (w[:24], hn, an, 100 * rate))

# ── 3. 규칙으로 삼으면 남은 기사를 얼마나 잘못 잡는가 ────────────────────
print("\n  [3] 후보 낱말을 규칙으로 쓸 때의 영향 (상위 5개 낱말 기준)")
kept = c.execute("SELECT title, source FROM articles WHERE link NOT IN "
                 "(SELECT link FROM hidden_links)").fetchall()
for hn, rate, an, w in cand[:5]:
    hit = [r for r in kept if w in (r["title"] or "").lower()]
    srcs = collections.Counter(r["source"] for r in hit)
    print("      '%s' → 아직 남은 기사 %d건 걸림 %s" % (
        w[:18], len(hit), dict(srcs.most_common(3)) if hit else ""))

# ── 4. 숨긴 기사 실제 제목 (사람이 보는 표본) ───────────────────────────
print("\n  [4] 최근 숨긴 기사 20건 (제목 · 소스)")
for r in c.execute("""
    SELECT COALESCE(NULLIF(h.title,''), a.title, '') AS t, COALESCE(a.source,'?') AS s, h.hidden_at
      FROM hidden_links h LEFT JOIN articles a ON a.link = h.link
     ORDER BY h.hidden_at DESC LIMIT 20"""):
    print("      %s  [%s]  %s" % ((r["t"] or "")[:64], (r["s"] or "?")[:16], (r["hidden_at"] or "")[:16]))

print("\n  [5] 숨긴 링크의 도메인 (상위 8)")
doms = collections.Counter()
for (l,) in c.execute("SELECT link FROM hidden_links"):
    m = re.match(r"https?://([^/]+)", l or "")
    if m:
        doms[m.group(1).lower()] += 1
for d, n in doms.most_common(8):
    print("      %-40s %d" % (d[:40], n))
c.close()
