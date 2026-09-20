"""Measure the keyword row as the browser actually lays it out, and watch the selection state.

Reading the source is not enough here: the reported faults are geometric (the label and the buttons
overlapping) and temporal (a selection marker that does not survive a refresh).
"""
import os
import sys

if os.environ.get("HERMES_BROWSER_TOOLS"):
    sys.path.insert(0, os.environ["HERMES_BROWSER_TOOLS"])
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://teemobkk.io/news/ko/"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                          headless=True)
    page = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if "/api/news?" in r.url else None)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#trend .tbtn[data-trend]", timeout=30000)
    page.wait_for_timeout(1200)

    geo = page.evaluate("""() => {
      const row=document.querySelector('#trend'), lab=row.querySelector('.tlabel'),
            btn=row.querySelector('.tbtn[data-trend]');
      const R=e=>e.getBoundingClientRect();
      return {row:[R(row).x,R(row).y,R(row).width,R(row).height],
              label:[R(lab).x,R(lab).y,R(lab).width,R(lab).height],
              btn:[R(btn).x,R(btn).y,R(btn).width,R(btn).height],
              rowScroll:{w:row.scrollWidth,cw:row.clientWidth,ox:row.scrollLeft},
              labelPos:getComputedStyle(lab).position, labelBg:getComputedStyle(lab).backgroundColor,
              labelZ:getComputedStyle(lab).zIndex,
              rowOverflow:getComputedStyle(row).overflowX,
              labelDisplay:getComputedStyle(lab).display, labelAlign:getComputedStyle(lab).alignSelf};
    }""")
    print("  줄     x=%.0f y=%.0f w=%.0f h=%.0f" % tuple(geo["row"]))
    print("  라벨   x=%.0f y=%.0f w=%.0f h=%.0f   position=%s  bg=%s  z=%s  align-self=%s"
          % (tuple(geo["label"]) + (geo["labelPos"], geo["labelBg"], geo["labelZ"], geo["labelAlign"])))
    print("  첫 버튼 x=%.0f y=%.0f w=%.0f h=%.0f" % tuple(geo["btn"]))
    print("  스크롤 w=%d / 보이는 폭 %d · overflow-x=%s" % (geo["rowScroll"]["w"], geo["rowScroll"]["cw"], geo["rowOverflow"]))
    print("  → 라벨이 버튼보다 낮은가: %s (라벨 %.0fpx vs 버튼 %.0fpx)"
          % ("예 — 겹침 원인" if geo["label"][3] < geo["btn"][3] else "아니오",
             geo["label"][3], geo["btn"][3]))

    # does the label sit on top of the buttons while the row is scrolled?
    page.evaluate("document.querySelector('#trend').scrollLeft = 160")
    page.wait_for_timeout(300)
    overlap = page.evaluate("""() => {
      const row=document.querySelector('#trend'), lab=row.querySelector('.tlabel');
      const L=lab.getBoundingClientRect();
      const under=[...row.querySelectorAll('.tbtn[data-trend]')].map(b=>b.getBoundingClientRect())
        .filter(r=>r.right>L.left+2 && r.left<L.right-2)
        .map(r=>[Math.round(r.left),Math.round(r.right)]);
      return {label:[Math.round(L.left),Math.round(L.right)], under};
    }""")
    print("  스크롤 160px 후 라벨 아래를 지나는 버튼: %s" % (overlap["under"] or "없음"))

    b.close()

    # selection persistence: click two keywords, then watch for two refresh cycles
    b = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                          headless=True)
    page = b.new_page(viewport={"width": 900, "height": 900})
    reqs2 = []
    page.on("request", lambda r: reqs2.append(r.url) if "/api/news?" in r.url else None)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#trend .tbtn[data-trend]", timeout=30000)
    page.wait_for_timeout(1200)
    btns = page.locator("#trend .tbtn[data-trend]")
    t1 = btns.nth(0).get_attribute("data-trend")
    btns.nth(0).click()
    page.wait_for_timeout(2500)
    state = page.evaluate("""() => {
      const b=document.querySelector('#trend .tbtn.on');
      const s=getComputedStyle(b);
      return {cls:b.className, border:s.borderColor, color:s.color, bg:s.backgroundColor,
              aria:b.getAttribute('aria-pressed'), dom:document.querySelectorAll('#trend .tbtn.on').length};
    }""")
    print()
    print("  선택 1개 — class=%s aria=%s border=%s color=%s bg=%s"
          % (state["cls"], state["aria"], state["border"], state["color"], state["bg"]))
    btns.nth(1).click()
    page.wait_for_timeout(2500)
    print("  키워드 2개 선택 — .on 개수=%d · V.terms=%s"
          % (page.evaluate("document.querySelectorAll('#trend .tbtn.on').length"), page.evaluate("window.V.terms")))

    print()
    print("  60초 관찰 (갱신 주기 1회 이상):")
    for i in range(6):
        page.wait_for_timeout(10000)
        s = page.evaluate("""() => ({on:document.querySelectorAll('#trend .tbtn.on').length,
                                     terms:JSON.stringify(window.V.terms),
                                     aria:[...document.querySelectorAll('#trend .tbtn[data-trend]')]
                                          .filter(b=>b.getAttribute('aria-pressed')==='true').length,
                                     cards:document.querySelectorAll('#feed .card').length})""")
        print("    %2ds  on=%d  aria=%d  V.terms=%s  카드=%d"
              % ((i + 1) * 10, s["on"], s["aria"], s["terms"], s["cards"]))
    print("  이 구간의 /api/news 요청 %d건" % len(reqs2))
    for u in reqs2[-3:]:
        params = [x for x in u.split("?")[1].split("&") if x.split("=")[0] in ("q", "category", "limit", "offset")]
        print("    %s" % "&".join(params))
    b.close()
