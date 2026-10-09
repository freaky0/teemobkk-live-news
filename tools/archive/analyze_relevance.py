"""소스별로 '시장 낱말이 없는 기사'가 얼마나 되는지 잰다.

숨김 29건 중 21건이 시장과 무관한 기사였다. 그렇다면 문제는 낱말이 아니라 '그 소스가 무엇이든
실어 온다'는 것이다. 소스별로 관련도 게이트를 걸면 무엇이 빠지고 무엇이 남는지 본다.
"""
import collections
import os
import re
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "news.db"
c = sqlite3.connect("file:%s?mode=ro" % (DB.replace("\\", "/")), uri=True)
c.row_factory = sqlite3.Row

MARKET = ("bitcoin", "btc", "crypto", "coin", "etf", "fed", "rate", "rates", "stock", "stocks",
          "market", "markets", "nasdaq", "s&p", "dollar", "gold", "oil", "yield", "bond",
          "inflation", "earnings", "trade", "tariff", "economy", "economic", "investor",
          "shares", "wall street", "hedge", "treasury", "매출", "실적", "증시", "주가", "금리",
          "연준", "환율", "투자", "채권", "금값", "코인", "비트코인", "시장", "경제", "무역",
          "관세", "물가", "예산", "은행", "기업", "반도체")

SOURCES = ("Bluesky · wsj.com", "Bluesky · bloomberg.com", "Bluesky · reuters.com",
           "Bluesky · theinformation.com", "SBHNews", "Google News · Bitcoin")

print("  시장 낱말이 제목/요약에 있는 기사의 비율 — 낮을수록 '무엇이든 싣는' 소스")
for src in SOURCES:
    rows = c.execute("SELECT title, summary FROM articles WHERE source=?", (src,)).fetchall()
    if not rows:
        continue
    hid = c.execute("""SELECT COUNT(*) FROM hidden_links h LEFT JOIN articles a ON a.link=h.link
                       WHERE a.source=?""", (src,)).fetchone()[0]
    keep = drop = 0
    dropped = []
    for r in rows:
        blob = ((r["title"] or "") + " " + (r["summary"] or "")).lower()
        if any(m in blob for m in MARKET):
            keep += 1
        else:
            drop += 1
            if len(dropped) < 4:
                dropped.append((r["title"] or "")[:56])
    print("\n  [%s] 전체 %d · 숨김 %d" % (src, len(rows), hid))
    print("      관련도 게이트를 걸면: 남음 %d (%.0f%%) · 걸림 %d (%.0f%%)"
          % (keep, 100.0 * keep / len(rows), drop, 100.0 * drop / len(rows)))
    for t in dropped:
        print("         걸릴 예: %s" % t)

print("\n  ── 남길 낱말 목록이 충분한가 (요약이 비어 있는 기사) ──")
for src in SOURCES:
    n = c.execute("SELECT COUNT(*) FROM articles WHERE source=? AND (summary IS NULL OR summary='')",
                  (src,)).fetchone()[0]
    tot = c.execute("SELECT COUNT(*) FROM articles WHERE source=?", (src,)).fetchone()[0]
    if tot:
        print("      %-28s 요약 없음 %4d/%4d (%.0f%%)" % (src[:28], n, tot, 100.0 * n / tot))
c.close()
