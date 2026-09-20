"""Run the dashboard's checks in one place, so a new session can see the whole state in one pass.

The page checks are jsdom scripts that each take a URL. They used to live only in a scratch folder
that is pruned after 72 hours, which meant the suite could quietly disappear between sessions.

    python tests/run.py            # local pages and the deployed ones
    python tests/run.py --local    # only what the local dashboard serves
    python tests/run.py --live     # only what teemobkk.io serves

jsdom is resolved from tests/node_modules if it is there, otherwise from the scratch harness, so
`npm i jsdom` inside tests/ makes this folder self-contained.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOCAL = "http://127.0.0.1:8765/"
LIVE_KO = "https://teemobkk.io/news/ko/"
LIVE_EN = "https://teemobkk.io/news/"
LIVE_THAI = "https://teemobkk.io/thai/news/"

# name, args, what it covers, needs a live server
SUITE = [
    ("t22.js", [], "카드 표시와 확장", "local"),
    ("t23.js", [], "기간·정렬", "local"),
    ("t25.js", [], "검색창", "local"),
    ("t26.js", [], "소스 알약", "local"),
    ("t27.js", [], "필터 축 배타", "local"),
    ("t28.js", [], "탭 글꼴", "local"),
    ("t29.js", [], "시드·언어", "local"),
    ("t32.js", [LOCAL], "키워드 멀티셀렉·해제", "local"),
    ("t33.js", [LOCAL], "키워드 교차(AND)", "local"),
    ("t34.js", [LOCAL], "검색어 매칭 규칙", "local"),
    ("t35.js", [LOCAL], "조건 줄·교차 필터", "local"),
    ("t36.js", [LOCAL], "숨기기·되돌리기 (운영자 화면)", "local"),
    ("t37.js", [LOCAL], "Teemo's Pick 배지·알약", "local"),
    ("t30.js", ["-", LIVE_EN], "영문 대시보드", "live"),
    ("t31.js", [LIVE_THAI], "태국 대시보드", "live"),
    ("t32.js", [LIVE_KO], "키워드 멀티셀렉 (운영)", "live"),
]

PYTHON_CHECKS = [
    ("test_landing.py", ["-m", "unittest", "test_landing"], "랜딩 단위 계약", "local"),
    ("test_categories.py", ["tests/test_categories.py"], "분류 다중 라벨 계약", "local"),
    ("test_admin_auth.py", ["tests/test_admin_auth.py"], "관리자 세션 규칙", "local"),
    ("test_admin_page.py", ["tests/test_admin_page.py"], "관리자·공개 문서 구성", "local"),
    ("test_hidden.py", ["tests/test_hidden.py"], "숨김·되돌리기 계약", "local"),
    ("test_picks.py", ["tests/test_picks.py"], "Pick 계약", "local"),
    ("test_admin_http.py", ["tests/test_admin_http.py"], "관리자 HTTP 게이트", "local"),
    ("probe_english_text.py", ["tools/probe_english_text.py"], "영문 문서 한국어 잔존", "local"),
    ("probe_english_text.py --thai", ["tools/probe_english_text.py", "--thai"], "태국 영문 문서 한국어 잔존", "local"),
]


def jsdom_path():
    for cand in (os.path.join(HERE, "node_modules"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "pagetest", "node_modules")):
        if os.path.isdir(os.path.join(cand, "jsdom")):
            return cand
    return ""


def tail(text, n=1):
    lines = [l for l in text.splitlines() if l.strip()]
    return lines[-n] if lines else "(출력 없음)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="로컬 페이지만")
    ap.add_argument("--live", action="store_true", help="운영 페이지만")
    a = ap.parse_args()
    want = {kind for kind, on in (("local", a.local), ("live", a.live)) if on} or {"local", "live"}

    env = dict(os.environ)
    nj = jsdom_path()
    if nj:
        env["NODE_PATH"] = nj
    if os.environ.get("HERMES_BROWSER_TOOLS"):
        env["HERMES_BROWSER_TOOLS"] = os.environ["HERMES_BROWSER_TOOLS"]

    print("  jsdom: %s" % (nj or "없음 — tests 안에서 npm i jsdom 필요"))
    print("  검사 대상: %s" % ", ".join(sorted(want)))
    print()

    results = []
    for name, args, what, kind in SUITE:
        if kind not in want:
            continue
        p = subprocess.run(["node", os.path.join(HERE, name)] + args,
                           capture_output=True, text=True, env=env, cwd=HERE, timeout=600)
        line = tail(p.stdout)
        results.append((name + " " + what, p.returncode == 0, line))
    for name, args, what, kind in PYTHON_CHECKS:
        if kind not in want:
            continue
        p = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                           env=env, cwd=ROOT, timeout=600)
        ok = p.returncode == 0
        results.append((os.path.basename(name) + " " + what, ok,
                        "OK" if ok else tail(p.stderr)))

    for name, ok, detail in results:
        print("  %s %-44s %s" % ("PASS" if ok else "FAIL", name, detail[:70]))
    bad = [n for n, ok, _ in results if not ok]
    print("\n  %d/%d" % (len(results) - len(bad), len(results)))
    if bad:
        print("  실패: %s" % ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
