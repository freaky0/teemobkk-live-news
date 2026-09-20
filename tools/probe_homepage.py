"""Check the typography layer and the phone rail on the homepage.

Playwright, headless, isolated profile. Runs the page's own template offline with a payload that
carries counts, so the checks do not depend on what the collector happens to hold right now.

Usage:  python tools/probe_homepage.py            (offline, deterministic)
        python tools/probe_homepage.py --live     (against https://teemobkk.io/)
"""
import json
import os
import sys
from pathlib import Path

if os.environ.get("HERMES_BROWSER_TOOLS"):
    sys.path.insert(0, os.environ["HERMES_BROWSER_TOOLS"])
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import landing

BASE = "https://teemobkk.io/"
LIVE = "--live" in sys.argv
OUT = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "shots"
OUT.mkdir(parents=True, exist_ok=True)

PAYLOAD = {
    "updated_at": "2026-09-20T02:30:00+00:00",
    "total": 1338,
    "region_counts": {"글로벌": 766, "태국": 572},
    # Distinct titles on purpose: the page drops items whose normalised title repeats, so a set
    # that differs only by a trailing publisher would collapse to one item and look like a bug.
    "articles": [
        {"title": "중 인민은행, %d일물 역RP %d억 위안 공급" % (7 + i, 320 + i), "region": "글로벌",
         "link": "https://example.com/%d" % i, "published_at": "2026-09-20T02:2%d:00+00:00" % i,
         "source": "CoinNess Stock", "category": "거시경제"} for i in range(6)
    ],
}

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    if not LIVE:
        page.route(BASE, lambda r: r.fulfill(content_type="text/html", body=landing.render_landing()))
        page.route("**/api/news?*", lambda r: r.fulfill(json=PAYLOAD))
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(2200)   # let the reveal animations land

    # headline: revealed, not stuck behind the mask
    h1 = page.evaluate("""(() => {
      const line = document.querySelector('h1 .rise > i');
      const cs = getComputedStyle(line);
      const box = line.getBoundingClientRect();
      return {transform: cs.transform, opacity: cs.opacity, height: Math.round(box.height),
              text: document.querySelector('h1').innerText.replace(/\\n/g,'')};
    })()""")
    check("제목이 마스크에서 내려옴", h1["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)"), h1["transform"])
    check("제목 줄이 실제 높이를 가짐", h1["height"] > 20, str(h1["height"]))
    check("제목 문구 유지", "경제 뉴스와 시장 관점" in h1["text"], h1["text"][:40])

    # hero motion
    rule = page.evaluate("getComputedStyle(document.querySelector('.hero-rule')).transform")
    check("히어로 라인이 그려짐", rule in ("none", "matrix(1, 0, 0, 1, 0, 0)"), rule)

    # live counts from the same endpoint (in live mode compare against what the API holds now)
    if LIVE:
        import urllib.request
        req = urllib.request.Request(BASE + "api/news?region=%EA%B8%80%EB%A1%9C%EB%B2%8C&hours=24&limit=1",
                                     headers={"User-Agent": "Mozilla/5.0"})
        now = json.loads(urllib.request.urlopen(req, timeout=30).read())
        want_total = "{:,}건".format(now["total"])
        want_thai = "{:,}건".format(now["region_counts"]["태국"])
    else:
        want_total, want_thai = "1,338건", "572건"
    check("통계가 API 값으로 채워짐",
          page.locator("#stat-total").inner_text() == want_total
          and page.locator("#stat-thai").inner_text() == want_thai,
          page.locator("#stat-total").inner_text() + " / " + page.locator("#stat-thai").inner_text()
          + " (기대 " + want_total + " / " + want_thai + ")")

    # oversized word band
    marq = page.evaluate("""(() => {
      const band = document.querySelector('.marq'), rail = band.querySelector('div');
      const cs = getComputedStyle(rail);
      return {anim: cs.animationName, w: Math.round(rail.scrollWidth), c: Math.round(band.clientWidth),
              overflow: getComputedStyle(band).overflow, words: band.querySelectorAll('span').length};
    })()""")
    check("아웃라인 활자 띠가 흐름", marq["anim"] == "drift" and marq["w"] > marq["c"],
          "%s · %dpx > %dpx · 단어 %d" % (marq["anim"], marq["w"], marq["c"], marq["words"]))
    check("띠가 페이지를 밀지 않음", marq["overflow"] == "hidden", marq["overflow"])

    # pointer layer exists and is inert
    check("포인터 라이트 (클릭 방해 없음)",
          page.evaluate("getComputedStyle(document.querySelector('.pointer-light')).pointerEvents") == "none")

    # widths
    for width in (320, 390, 768, 1024, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(120)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("가로 넘침 없음 @%d" % width, over <= 0, "%dpx" % over)

    # the phone rail: flex, animated, clipped by its section, and actually moving
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    rail1 = page.evaluate("getComputedStyle(document.querySelector('.news-list')).transform")
    rail_css = page.evaluate("""(() => {
      const list = document.querySelector('.news-list'), sec = document.querySelector('#news');
      const cs = getComputedStyle(list);
      const item = document.querySelector('.news-item').getBoundingClientRect();
      return {display: cs.display, anim: cs.animationName, clip: getComputedStyle(sec).overflow,
              itemW: Math.round(item.width), items: document.querySelectorAll('.news-item').length,
              overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth};
    })()""")
    page.wait_for_timeout(1800)
    rail2 = page.evaluate("getComputedStyle(document.querySelector('.news-list')).transform")
    check("모바일 뉴스가 흐르는 레일", rail_css["display"] == "flex" and rail_css["anim"] == "rail",
          "%s / %s" % (rail_css["display"], rail_css["anim"]))
    check("레일이 실제로 움직임", rail1 != rail2, "%s → %s" % (rail1[:22], rail2[:22]))
    check("섹션이 레일을 잘라냄", rail_css["clip"] == "hidden", rail_css["clip"])
    check("모바일에서도 넘침 없음", rail_css["overflow"] <= 0, "%dpx" % rail_css["overflow"])
    check("기사 6건 유지", rail_css["items"] == 6, str(rail_css["items"]))
    check("카드가 화면 폭 기준", 250 < rail_css["itemW"] < 340, "%dpx" % rail_css["itemW"])

    check("자바스크립트 오류 없음", not errors, "; ".join(errors)[:120])

    # screenshots
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / ("kinetic-desktop.png" if not LIVE else "kinetic-live-desktop.png")), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / ("kinetic-mobile.png" if not LIVE else "kinetic-live-mobile.png")), full_page=True)
    browser.close()

passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""))
print("\n  %d/%d" % (passed, len(results)))
print("  screenshots: %s" % OUT)
sys.exit(0 if passed == len(results) else 1)
