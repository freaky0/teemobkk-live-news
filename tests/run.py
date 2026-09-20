"""Run the dashboard's checks in one place, so a new session can see the whole state in one pass.

The page checks are jsdom scripts that each take a URL. They used to live only in a scratch folder
that is pruned after 72 hours, which meant the suite could quietly disappear between sessions.

The local run also used to need a dashboard already running on this machine, started by hand with
start_dashboard_bg.bat, and it refused to run without one. The local page is no longer the operator's
view - /admin on the deployed site is - so the local server is a fixture of this script now: it
rebuilds the page, starts a collector for the run, and stops what it started. A server that is
already listening is used as it is and left alone.

    python tests/run.py            # local pages and the deployed ones
    python tests/run.py --local    # only what the local page serves
    python tests/run.py --live     # only what teemobkk.io serves

jsdom is resolved from tests/node_modules if it is there, otherwise from the scratch harness, so
`npm i jsdom` inside tests/ makes this folder self-contained.
"""
import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOCAL_PORT = int(os.environ.get("DASH_PORT", "8765"))
LOCAL_URL = "http://127.0.0.1:%d/" % LOCAL_PORT
LIVE_KO = "https://teemobkk.io/news/ko/"
LIVE_EN = "https://teemobkk.io/news/"
LIVE_THAI = "https://teemobkk.io/thai/news/"

# name, args, what it covers, needs a live server
SUITE = [
    ("t22.js", [LOCAL_URL], "카드 표시와 확장", "local"),
    ("t23.js", [LOCAL_URL], "기간·정렬", "local"),
    ("t25.js", [LOCAL_URL], "검색창", "local"),
    ("t26.js", [LOCAL_URL], "소스 알약", "local"),
    ("t27.js", [LOCAL_URL], "필터 축 배타", "local"),
    ("t28.js", [LOCAL_URL], "탭 글꼴", "local"),
    ("t29.js", [LOCAL_URL], "시드·언어", "local"),
    ("t32.js", [LOCAL_URL], "키워드 멀티셀렉·해제", "local"),
    ("t33.js", [LOCAL_URL], "키워드 교차(AND)", "local"),
    ("t34.js", [LOCAL_URL], "검색어 매칭 규칙", "local"),
    ("t35.js", [LOCAL_URL], "조건 줄·교차 필터", "local"),
    ("t36.js", [LOCAL_URL], "숨기기·되돌리기 (운영자 화면)", "local"),
    ("t37.js", [LOCAL_URL], "Teemo's Pick 배지·알약", "local"),
    ("t39.js", [LOCAL_URL], "소스 스위치·알약", "local"),
    ("t30.js", ["-", LIVE_EN], "영문 대시보드", "live"),
    ("t31.js", [LIVE_THAI], "태국 대시보드", "live"),
    ("t32.js", [LIVE_KO], "키워드 멀티셀렉 (운영)", "live"),
]

PYTHON_CHECKS = [
    ("test_landing.py", ["-m", "unittest", "test_landing"], "랜딩 단위 계약", "local"),
    ("test_categories.py", ["tests/test_categories.py"], "분류 다중 라벨 계약", "local"),
    ("test_admin_auth.py", ["tests/test_admin_auth.py"], "관리자 세션 규칙", "local"),
    ("test_admin_page.py", ["tests/test_admin_page.py"], "관리자·공개 문서 구성", "local"),
    ("test_page_script.py", ["tests/test_page_script.py"], "문서 스크립트 문법(node --check)", "local"),
    ("test_hidden.py", ["tests/test_hidden.py"], "숨김·되돌리기 계약", "local"),
    ("test_picks.py", ["tests/test_picks.py"], "Pick 계약", "local"),
    ("test_admin_http.py", ["tests/test_admin_http.py"], "관리자 HTTP 게이트", "local"),
    ("test_source_switch.py", ["tests/test_source_switch.py"], "소스 스위치 계약", "local"),
    ("probe_english_text.py", ["tools/probe_english_text.py"], "영문 문서 한국어 잔존", "local"),
    ("probe_english_text.py --thai", ["tools/probe_english_text.py", "--thai"], "태국 영문 문서 한국어 잔존", "local"),
]


def jsdom_path():
    for cand in (os.path.join(HERE, "node_modules"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "pagetest", "node_modules")):
        if os.path.isdir(os.path.join(cand, "jsdom")):
            return cand
    return ""


