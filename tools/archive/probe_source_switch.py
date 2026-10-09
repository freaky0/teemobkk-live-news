"""운영에서 소스 스위치가 실제로 거르는지 확인한다.

설정을 바꾸는 일은 운영자 세션으로만 할 수 있다(비밀번호는 여기서 다루지 않는다). 그래서 이
도구는 두 갈래로 확인한다:

  * 익명 쓰기가 거부되는지 — 엔드포인트가 열려 있지 않다는 증거
  * 설정을 서버 DB에 직접 넣었을 때 읽기 경로가 정말 빠지는지 — 필터가 도는 증거
    (끝나면 되돌리고, 되돌린 것까지 다시 확인한다)

    python tools/probe_source_switch.py [--source CoinNess]
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

VPS = "root@72.62.64.195"
DB = "/opt/teemo-live-news/news.db"
BASE = "https://teemobkk.io"


def api(path):
    request = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read())


def count(**query):
    query.setdefault("hours", 24)
    query.setdefault("region", "글로벌")
    query["limit"] = 1
    data = api("/api/news?" + urllib.parse.urlencode(query, doseq=True))
    return data.get("total"), data.get("returned")


def ssh(script):
    done = subprocess.run(["ssh", "-o", "BatchMode=yes", VPS, script],
                          capture_output=True, text=True, timeout=90)
    return done.returncode, (done.stdout or "").strip(), (done.stderr or "").strip()


def set_hidden(sources):
    payload = json.dumps(sources, ensure_ascii=False)
    script = ("python3 - <<'PY'\n"
              "import sqlite3\n"
              "value = %r\n"
              "c = sqlite3.connect(%r)\n"
              "c.execute(\"INSERT INTO settings (name, value, changed_at) VALUES ('hidden_sources', ?, datetime('now')) \"\n"
              "          \"ON CONFLICT(name) DO UPDATE SET value = excluded.value, changed_at = excluded.changed_at\", (value,))\n"
              "c.commit()\n"
              "print(c.execute(\"SELECT value FROM settings WHERE name='hidden_sources'\").fetchone()[0])\n"
              "c.close()\n"
              "PY") % (payload, DB)
    return ssh(script)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="CoinNess")
    args = parser.parse_args()
    source = args.source
    results = []

    def check(name, good, detail=""):
        results.append(good)
        print("  %s %s%s" % ("PASS" if good else "FAIL", name, ("  (%s)" % detail) if detail else ""))

    # 1. an anonymous write must be refused
    body = json.dumps({"source": source, "hidden": True}).encode()
    request = urllib.request.Request(BASE + "/api/source", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            check("익명 쓰기가 거부됨", False, "상태 %s 로 통과했다" % response.status)
    except urllib.error.HTTPError as error:
        check("익명 쓰기가 거부됨", error.code == 401, "상태 %s" % error.code)

    # 2. the operator page carries the switch
    code, out, err = ssh("cd /opt/teemo-live-news && python3 -c \"import page_build;"
                         " p=page_build.admin_page(); print('sourceSwitch' in p, 'switchSource' in p)\"")
    check("운영자 문서에 스위치가 있음", code == 0 and out.split() == ["True", "True"], out or err[:60])

    before_all, _ = count()
    before_src, _ = count(source=source)
    print("      기준: 전체 %s건 · %s %s건" % (before_all, source, before_src))
    if not before_src:
        print("      %s 기사가 창에 없어 이번 확인은 건너뜁니다" % source)
        return 1 if not all(results) else 0

    # 3. with the source switched off, the read paths must lose it
    code, out, err = set_hidden([source])
    check("서버 DB에 설정을 넣음", code == 0, out or err[:80])
    try:
        after_all, _ = count()
        after_src, returned = count(source=source)
        check("꺼진 소스는 조회되지 않음", after_src == 0, "before %s → after %s" % (before_src, after_src))
        # The overall total cannot be asserted exactly: the collector keeps running while this is
        # measured, so the window grows (measured once: 691 → 758 while a source of 17 was dropped).
        # What is deterministic is the source's own count and the absence of its rows in the feed.
        print("      전체: %s → %s (숨긴 소스 %s건 · 그 사이 수집으로 늘어난 몫 포함)"
              % (before_all, after_all, before_src))
        feed = api("/api/news?region=%s&hours=24&limit=100" % urllib.parse.quote("글로벌"))
        leaked = [a for a in feed.get("articles", []) if a.get("source") == source]
        check("피드에도 남아 있지 않음", not leaked, "%d건 남음" % len(leaked))
    finally:
        code, out, err = set_hidden([])
        back_src, _ = count(source=source)
        check("되돌리면 그대로 돌아옴", back_src == before_src, "%s → %s" % (0, back_src))

    print("\n  %d/%d" % (sum(1 for r in results if r), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
