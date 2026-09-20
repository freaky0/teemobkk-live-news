"""Check the Thailand section front page, and the category deep link into its dashboard.

Usage:  python tools/probe_thai.py            (offline, deterministic payload)
        python tools/probe_thai.py --live     (against https://teemobkk.io/thai/)
"""
import json
import os
import sys
from pathlib import Path

if os.environ.get("HERMES_BROWSER_TOOLS"):
    sys.path.insert(0, os.environ["HERMES_BROWSER_TOOLS"])
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import landing_thai

BASE = "https://teemobkk.io/thai/"
LIVE = "--live" in sys.argv
OUT = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "shots"
OUT.mkdir(parents=True, exist_ok=True)

TITLES = ["태국 이민국, 비자 연장 온라인 신청 확대", "방콕 시내 교통 체계 개편 발표",
          "태국 남부 폭우로 도로 통제", "푸켓 관광객 회복세 지속",
          "태국 중앙은행 기준금리 동결", "방콕 병원 진료 예약 앱 출시"]
PAYLOAD = {
    "updated_at": "2026-09-20T02:30:00+00:00",
    "total": 572,
    "articles": [{"title": TITLES[i], "region": "태국", "link": "https://example.com/th/%d" % i,
                  "published_at": "2026-09-20T02:2%d:00+00:00" % i, "source": "Bangkok Post",
                  "category": ["비자·이민", "태국 생활", "사고·재난", "태국 관광", "태국 경제", "태국 보건"][i]}
                 for i in range(6)],
}

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors, requests = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append(r.url))

    if not LIVE:
        page.route(BASE, lambda r: r.fulfill(content_type="text/html", body=landing_thai.render_thai_landing()))
        page.route("**/api/news?*", lambda r: r.fulfill(json=PAYLOAD))
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_function("document.querySelector('#news-list').getAttribute('aria-busy')==='false'")
    page.wait_for_timeout(1600)

    head = page.evaluate("""(() => {
      const line = document.querySelector('h1 .rise > i');
      return {text: document.querySelector('h1').innerText.replace(/\\n/g,''),
              transform: getComputedStyle(line).transform,
              height: Math.round(line.getBoundingClientRect().height)};
    })()""")
    check("제목이 마스크에서 내려옴", head["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)"), head["transform"])
    check("제목 문구", "방콕에서먼저 볼 소식" in head["text"], head["text"])
    check("제목 줄이 실제 높이", head["height"] > 20, str(head["height"]))

    if LIVE:
        import urllib.request
        req = urllib.request.Request(
            "https://teemobkk.io/api/news?region=%ED%83%9C%EA%B5%AD&hours=24&limit=1",
            headers={"User-Agent": "Mozilla/5.0"})
        now = json.loads(urllib.request.urlopen(req, timeout=30).read())
        want = "{:,}건".format(now["total"])
    else:
        want = "572건"
    check("통계가 수집 서버 값과 일치", page.locator("#stat-total").inner_text() == want,
          page.locator("#stat-total").inner_text() + " (기대 " + want + ")")

    check("태국 소식 6건", page.locator(".news-item h3").count() == 6, str(page.locator(".news-item h3").count()))
    topics = page.evaluate("""Array.from(document.querySelectorAll('.topic-link')).map((a) => a.getAttribute('href'))""")
    check("분류 7개가 딥링크", len(topics) == 7 and all("/thai/news/ko/#cat=" in t for t in topics), ", ".join(topics[:2]))
    check("태국 목록만 요청", any("region=%ED%83%9C%EA%B5%AD" in u or "region=태국" in u for u in requests),
          next((u.split("?")[1][:60] for u in requests if "/api/news?" in u), "없음"))

    band = page.evaluate("""(() => {
      const rail = document.querySelector('.marq > div');
      return {anim: getComputedStyle(rail).animationName, w: Math.round(rail.scrollWidth),
              c: Math.round(document.querySelector('.marq').clientWidth)};
    })()""")
    check("아웃라인 띠가 흐름", band["anim"] == "drift" and band["w"] > band["c"], "%s · %d>%d" % (band["anim"], band["w"], band["c"]))

    for width in (320, 390, 768, 1024, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(120)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("가로 넘침 없음 @%d" % width, over <= 0, "%dpx" % over)

    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    css = page.evaluate("""(() => {
      const list = document.querySelector('.news-list');
      return {display: getComputedStyle(list).display, anim: getComputedStyle(list).animationName,
              clip: getComputedStyle(document.querySelector('#news')).overflow,
              items: document.querySelectorAll('.news-item').length};
    })()""")
    t1 = page.evaluate("getComputedStyle(document.querySelector('.news-list')).transform")
    page.wait_for_timeout(1800)
    t2 = page.evaluate("getComputedStyle(document.querySelector('.news-list')).transform")
    check("모바일 뉴스가 흐르는 레일", css["display"] == "flex" and css["anim"] == "rail", "%s/%s" % (css["display"], css["anim"]))
    check("레일이 실제로 움직임", t1 != t2, "%s → %s" % (t1[:20], t2[:20]))
    check("섹션이 레일을 잘라냄", css["clip"] == "hidden", css["clip"])
    check("자바스크립트 오류 없음", not errors, "; ".join(errors)[:100])

    page.set_viewport_size({"width": 1440, "height": 1000})
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / ("thai-landing.png" if not LIVE else "thai-live-desktop.png")), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / ("thai-landing-mobile.png" if not LIVE else "thai-live-mobile.png")), full_page=True)

    # the deep link: the dashboard must arrive with the category already applied
    import page_build
    dash = page_build.render(public=False, datadir="", want_thai=True, icon_prefix="/",
                             admin=False, lang="ko", alt="../index.html", seed_html="")
    dash_url = "https://teemobkk.io/thai/news/ko/"
    deep = []
    page2 = browser.new_page(viewport={"width": 1440, "height": 1000})
    page2.on("request", lambda r: deep.append(r.url) if "/api/news?" in r.url else None)
    if not LIVE:
        page2.route(dash_url + "*", lambda r: r.fulfill(content_type="text/html", body=dash))
        page2.route("**/api/news?*", lambda r: r.fulfill(json=PAYLOAD))
    page2.goto(dash_url + "#cat=%EB%B9%84%EC%9E%90%C2%B7%EC%9D%B4%EB%AF%BC")
    page2.wait_for_timeout(3500)
    applied = any("category=" in u for u in deep)
    active = page2.evaluate("""(() => {
      const b = document.querySelector('#filters-thai button[data-cat].active');
      return b ? b.dataset.cat : "";
    })()""")
    check("분류 딥링크가 실제로 걸림", applied and active == "비자·이민",
          "%s · 활성 %s" % (("요청에 category 포함" if applied else "요청에 category 없음"), active))
    browser.close()

passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""))
print("\n  %d/%d" % (passed, len(results)))
sys.exit(0 if passed == len(results) else 1)
