"""Add the kinetic type layer to the homepage, and make the news flow on phones.

The information structure, the fetch logic, the status strings and the filter behaviour are left
exactly as they are: the existing browser tests check all of those, and they must keep passing.
What is added is a typographic layer (masked line reveals, an oversized drifting word band, a
pointer light, hover sheen) and, on phones, a drifting news rail instead of six stacked items,
because that list is what forces the long scroll.

Nothing here may break: the headline text stays contiguous, the item count stays six, no string
handed to the tests changes, and no element may push the page sideways.
"""
import ast
import io

P = "C:/AI/Work_Folders/News_Macros/live_news_dashboard/landing.py"
text = io.open(P, encoding="utf-8").read()
before = text

CSS = """
/* ── kinetic layer ───────────────────────────────────────────────────────────
   The structure stays; the type carries the motion. Masked line reveals on load, an oversized
   drifting word band, a light that follows the pointer, and hover sheen on the cards. Nothing
   scroll-triggered: a full-page screenshot or a reader mid-scroll must never see a blank block. */
.pointer-light{position:fixed;inset:0;z-index:0;pointer-events:none;opacity:0;transition:opacity .6s;
  background:radial-gradient(340px circle at var(--px,50%) var(--py,20%),rgba(121,216,221,.10),transparent 68%)}
body{position:relative}
main,header,footer{position:relative;z-index:1}
.hero .eyebrow,.hero .intro,.hero .actions{opacity:0;transform:translateY(14px);
  animation:soft .9s cubic-bezier(.16,1,.3,1) forwards}
.hero .eyebrow{animation-delay:.05s}.hero .intro{animation-delay:.34s}.hero .actions{animation-delay:.5s}
@keyframes soft{to{opacity:1;transform:none}}
h1 span.rise{display:block;overflow:hidden}
h1 span.rise>i{display:block;font-style:normal;transform:translateY(112%);
  animation:maska 1.05s cubic-bezier(.16,1,.3,1) forwards}
h1 span.rise:nth-child(2)>i{animation-delay:.15s}
@keyframes maska{to{transform:translateY(0)}}
.hero-rule{height:1px;background:linear-gradient(90deg,var(--accent),transparent);margin:26px 0 0;
  transform:scaleX(0);transform-origin:0 50%;animation:draw 1.2s .45s cubic-bezier(.16,1,.3,1) forwards}
@keyframes draw{to{transform:scaleX(1)}}
.stats{display:flex;flex-wrap:wrap;gap:22px 46px;margin-top:30px;padding-top:20px;border-top:1px solid var(--line)}
.stat b{display:block;font-size:21px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat span{display:block;margin-top:4px;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.marq{position:relative;overflow:hidden;margin-top:44px;padding:14px 0;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 10%,#000 90%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 10%,#000 90%,transparent)}
.marq>div{display:flex;width:max-content;animation:drift 46s linear infinite}
.marq span{font-size:clamp(26px,5.2vw,56px);font-weight:800;letter-spacing:-.045em;white-space:nowrap;
  padding-right:.5em;color:transparent;-webkit-text-stroke:1px rgba(237,242,247,.22)}
@keyframes drift{to{transform:translateX(-50%)}}
.section>h2{position:relative}
.section>h2::after{content:"";position:absolute;left:0;bottom:-7px;width:34px;height:2px;
  background:var(--accent);opacity:.7}
.news-item,.post,.chart-open{transition:border-color .35s,box-shadow .5s,background .35s,
  transform .5s cubic-bezier(.16,1,.3,1)}
.news-item:hover{transform:translateX(4px)}
.post:hover,.chart-open:hover{border-color:rgba(121,216,221,.5);transform:translateY(-4px);
  box-shadow:0 22px 50px -30px rgba(121,216,221,.65)}

/* Phones: a drifting rail instead of six stacked items. The list was the reason for the long
   scroll. The section clips it, so the page itself never moves sideways. */
@media(max-width:767px){
  #news{overflow:hidden}
  .news-list{display:flex;grid-template-columns:none;gap:13px;width:max-content;align-items:stretch;
    animation:rail 42s ease-in-out infinite alternate}
  .news-item{flex:0 0 76vw;padding:17px 18px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--radius)}
  .news-item:hover{transform:none}
  .news-list:hover,.news-list:active,.news-list:focus-within{animation-play-state:paused}
  @keyframes rail{from{transform:translateX(0)}to{transform:translateX(calc(-100% + 100vw - 40px))}}
  .stats{gap:18px 26px}.stat b{font-size:19px}
  .marq{margin-top:30px}
}
@media(prefers-reduced-motion:reduce){
  .pointer-light{display:none}
  h1 span.rise>i,.hero .eyebrow,.hero .intro,.hero .actions{animation:none;opacity:1;transform:none}
  .hero-rule{animation:none;transform:scaleX(1)}
  .marq>div{animation:none}
  .news-list{animation:none;width:auto;overflow-x:auto}
}
</style>"""

