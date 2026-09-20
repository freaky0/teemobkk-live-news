"""Capture the keyword row as it now behaves: sideways on a phone, two keywords selected."""
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
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#trend .tbtn[data-trend]", timeout=30000)
    page.wait_for_timeout(1500)

    buttons = page.locator("#trend .tbtn[data-trend]")
    terms = [buttons.nth(0).get_attribute("data-trend"), buttons.nth(1).get_attribute("data-trend")]
    buttons.nth(0).click()
    page.wait_for_timeout(1800)
    buttons.nth(1).click()
    page.wait_for_timeout(3000)

    print("  선택한 낱말:", " + ".join(terms))
    print("  선택 표시:", page.locator("#trend .tbtn.on").count(), "개")
    print("  해제 버튼:", page.locator("#trend [data-trend-clear]").inner_text().strip())
    print("  카드:", page.locator("#feed .card").count(), "건")
    print("  상태줄:", (page.locator("#stamp").inner_text() if page.locator("#stamp").count() else "")[:70])

    page.locator("#trend").screenshot(path=str(OUT / "keywords-row-phone.png"))
    page.screenshot(path=str(OUT / "keywords-phone.png"), full_page=False)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(800)
    page.locator("#trend").screenshot(path=str(OUT / "keywords-row-desktop.png"))
    browser.close()

for name in ("keywords-row-phone.png", "keywords-phone.png", "keywords-row-desktop.png"):
    f = OUT / name
    print("  %-28s %d 바이트" % (name, f.stat().st_size))
