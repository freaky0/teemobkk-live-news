"""Measure a deployed page's layout at phone, tablet and desktop widths.

Usage:  python tools/measure_page.py [url]

A window cannot be narrower than about 492px on Windows, and the device-scale flag does not
shrink the CSS viewport, so each width is measured inside an iframe of exactly that width - vw
units and media queries resolve against the frame, which is what a phone gives the page anyway.

The vision provider that would have let a human look at the render is unavailable, so this covers
what a look would have caught: horizontal overflow, elements escaping the frame, type sizes and
block heights. The data strips are laid out with a stubbed payload so they are present.
"""
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WORK = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "shots")
URL = sys.argv[1] if len(sys.argv) > 1 else "https://teemobkk.io/"
SIZES = (("phone", 390, 844), ("tablet", 768, 1024), ("desktop", 1440, 1000))

STUB = """<script>
window.fetch = function(){
  var items = [];
  for (var i = 0; i < 8; i++){
    items.push({title: "\uc911 \uc778\ubbfc\uc740\ud589, 7\uc77c\ubb3c \uc5edRP 320\uc5b5 \uc704\uc548 \uacf5\uae09 / China central bank injects liquidity " + i,
                source: "CoinNess Stock"});
  }
  return Promise.resolve({ok: true, json: function(){ return Promise.resolve({
    total: 1338, region_counts: {"\ud0dc\uad6d": 572},
    updated_at_ict: "2026-09-20 08:26 ICT", articles: items}); }});
};
</script>
"""

PROBE = """<script>
setTimeout(function(){
  var W = window.innerWidth, H = window.innerHeight;
  var out = {vw: W, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, blocks: [], escape: []};
  function rec(sel, name){
    var el = document.querySelector(sel);
    if (!el) { out.blocks.push({name: name, missing: true}); return; }
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    out.blocks.push({name: name, x: Math.round(r.x), w: Math.round(r.width), right: Math.round(r.right),
                     h: Math.round(r.height), font: cs.fontSize, weight: cs.fontWeight});
  }
  [["h1","h1"],["h1 .ln>span","h1 line 1"],["#main .sub",".sub"],["#stats","stats"],
   ["#tick","ticker"],["#tick .rail div","ticker rail"],["#s-window","stat number"],
   [".sect","section label"],["#main .cards","cards grid"],["#main .card","card 1"],
   ["#main .card h3","card title"],[".marq","marquee"],[".marq span","marquee word"],["footer","footer"]]
   .forEach(function(p){ rec(p[0], p[1]); });

  // Anything sticking out of the frame, ignoring what legitimately runs off the edge: fixed and
  // absolutely positioned layers, and anything inside a clipping ancestor (the marquee).
  function clipped(el){
    for (var n = el.parentElement; n; n = n.parentElement){
      var cs = getComputedStyle(n);
      if (cs.overflowX === "hidden" || cs.overflow === "hidden") return true;
    }
    return false;
  }
  Array.prototype.slice.call(document.querySelectorAll("body *")).forEach(function(el){
    var cs = getComputedStyle(el);
    if (cs.position === "fixed" || cs.position === "absolute") return;
    var r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > W + 1 || r.left < -1) && !clipped(el)){
      out.escape.push((el.className || el.tagName) + " [" + Math.round(r.left) + ".." + Math.round(r.right) + "]");
    }
  });
  out.escape = out.escape.slice(0, 8);
  (window.parent === window ? function(){ var p = document.createElement("pre"); p.id = "probe"; p.textContent = JSON.stringify(out); document.body.appendChild(p); }()
                            : function(){ window.parent.postMessage(JSON.stringify(out), "*"); }());
}, 2600);
</script>
"""


def fetch_page():
    return urllib.request.urlopen(URL, timeout=30).read().decode("utf-8")


def write(name, text):
    path = os.path.join(WORK, name)
    io.open(path, "w", encoding="utf-8", newline="").write(text)
    return path.replace("\\", "/")


page = fetch_page()
results = {}
for label, width, height in SIZES:
    frame = page.replace("<title>", STUB + "<title>", 1).replace("</body>", PROBE + "</body>", 1)
    frame_path = write("frame-%s.html" % label, frame)
    wrapper = """<!doctype html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#222">
<iframe src="%s" style="width:%dpx;height:%dpx;border:0;display:block" scrolling="no"></iframe>
<pre id="out">waiting</pre>
<script>
window.addEventListener("message", function(e){ document.getElementById("out").textContent = e.data; });
</script></body></html>""" % (os.path.basename(frame_path), width, height)
    wrapper_path = write("wrap-%s.html" % label, wrapper)
    dom = subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                          "--allow-file-access-from-files",
                          "--virtual-time-budget=12000", "--window-size=1500,1200",
                          "--dump-dom", "file:///" + wrapper_path],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    match = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not match or match.group(1).strip() == "waiting":
        print("── %-8s 측정 실패" % label)
        continue
    raw = match.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    results[label] = json.loads(raw)

for label, width, height in SIZES:
    data = results.get(label)
    print("── %s (%dpx)" % (label, width))
    if not data:
        continue
    print("   뷰포트 %d · 가로 넘침 %dpx · 프레임 밖 요소: %s"
          % (data["vw"], data["overflow"], data["escape"] or "없음"))
    for b in data["blocks"]:
        if b.get("missing"):
            print("   %-14s (없음)" % b["name"])
        else:
            print("   %-14s x=%-5d w=%-5d right=%-5d h=%-4d %s / %s"
                  % (b["name"], b["x"], b["w"], b["right"], b["h"], b["font"], b["weight"]))
    print()
