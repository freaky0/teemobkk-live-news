"""Measure the keyword row in a real browser: does the label overlap, is the selected chip filled
without hovering, and do categories and keywords actually travel together."""
import os
import re
import sys
import urllib.parse

if os.environ.get("HERMES_BROWSER_TOOLS"):
    sys.path.insert(0, os.environ["HERMES_BROWSER_TOOLS"])
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
def _cat(u):
    m = re.search(r"[?&]category=([^&]*)", u)
    return urllib.parse.unquote_plus(m.group(1)) if m else ""


ok = []


def check(name, good, detail=""):
    ok.append(bool(good))
    print("  %s %s%s" % ("PASS" if good else "FAIL", name, ("  (%s)" % detail) if detail else ""))


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                          headless=True)
    page = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if "/api/news?" in r.url else None)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#trend .tbtn[data-trend]", timeout=30000)
    page.wait_for_timeout(1500)

    # 1. the label and the scrolling track are separate boxes: the buttons cannot pass under it
    geo = page.evaluate("""() => {
      const row=document.querySelector('#trend'), lab=row.querySelector('.tlabel'),
            trk=row.querySelector('.ttrack');
      const R=e=>{const r=e.getBoundingClientRect();return [Math.round(r.x),Math.round(r.y),
                                                       Math.round(r.width),Math.round(r.height)]};
      return {label:R(lab), track:R(trk), scrolls:trk.scrollWidth>trk.clientWidth,
              rowOverflow:getComputedStyle(row).overflowX, trackOverflow:getComputedStyle(trk).overflowX};
    }""")
    check("라벨과 트랙이 다른 상자", geo["label"][0] + geo["label"][2] <= geo["track"][0] + 1,
          "라벨 끝 %d ≤ 트랙 시작 %d" % (geo["label"][0] + geo["label"][2], geo["track"][0]))
    check("트랙이 옆으로 흐름", geo["scrolls"] and geo["trackOverflow"] == "auto", geo["trackOverflow"])

    page.evaluate("document.querySelector('#trend .ttrack').scrollLeft = 260")
    page.wait_for_timeout(250)
    clip = page.evaluate("""() => {
      const lab=document.querySelector('#trend .tlabel'), trk=document.querySelector('#trend .ttrack');
      const L=lab.getBoundingClientRect(), T=trk.getBoundingClientRect();
      return {gap:T.left-L.right, clip:getComputedStyle(trk).overflowX, parent:lab.parentElement===trk.parentElement,
              same:lab.parentElement===trk};
    }""")
    check("라벨은 스크롤 상자의 형제 (버튼이 위로 지나갈 수 없음)",
          clip["same"] is False and clip["parent"] and clip["clip"] != "visible",
          "간격 %.0fpx · 트랙 %s" % (clip["gap"], clip["clip"]))

    # 2. the selected chip must be filled, with the pointer nowhere near it
    page.mouse.move(2, 2)
    page.wait_for_timeout(200)
    btns = page.locator("#trend .tbtn[data-trend]")
    btns.nth(0).click()
    page.wait_for_timeout(2200)
    page.mouse.move(2, 2)
    page.wait_for_timeout(400)
    sel = page.evaluate("""() => {
      const on=document.querySelector('#trend .tbtn.on'), off=[...document.querySelectorAll('#trend .tbtn[data-trend]')]
        .find(x=>!x.classList.contains('on'));
      const g=e=>{const s=getComputedStyle(e);return {bg:s.backgroundColor,border:s.borderColor,
                                                     color:s.color,w:s.fontWeight}};
      return {on:g(on), off:g(off)};
    }""")
    check("선택한 키워드가 채워짐 (호버 없이)", sel["on"]["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"),
          sel["on"]["bg"])
    check("선택 표시가 선택 안 된 것과 뚜렷이 다름",
          sel["on"]["bg"] != sel["off"]["bg"] and sel["on"]["border"] != sel["off"]["border"],
          "선택 %s / 미선택 %s" % (sel["on"]["bg"], sel["off"]["bg"]))

    # 3. categories multi-select, and they compose with keywords
    page.set_viewport_size({"width": 1200, "height": 1000})
    page.wait_for_timeout(600)
    rows = page.evaluate("""() => [...document.querySelectorAll('#filters-global,#filters-thai')]
        .filter(r=>!r.hidden).map(r=>'#'+r.id)""")
    print("      알약 줄: %s" % (rows[0] if rows else "없음"))
    pills = page.locator("%s button[data-cat]" % rows[0])
    names = [pills.nth(i).get_attribute("data-cat") for i in range(3)]
    c1, c2 = names[1], names[2]
    reqs.clear()
    pills.nth(1).click()
    page.wait_for_timeout(1800)
    pills.nth(2).click()
    page.wait_for_timeout(2200)
    active = page.evaluate("""() => [...document.querySelectorAll(
        '#filters-global button[data-cat].active,#filters-thai button[data-cat].active')]
        .map(b=>b.dataset.cat)""")
    check("분류 두 개를 함께 고를 수 있음", len(active) == 2 and c1 in active and c2 in active,
          " + ".join(active))
    cat2 = [u for u in reqs if "category=" in u]
    check("분류마다 따로 조회", len(cat2) >= 2, "%d건" % len(cat2))
    check("두 분류가 각각 조회됨", all(any(_cat(u) == c for u in cat2) for c in (c1, c2)),
          ", ".join(sorted({_cat(u) for u in cat2})))

    reqs.clear()
    page.locator("#trend .tbtn[data-trend]").nth(1).click()
    page.wait_for_timeout(3000)
    combo = [u for u in reqs if "category=" in u and "q=" in u]
    want = len(page.evaluate("window.V.cats")) * len(page.evaluate("window.V.terms"))
    check("분류 + 키워드가 한 요청에 함께 실림 (조합마다 하나)", len(combo) == want,
          "%d건 (기대 %d)" % (len(combo), want))
    if combo:
        print("      예: %s" % combo[0].split("?")[1][:110])
    state = page.evaluate("""() => ({cats:window.V.cats, terms:window.V.terms,
                                     pills:[...document.querySelectorAll('#filters-global button[data-cat].active,#filters-thai button[data-cat].active')]
                                       .map(b=>b.dataset.cat),
                                     on:[...document.querySelectorAll('#trend .tbtn.on[data-trend]')]
                                       .map(b=>b.dataset.trend)})""")
    check("화면 상태가 둘 다 유지됨",
          len(state["pills"]) == 2 and len(state["on"]) == len(state["terms"]) and state["cats"] and state["terms"],
          "분류 %s · 키워드 %s" % (state["pills"], state["on"]))

    # 4. 전체 is still the one control that clears everything
    reqs.clear()
    page.locator("%s button[data-cat]" % rows[0]).first.click()
    page.wait_for_timeout(2500)
    cleared = page.evaluate("""() => ({cats:window.V.cats, terms:window.V.terms,
                                       box:(document.querySelector('#q')||{}).value,
                                       pills:document.querySelectorAll('#filters-global button[data-cat].active,#filters-thai button[data-cat].active').length,
                                       on:document.querySelectorAll('#trend .tbtn.on[data-trend]').length})""")
    check("전체를 누르면 분류·키워드·검색어가 모두 풀림",
          cleared["cats"] == [] and cleared["terms"] == [] and (cleared["box"] or "") == "",
          "분류 %s · 키워드 %s" % (cleared["cats"], cleared["terms"]))
    check("전체 뒤에는 분류 알약도 선택 표시가 없음", cleared["pills"] == 1, "%d개 활성" % cleared["pills"])
    b.close()

print("\n  %d/%d" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