def server_is_up(url=None):
    """Whether something is answering on the local port."""
    try:
        with urllib.request.urlopen(url or LOCAL_URL, timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def port_is_taken(port=None):
    with socket.socket() as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port or LOCAL_PORT)) == 0


def build_local_page():
    """Rebuild the page the local server serves.

    The checks read the document on disk, so a stale one would test code that is not there any more.
    Only the local page is written here; the published copies and the section pages belong to the
    deployment, and a test run must not touch them.
    """
    sys.path.insert(0, ROOT)
    import page_build
    size = page_build.write(page_build.ROOT / "index.html", page_build.admin_page())
    return size


def start_local_server(log_path):
    """Start a collector for this run and return the process, or None if it will not come up."""
    handle = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "live_news_dashboard.py", "--port", str(LOCAL_PORT), "--interval", "3600"],
        cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    for _ in range(60):
        if server_is_up():
            return process
        if process.poll() is not None:
            break
        time.sleep(0.5)
    return None


def stop_local_server(process):
    """Stop the server this script started, and say whether the port came free."""
    if process is None or process.poll() is not None:
        return True
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
    for _ in range(20):
        if not port_is_taken():
            return True
        time.sleep(0.25)
    return False


def failure_reason(log_path):
    """The most useful line from a server that would not come up.

    The last line of the log is often a collection cycle message, which says nothing about the
    failure; the reason is the bind error underneath it.
    """
    if not os.path.exists(log_path):
        return "로그 없음"
    text = open(log_path, encoding="utf-8", errors="replace").read()
    marks = ("Address already in use", "OSError", "error while attempting", "Traceback",
             "Errno", "PermissionError")
    for line in text.splitlines():
        if any(mark in line for mark in marks):
            return line.strip()
    return tail(text)


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

    results = []
    started = None
    log_path = os.path.join(HERE, "local_test_server.log")
    if "local" in want:
        if server_is_up():
            print("  로컬 서버: 이미 떠 있는 %s 를 씁니다 (그대로 둡니다)" % LOCAL_URL)
        else:
            print("  로컬 페이지 재생성: index.html (%d bytes)" % build_local_page())
            started = start_local_server(log_path)
            if started is None:
                # Not a skip: the point of this run is to test what this machine serves, so a server
                # that will not start is a failure of the run, not a reason to check less.
                results.append(("로컬 서버 기동", False, failure_reason(log_path)))
                want.discard("local")
            else:
                print("  로컬 서버: %s (pid %d, 이 실행이 띄웠습니다)" % (LOCAL_URL, started.pid))
    print()

    try:
        for name, args, what, kind in SUITE:
            if kind not in want:
                continue
            p = subprocess.run(["node", os.path.join(HERE, name)] + args,
                               capture_output=True, text=True, env=env, cwd=HERE, timeout=600)
            ok = p.returncode == 0
            results.append((name + " " + what, ok, "OK" if ok else tail(p.stdout)))
            if not ok:
                # A failing page check used to report only its own summary line, which says a count
                # and not which assertion failed. The check names are the useful part.
                for line in p.stdout.splitlines():
                    if "FAIL" in line:
                        print("      " + line.strip())
        for name, args, what, kind in PYTHON_CHECKS:
            if kind not in want:
                continue
            p = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                               env=env, cwd=ROOT, timeout=600)
            ok = p.returncode == 0
            results.append((os.path.basename(name) + " " + what, ok,
                            "OK" if ok else tail(p.stderr)))
            if not ok:
                for line in p.stderr.splitlines():
                    if line.startswith(("FAIL", "ERROR", "AssertionError")):
                        print("      " + line.strip()[:150])
    finally:
        if started is not None:
            freed = stop_local_server(started)
            print("  로컬 서버 종료: %s" % ("포트 반환됨" if freed else "포트가 아직 잡혀 있음"))
            if not freed:
                results.append(("로컬 서버 종료", False, "포트 %d 가 아직 잡혀 있습니다" % LOCAL_PORT))

    for name, ok, detail in results:
        print("  %s %-44s %s" % ("PASS" if ok else "FAIL", name, detail[:70]))
    bad = [n for n, ok, _ in results if not ok]
    print("\n  %d/%d" % (len(results) - len(bad), len(results)))
    if bad:
        print("  실패: %s" % ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
