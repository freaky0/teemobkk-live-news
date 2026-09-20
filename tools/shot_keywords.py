"""Capture the keyword row as it is now: the label with the track scrolled right under it, and a
category plus two keywords selected together."""
import os
import sys
from pathlib import Path

if os.environ.get("HERMES_BROWSER_TOOLS"):
    sys.path.insert(0, os.environ["HERMES_BROWSER_TOOLS"])
from playwright.sync_api import sync_playwright

OUT = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
URL = sys.argv[1] if len(sys.argv) > 1 else "https://teemobkk.io/news/ko/"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                          headless=True)
    page = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#trend .tbtn[data-trend]", timeout=30000)
    page.wait_for_timeout(1500)

    page.evaluate("document.querySelector('#trend .ttrack').scrollLeft = 300")
    page.mouse.move(2, 2)
    page.wait_for_timeout(400)
    page.locator("#trend").screenshot(path=str(OUT / "kw-label-scrolled.png"))

    page.evaluate("document.querySelector('#trend .ttrack').scrollLeft = 0")
    page.locator("#filters-global button[data-cat]").nth(3).click()
    page.wait_for_timeout(2000)
    btns = page.locator("#trend .tbtn[data-trend]")
    btns.nth(0).click()
    page.wait_for_timeout(2000)
    btns.nth(1).click()
    page.wait_for_timeout(2600)
    page.mouse.move(2, 2)
    page.wait_for_timeout(300)
    state = page.evaluate("""() => ({cats:window.V.cats, terms:window.V.terms,
      pills:[...document.querySelectorAll('#filters-global button[data-cat].active')].map(b=>b.textContent),
      on:[...document.querySelectorAll('#trend .tbtn.on[data-trend]')].map(b=>b.textContent.trim()),
      cards:document.querySelectorAll('#feed .card').length})""")
    print("  분류 %s · 키워드 %s · 카드 %d건" % (state["pills"], state["on"], state["cards"]))
    page.locator("#trend").screenshot(path=str(OUT / "kw-row-selected.png"))
    page.locator("#filters-global").screenshot(path=str(OUT / "kw-cats-selected.png"))
    page.screenshot(path=str(OUT / "kw-phone.png"))
    b.close()

for name in ("kw-label-scrolled.png", "kw-row-selected.png", "kw-cats-selected.png", "kw-phone.png"):
    print("  %-26s %d 바이트" % (name, (OUT / name).stat().st_size))
