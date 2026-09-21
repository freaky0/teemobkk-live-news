"""운영에서 거르는 규칙이 실제로 도는지 확인한다.

확인하는 것:
  1. 익명은 규칙을 만들 수 없다 (쓰기 경로가 열려 있지 않다)
  2. 규칙을 켜면 그 문구가 들어 있는 기사가 등록은 되지만 조회에서 빠진다
  3. 규칙을 끄면 그 기사가 돌아온다 (되돌림이 실제로 된다)
  4. 숨긴 기사 29건에서 규칙 후보를 뽑을 수 있다 (꺼진 채로 올라온다)

운영 DB를 직접 고치므로 끝나면 스스로 지운다. 쓰는 것은 표식이 붙은 합성 기사 하나뿐이고,
운영자가 숨긴 29건과 그 밖의 기사는 건드리지 않는다.
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HOST = "root@72.62.64.195"
DIR = "/opt/teemo-live-news"
BASE = "https://teemobkk.io"
MARK = "zzz-probe-filter-marker"
LINK = "https://example.invalid/probe-filter"

pass_ = []


def check(name, ok, detail=""):
    pass_.append(bool(ok))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, "  (%s)" % detail if detail else ""))


def ssh(code, **kw):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, code],
                          capture_output=True, text=True, encoding="utf-8", **kw)


def py(code):
    """운영 서버에서 코어를 불러 실행한다."""
    return ssh("cd %s && PYTHONIOENCODING=utf-8 python3 -c %s"
               % (DIR, urllib.parse.quote(code, safe="")))


def api(path, body=None, method=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:                                   # noqa: BLE001
        return 0, {"error": str(exc)[:60]}


def cleanup():
    ssh("cd %s && python3 -c \"import live_news_dashboard as c; "
        "con=c.db_connect(); "
        "con.execute('DELETE FROM filter_hits WHERE link = ?', ('%s',)); "
        "con.execute('DELETE FROM articles WHERE link = ?', ('%s',)); "
        "con.execute('DELETE FROM filter_rules WHERE pattern = ?', ('%s',)); "
        "con.commit()\"" % (DIR, LINK, LINK, MARK))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="정리하지 않는다 (규칙 후보를 남겨 둔다)")
    args = parser.parse_args()

    # 1. 익명 쓰기
    status, _ = api("/api/filter", {"action": "add", "pattern": MARK})
    check("익명은 규칙을 만들 수 없음", status == 401, "상태 %s" % status)
    status, _ = api("/api/filters")
    check("익명은 규칙 목록을 볼 수 없음", status == 404, "상태 %s" % status)

    # 2. 규칙을 켜고 합성 기사를 등록한다
    start = ssh("cd %s && python3 -c \"import live_news_dashboard as c; "
                "print(len(c.filter_rules()))\"" % DIR)
    check("규칙은 지금 0개", start.stdout.strip() == "0", "규칙 %s개" % start.stdout.strip())

    made = ssh("cd %s && PYTHONIOENCODING=utf-8 python3 -c %s"
               % (DIR, urllib.parse.quote(
                   "import live_news_dashboard as c; "
                   "c.add_filter_rule('%s', enabled=True); "
                   "print([r['pattern'] for r in c.filter_rules()])" % MARK, safe="")))
    check("규칙을 켤 수 있음", MARK in (made.stdout or ""), (made.stdout or made.stderr or "").strip()[:60])

    ins = ssh("cd %s && PYTHONIOENCODING=utf-8 python3 -c %s"
              % (DIR, urllib.parse.quote(
                  "import live_news_dashboard as c; "
                  "from datetime import datetime, timezone; "
                  "now = datetime.now(timezone.utc).isoformat(); "
                  "c.insert_articles([{'link': '%s', 'title': 'Probe %s headline', 'summary': 'probe', "
                  "'source': 'Probe', 'source_type': 'rss', 'region': '글로벌', 'category': '시장·가격', "
                  "'categories': ['시장·가격'], 'priority': 1, 'published_at': now, 'collected_at': now}]); "
                  "print('caught', len(c.caught_links(200)))" % (LINK, MARK), safe="")))
    check("등록 뒤 규칙이 걸러 냄", "caught 1" in (ins.stdout or ""), (ins.stdout or ins.stderr or "").strip()[:70])

    reg = ssh("cd %s && python3 -c \"import sqlite3;c=sqlite3.connect('file:news.db?mode=ro',uri=True);"
              "print(c.execute(\\\"SELECT COUNT(*) FROM articles WHERE link='%s'\\\").fetchone()[0])\"" % (DIR, LINK))
    check("기사는 등록되어 있음 (삭제가 아니라 거르기)", reg.stdout.strip() == "1", "행 %s" % reg.stdout.strip())

    status, payload = api("/api/news?hours=24&limit=500")
    links = [a.get("link") for a in (payload.get("articles") or [])]
    check("공개 조회에는 나오지 않음", LINK not in links, "응답 %s건" % len(links))
    status, payload = api("/api/news?hours=24&limit=500&q=probe")
    links = [a.get("link") for a in (payload.get("articles") or [])]
    check("검색으로도 나오지 않음", LINK not in links, "응답 %s건" % len(links))

    off = ssh("cd %s && PYTHONIOENCODING=utf-8 python3 -c %s"
              % (DIR, urllib.parse.quote(
                  "import live_news_dashboard as c; "
                  "rid = [r['id'] for r in c.filter_rules()][0]; "
                  "c.set_filter_rule(rid, enabled=False); "
                  "print('caught', len(c.caught_links(200)))", safe="")))
    check("규칙을 끄면 걸린 기사가 돌아옴", "caught 0" in (off.stdout or ""), (off.stdout or off.stderr or "").strip()[:60])
    status, payload = api("/api/news?hours=24&limit=500&q=probe")
    links = [a.get("link") for a in (payload.get("articles") or [])]
    check("끄면 공개 조회로 다시 보임", LINK in links, "응답 %s건" % len(links))

    # 4. 숨긴 기사에서 규칙 뽑기
    learn = ssh("cd %s && PYTHONIOENCODING=utf-8 python3 -c %s"
                % (DIR, urllib.parse.quote(
                    "import live_news_dashboard as c; "
                    "before = len(c.filter_rules()); "
                    "c.learn_filter_rules(); "
                    "new = [r for r in c.filter_rules() if r['origin'] == 'learned']; "
                    "print('learned', len(new), '|', ', '.join(r['pattern'] for r in new[:3]), "
                    "'| 꺼짐', all(not r['enabled'] for r in new))", safe="")))
    out = (learn.stdout or learn.stderr or "").strip()
    check("숨긴 기사에서 후보를 뽑음", "learned 0" not in out and "learned" in out, out[:90])
    check("뽑은 후보는 꺼진 채로 들어옴", "꺼짐 True" in out, out[-30:])

    if not args.keep:
        cleanup()
        left = ssh("cd %s && python3 -c \"import live_news_dashboard as c; "
                   "print(len(c.filter_rules()), len(c.caught_links(200)), "
                   "c.db_connect().execute(\\\"SELECT COUNT(*) FROM articles WHERE link='%s'\\\").fetchone()[0])\""
                   % (DIR, LINK))
        check("정리됨 (규칙 0 · 걸린 기사 0 · 합성 기사 0)", left.stdout.strip() == "0 0 0",
              "남은 것 %s" % left.stdout.strip())

    print("\n  %d/%d" % (sum(pass_), len(pass_)))
    return 0 if all(pass_) else 1


if __name__ == "__main__":
    sys.exit(main())