STATS = """<div class="hero-rule"></div>
<div class="stats">
<div class="stat"><b id="stat-total">&mdash;</b><span>&#52572;&#44540; 24&#49884;&#44036; &#49688;&#51665;</span></div>
<div class="stat"><b id="stat-thai">&mdash;</b><span>&#44536;&#51473; &#53468;&#44397; &#49548;&#49885;</span></div>
<div class="stat"><b>2&#48516;</b><span>&#51088;&#46041; &#44081;&#49888;</span></div>
</div>"""

MARQ = """<div class="marq" aria-hidden="true"><div>
<span>ECONOMIC NEWS</span><span>MARKET PERSPECTIVES</span><span>TRADINGVIEW INDICATORS</span><span>BANGKOK</span>
<span>ECONOMIC NEWS</span><span>MARKET PERSPECTIVES</span><span>TRADINGVIEW INDICATORS</span><span>BANGKOK</span>
</div></div>"""

SCRIPT = """<script>
(function(){
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // A light that follows the pointer, where a real pointer exists. Above the content, below the
  // dialog, and hidden from assistive tech.
  if (!reduce && window.matchMedia("(hover:hover) and (pointer:fine)").matches){
    var light = document.querySelector(".pointer-light"), raf = 0, tx = 0, ty = 0, cx = 0, cy = 0;
    window.addEventListener("pointermove", function(e){
      tx = e.clientX; ty = e.clientY; light.style.opacity = "1";
      if (!raf) raf = requestAnimationFrame(glide);
    }, {passive:true});
    var glide = function(){
      cx += (tx - cx) * .09; cy += (ty - cy) * .09;
      light.style.setProperty("--px", cx + "px");
      light.style.setProperty("--py", cy + "px");
      raf = (Math.abs(tx - cx) > .5 || Math.abs(ty - cy) > .5) ? requestAnimationFrame(glide) : 0;
    };
  }

  // The counts come from the same endpoint the list uses, one row at a time, so the strip shows
  // what the collector actually holds rather than a number kept in two places. Missing fields
  // leave the dash in place: this must never throw, the page's own status line reports health.
  function paint(data){
    if (!data || typeof data !== "object") return;
    var set = function(id, value){
      var el = document.getElementById(id);
      if (el && typeof value === "number") el.textContent = value.toLocaleString("en-US") + "\\uac74";
    };
    set("stat-total", data.total);
    set("stat-thai", data.region_counts && data.region_counts["\\ud0dc\\uad6d"]);
  }
  function counts(){
    fetch("/api/news?region=" + encodeURIComponent("\\uae00\\ub85c\\ubc8c") + "&hours=24&limit=1", {cache:"no-cache"})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(paint)
      .catch(function(){});
  }
  counts();
  setInterval(function(){ if (!document.hidden) counts(); }, 120000);
})();
</script>
</body>"""

replacements = [
    # the stylesheet
    ("</style>", CSS),
    # the headline: each line masked, text unchanged and contiguous for the existing test
    ('<h1 id="headline"><span>트레이딩을 위한</span>경제 뉴스와 시장 관점</h1>',
     '<h1 id="headline"><span class="rise"><i>트레이딩을 위한</i></span>'
     '<span class="rise"><i>경제 뉴스와 시장 관점</i></span></h1>'),
    # the live strip at the foot of the hero
    ('<a class="button" href="#perspectives">시장 관점 읽기</a></div></section>',
     '<a class="button" href="#perspectives">시장 관점 읽기</a></div>' + STATS + '</section>'),
    # the drifting word band, between the hero and the news
    ('<section class="section" id="news"', MARQ + '\n<section class="section" id="news"'),
    # the pointer layer, and the small script that feeds the strip
    ('<body>\n<a class="skip"', '<body>\n<div class="pointer-light" aria-hidden="true"></div>\n<a class="skip"'),
    ("</body>\n</html>", SCRIPT + "\n</html>"),
]

for old, new in replacements:
    if old not in text:
        print("  MISS: %s" % old[:70].replace("\n", " "))
        continue
    text = text.replace(old, new, 1)

io.open(P, "w", encoding="utf-8", newline="").write(text)
ast.parse(io.open(P, encoding="utf-8").read())
print("  landing.py rewritten (%d -> %d chars); ast OK" % (len(before), len(text)))

check = io.open(P, encoding="utf-8").read()
for name, needle in (("hero rise", 'class="rise"'), ("hero rule", "hero-rule"),
                     ("stats strip", 'id="stat-total"'), ("marquee", 'class="marq"'),
                     ("pointer light", "pointer-light"), ("mobile rail", "@keyframes rail"),
                     ("reduced motion", ".marq>div{animation:none}"),
                     ("headline intact", "경제 뉴스와 시장 관점")):
    print("  %s %s" % ("OK  " if needle in check else "MISS", name))
print("  broken jamo: %d" % len([c for c in check if 0x1100 <= ord(c) <= 0x11FF]))
