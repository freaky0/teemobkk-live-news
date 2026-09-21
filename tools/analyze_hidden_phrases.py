"""숨긴 제목에서 '등록 전에 걸 규칙' 후보를 뽑고, 각각이 현재 몇 건을 잡는지 잰다.

낱말 하나가 아니라 반복되는 구절(4~8단어)을 본다. 되풀이되는 정형 기사가 숨김의 큰 몫이라
그쪽이 가장 정확한 규칙이 된다. 읽기 전용.
"""
import collections
import os
import re
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "news.db"
c = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c.row_factory = sqlite3.Row

rows = c.execute("""
    SELECT COALESCE(NULLIF(h.title,''), a.title, '') AS t,
           COALESCE(a.source,'?') AS s, a.summary AS sm
      FROM hidden_links h LEFT JOIN articles a ON a.link = h.link""").fetchall()
hid = [(r["t"] or "", r["s"] or "?", r["sm"] or "") for r in rows]
kept = c.execute("SELECT title, summary, source FROM articles WHERE link NOT IN "
                 "(SELECT link FROM hidden_links)").fetchall()
kept_t = [((r["title"] or "") + " " + (r["summary"] or "")).lower() for r in kept]

print("  숨김 %d건에서 뽑은 구절 후보 (앞 12단어 안에서 4~8단어 연속)" % len(hid))
cand = collections.Counter()
for t, s, _ in hid:
    w = re.findall(r"[0-9A-Za-z가-힣']+", t.lower())
    for n in range(8, 3, -1):
        for i in range(0, max(0, len(w) - n + 1)):
            # 첫 12단어까지만 본다: 제목 앞머리가 되풀이되는 정형 기사의 표식이다
            if i + n > 12:
                continue
            cand[" ".join(w[i:i + n])] += 1

# 긴 구절부터, 숨김 2건 이상, 남은 기사에는 거의 없는 것만
best = []
for phrase, n in cand.items():
    if n < 2 or len(phrase) < 12:
        continue
    hit_kept = sum(1 for k in kept_t if phrase in k)
    best.append((n - hit_kept, n, hit_kept, phrase))
best.sort(reverse=True)

seen = []
for score, n, hit_kept, phrase in best:
    if any(phrase in s or s in phrase for s in seen):
        continue
    seen.append(phrase)
    if len(seen) > 10:
        break
    print("      숨김 %2d · 남은 기사 %2d  \"%s\"" % (n, hit_kept, phrase[:66]))
    for t, s, _ in hid:
        if phrase in t.lower():
            print("         예: [%s] %s" % (s[:18], t[:58]))
            break

print("\n  ── 낱말 후보(광고·스팸)와 타격량 ──")
for w in ("casino", "bonus", "sponsor", "promo", "airdrop", "에어드롭", "이벤트"):
    n_hid = sum(1 for t, _, _ in hid if w in t.lower())
    n_kept = sum(1 for k in kept_t if w in k)
    if n_hid or n_kept:
        print("      %-10s 숨김 %2d · 남은 기사 %3d" % (w, n_hid, n_kept))

print("\n  ── 소스 규모 (숨김이 적어도 부피가 큰 곳) ──")
for r in c.execute("""SELECT source, COUNT(*) n FROM articles GROUP BY source
                      ORDER BY n DESC LIMIT 8"""):
    h = c.execute("""SELECT COUNT(*) FROM hidden_links h LEFT JOIN articles a ON a.link=h.link
                     WHERE a.source=?""", (r["source"],)).fetchone()[0]
    print("      %-28s 전체 %5d · 숨김 %2d" % ((r["source"] or "?")[:28], r["n"], h))

print("\n  ── '시장과 무관'해 보이는 숨김의 비율 (제목에 시장 낱말이 없는 것) ──")
MARKET = ("bitcoin", "btc", "crypto", "coin", "etf", "fed", "rate", "stock", "market", "nasdaq",
          "s&p", "dollar", "gold", "oil", "yield", "inflation", "earnings", "trade", "비트코인",
          "코인", "주가", "금리", "연준", "환율", "증시", "시장", "투자", "채권", "금값")
nomarket = [t for t, _, _ in hid if not any(m in t.lower() for m in MARKET)]
print("      시장 낱말 없음 %d/%d (%.0f%%)" % (len(nomarket), len(hid), 100.0 * len(nomarket) / max(len(hid), 1)))
for t in nomarket[:6]:
    print("         %s" % t[:66])
c.close()
