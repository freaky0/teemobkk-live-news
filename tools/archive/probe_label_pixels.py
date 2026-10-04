"""Pixel proof that nothing from the keyword track is painted over the label.

If a pill were sliding under the label, the label's own pixels would change as the track scrolls.
Capture the label's box at two scroll positions and compare the bytes.
"""
import hashlib
import os
import sys
from pathlib import Path

if os.environ.get("HERMES_BROWSER_TOOLS"):
    sys.path.insert(0, os.environ["HERMES_BROWSER_TOOLS"])
from playwright.sync_api import sync_playwright

OUT = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "shots"
URL = sys.argv[1] if len(sys.argv) > 1 else "https://teemobkk.io/news/ko/"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                          headless=True)
    page = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#trend .tbtn[data-trend]", timeout=30000)
    page.wait_for_timeout(1500)
    page.mouse.move(2, 2)

    shots = {}
    for name, left in (("start", 0), ("scrolled", 300), ("far", 600)):
        page.evaluate("document.querySelector('#trend .ttrack').scrollLeft = %d" % left)
        page.wait_for_timeout(500)
        f = OUT / ("label-%s.png" % name)
        page.locator("#trend .tlabel").screenshot(path=str(f))
        shots[name] = digest(f)
        print("  라벨 %-9s 스크롤 %3dpx → %s" % (name, left, shots[name]))

    # and the whole row, to show what does move
    for name, left in (("start", 0), ("scrolled", 300)):
        page.evaluate("document.querySelector('#trend .ttrack').scrollLeft = %d" % left)
        page.wait_for_timeout(400)
        f = OUT / ("row-%s.png" % name)
        page.locator("#trend").screenshot(path=str(f))
        print("  줄   %-9s 스크롤 %3dpx → %s" % (name, left, digest(f)))
    b.close()

same = len(set(shots.values())) == 1
print("\n  %s 라벨 픽셀이 스크롤과 무관하게 동일 (버튼이 위로 지나가지 않음)"
      % ("PASS" if same else "FAIL"))
sys.exit(0 if same else 1)
