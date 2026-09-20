"""The site's front page.

Kept apart from page_build because it shares nothing with the dashboard: no tabs, no feed, no
filters. It is a typographic index that states what the domain carries and points at each part.
The only live piece is a small stats strip and a headline ticker, read from the same /api/news
the dashboards use, so the page is never stale and shows nothing an operator sees.
"""

PAGE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK - 시장과 생활을 한 곳에서</title>
<meta name="description" content="방콕에서 보는 비트코인·매크로 뉴스, 태국 소식, 트레이딩뷰 지표. 수집한 기사를 한 화면에 모읍니다.">
<meta name="theme-color" content="#05070d">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="canonical" href="https://teemobkk.io/">
<style>
*,*::before,*::after{box-sizing:border-box}
:root{
  --ink:#05070d;--ink2:#0a0f1a;--text:#eef3ff;--muted:#8b9bbd;
  --line:rgba(255,255,255,.09);--accent:#64d7ff;--amber:#ffd479;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"Malgun Gothic","Apple SD Gothic Neo",Roboto,sans-serif;
}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ink);color:var(--text);font-family:var(--sans);
  letter-spacing:-.011em;-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit;text-decoration:none}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:6px}
.skip{position:absolute;left:-9999px}
.skip:focus{left:12px;top:12px;z-index:99;background:var(--accent);color:#04121a;padding:8px 14px;border-radius:8px;font-size:13px}

/* two backgrounds: a slow drifting light, and film grain for texture */
.glow{position:fixed;inset:-25% -12%;z-index:0;pointer-events:none;
  background:
    radial-gradient(36% 30% at 20% 16%,rgba(100,215,255,.17),transparent 62%),
    radial-gradient(32% 28% at 80% 10%,rgba(255,212,121,.10),transparent 60%),
    radial-gradient(44% 38% at 56% 96%,rgba(100,215,255,.08),transparent 66%);
  filter:blur(26px);animation:drift 24s ease-in-out infinite alternate}
@keyframes drift{from{transform:translate3d(-2%,-1%,0) scale(1)}to{transform:translate3d(3%,2%,0) scale(1.07)}}
.grain{position:fixed;inset:0;z-index:1;pointer-events:none;opacity:.045;mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.82' numOctaves='3'/></filter><rect width='140' height='140' filter='url(%23n)'/></svg>")}
.spot{position:fixed;inset:0;z-index:1;pointer-events:none;opacity:0;transition:opacity .5s;
  background:radial-gradient(320px circle at var(--px,50%) var(--py,30%),rgba(100,215,255,.09),transparent 70%)}

.wrap{position:relative;z-index:2;max-width:1080px;margin:0 auto;padding:0 clamp(20px,5vw,40px)}

/* top bar */
.top{position:sticky;top:0;z-index:30;display:flex;align-items:center;justify-content:space-between;
  gap:16px;padding:15px clamp(20px,5vw,40px);
  background:linear-gradient(180deg,rgba(5,7,13,.92),rgba(5,7,13,.55));backdrop-filter:blur(14px);
  border-bottom:1px solid var(--line)}
.mark{font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase;white-space:nowrap}
.mark i{font-style:normal;color:var(--accent)}
.live{display:flex;align-items:center;gap:9px;font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);white-space:nowrap}
.live b{color:var(--text);font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:.06em}
.dot{width:6px;height:6px;border-radius:50%;background:var(--accent);animation:pulse 2.6s ease-out infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(100,215,255,.5)}70%{box-shadow:0 0 0 8px rgba(100,215,255,0)}100%{box-shadow:0 0 0 0 rgba(100,215,255,0)}}

/* hero */
.hero{padding:clamp(54px,13vh,132px) 0 0}
.kick{margin:0 0 18px;font-size:10.5px;letter-spacing:.3em;text-transform:uppercase;color:var(--accent)}
.kick u{text-decoration:none;color:var(--muted)}
h1{margin:0;font-weight:800;letter-spacing:-.038em;line-height:.97;font-size:clamp(2.35rem,8.6vw,5.3rem)}
h1 .ln{display:block;overflow:hidden;padding:.02em 0 .05em}
h1 .ln>span{display:block;transform:translateY(115%);animation:rise .95s cubic-bezier(.16,1,.3,1) both}
h1 .ln:nth-child(2)>span{animation-delay:.13s}
@keyframes rise{to{transform:translateY(0)}}
h1 .thin{color:transparent;-webkit-text-stroke:1.2px rgba(238,243,255,.62)}
.rule{height:1px;background:var(--line);margin:26px 0 0;transform:scaleX(0);transform-origin:0 50%;
  animation:draw 1.1s .42s cubic-bezier(.16,1,.3,1) forwards}
@keyframes draw{to{transform:scaleX(1)}}
.sub{margin:22px 0 0;max-width:58ch;color:var(--muted);font-size:clamp(13.5px,1.55vw,15.5px);line-height:1.85}

/* live strip */
.stats{display:flex;flex-wrap:wrap;gap:clamp(20px,4vw,44px);margin:34px 0 0;padding:20px 0 0;border-top:1px solid var(--line)}
.stat b{display:block;font-size:clamp(20px,2.6vw,26px);font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.stat span{display:block;margin-top:5px;font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted)}
.tick{display:flex;align-items:center;gap:14px;margin:26px 0 0;padding:11px 16px;border:1px solid var(--line);
  border-radius:999px;background:rgba(255,255,255,.022);overflow:hidden}
.tick em{flex:0 0 auto;font-style:normal;font-size:9.5px;letter-spacing:.22em;text-transform:uppercase;color:var(--amber)}
.tick .rail{overflow:hidden;min-width:0}
.tick .rail div{display:flex;gap:36px;width:max-content;white-space:nowrap;animation:slide 72s linear infinite}
.tick .rail span{font-size:13px;color:var(--muted)}
.tick .rail span b{color:var(--text);font-weight:500}
@keyframes slide{to{transform:translateX(-50%)}}

/* destinations */
.sect{margin:clamp(52px,9vh,86px) 0 16px;font-size:10.5px;letter-spacing:.3em;text-transform:uppercase;color:var(--muted);font-weight:600}
.cards{display:grid;gap:13px;grid-template-columns:repeat(auto-fit,minmax(238px,1fr))}
.card{position:relative;display:flex;flex-direction:column;gap:9px;overflow:hidden;
  padding:22px 20px 18px;border:1px solid var(--line);border-radius:16px;
  background:linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.012));
  opacity:0;transform:translateY(18px)}
.card.in{opacity:1;transform:none;transition:opacity .7s cubic-bezier(.16,1,.3,1),transform .7s cubic-bezier(.16,1,.3,1),
  border-color .35s,box-shadow .45s}
.card::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(112deg,transparent 32%,rgba(100,215,255,.14) 50%,transparent 68%);
  transform:translateX(-130%);transition:transform .85s cubic-bezier(.16,1,.3,1)}
.card:hover{transform:translateY(-5px);border-color:rgba(100,215,255,.42);box-shadow:0 22px 55px -26px rgba(100,215,255,.55)}
.card:hover::after{transform:translateX(130%)}
.no{font-size:10.5px;letter-spacing:.24em;color:var(--accent);font-variant-numeric:tabular-nums}
.card h3{margin:0;font-size:18.5px;font-weight:700;letter-spacing:-.022em}
.card p{margin:0;color:var(--muted);font-size:13px;line-height:1.72}
.go{margin-top:auto;padding-top:12px;display:flex;align-items:center;gap:8px;
  font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
.go i{font-style:normal;transition:transform .45s cubic-bezier(.16,1,.3,1)}
.card:hover .go{color:var(--accent)}
.card:hover .go i{transform:translateX(6px)}
.card.soon{opacity:.5}
.card.soon:hover{transform:none;border-color:var(--line);box-shadow:none}

/* oversized outline type, always drifting */
.marq{position:relative;z-index:2;overflow:hidden;margin-top:clamp(52px,9vh,92px);padding:16px 0;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)}
.marq div{display:flex;width:max-content;animation:slide 40s linear infinite}
.marq span{font-size:clamp(30px,6.6vw,68px);font-weight:800;letter-spacing:-.045em;white-space:nowrap;padding-right:.55em;
  color:transparent;-webkit-text-stroke:1px rgba(238,243,255,.2)}

.foot{position:relative;z-index:2;display:flex;flex-wrap:wrap;gap:10px 22px;justify-content:space-between;
  padding:30px 0 44px;font-size:11.5px;color:var(--muted)}
.foot a{border-bottom:1px solid transparent}
.foot a:hover{color:var(--accent);border-color:var(--accent)}

@media (max-width:560px){
  .top{padding:13px 20px}
  .live{font-size:9.5px;letter-spacing:.14em;gap:7px}
  .stat b{font-size:19px}
  .cards{gap:11px}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important}
  h1 .ln>span{transform:none}
  .rule{transform:scaleX(1)}
  .card{opacity:1;transform:none}
  .marq div,.tick .rail div{animation:none}
}
</style>
</head>
<body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<div class="glow" aria-hidden="true"></div>
<div class="grain" aria-hidden="true"></div>
<div class="spot" id="spot" aria-hidden="true"></div>

<header class="top">
  <span class="mark">Teemo<i>BKK</i></span>
  <span class="live"><span class="dot" aria-hidden="true"></span>방콕 <b id="clock">--:--:--</b> ICT</span>
</header>

<main class="wrap" id="main">
  <section class="hero">
    <p class="kick">Bangkok <u>·</u> markets &amp; daily life</p>
    <h1>
      <span class="ln"><span>시장과 생활을</span></span>
      <span class="ln"><span class="thin">한 곳에서.</span></span>
    </h1>
    <div class="rule" aria-hidden="true"></div>
    <p class="sub">비트코인·매크로 헤드라인과 태국 소식을 계속 수집해 한 화면에 모읍니다.
    지표와 글은 각자의 자리에서 이어집니다.</p>

    <div class="stats" id="stats" hidden>
      <div class="stat"><b id="s-window">-</b><span>최근 24시간 기사</span></div>
      <div class="stat"><b id="s-thai">-</b><span>그중 태국 소식</span></div>
      <div class="stat"><b id="s-upd">-</b><span>마지막 수집 ICT</span></div>
    </div>

    <div class="tick" id="tick" hidden>
      <em>방금 들어온 소식</em>
      <div class="rail"><div id="rail"></div></div>
    </div>
  </section>

  <h2 class="sect">가는 곳</h2>
  <div class="cards">
    <a class="card" href="/news/">
      <span class="no">01</span>
      <h3>뉴스 대시보드</h3>
      <p>비트코인·매크로 헤드라인과 경제지표 일정. 분류·기간·출처로 걸러 봅니다.</p>
      <span class="go">영어 / 한국어 <i>&rarr;</i></span>
    </a>
    <a class="card" href="/thai/">
      <span class="no">02</span>
      <h3>태국 소식</h3>
      <p>비자·이민, 사고·재난, 생활·경제, 관광·보건. 방콕에 사는 사람이 먼저 볼 것들.</p>
      <span class="go">영어 / 한국어 <i>&rarr;</i></span>
    </a>
    <a class="card" href="https://teemobkk.substack.com/" target="_blank" rel="noopener me">
      <span class="no">03</span>
      <h3>서브스택 블로그</h3>
      <p>시장과 생활에 대해 쓴 글. 구독하면 새 글이 메일로 갑니다.</p>
      <span class="go">teemobkk.substack.com <i>&#8599;</i></span>
    </a>
    <a class="card" href="https://www.tradingview.com/u/TeemoBKK/" target="_blank" rel="noopener me">
      <span class="no">04</span>
      <h3>트레이딩뷰 지표</h3>
      <p>차트 위에 올려 쓰는 지표를 공개합니다. 프로필에서 발행 목록을 봅니다.</p>
      <span class="go">tradingview.com/u/TeemoBKK <i>&#8599;</i></span>
    </a>
  </div>
</main>

<div class="marq" aria-hidden="true">
  <div>
    <span>BANGKOK</span><span>MARKETS</span><span>THAILAND</span><span>INDICATORS</span>
    <span>BANGKOK</span><span>MARKETS</span><span>THAILAND</span><span>INDICATORS</span>
  </div>
</div>

<div class="wrap">
  <footer class="foot">
    <span>TeemoBKK · 방콕에서 수집하고 운영합니다</span>
    <span>뉴스는 자동 매매 신호가 아닙니다 · 중요한 사건은 원문과 공시로 확인하세요</span>
  </footer>
</div>

<script>
(function(){
  "use strict";
  var API = "/api/news";

  // Bangkok time from the browser's own zone database: no manual offset to keep in sync.
  var clockFmt = new Intl.DateTimeFormat("en-GB", {timeZone:"Asia/Bangkok", hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false});
  var minFmt = new Intl.DateTimeFormat("en-GB", {timeZone:"Asia/Bangkok", hour:"2-digit", minute:"2-digit", hour12:false});
  var clock = document.getElementById("clock");
  function tickClock(){ clock.textContent = clockFmt.format(new Date()); }
  tickClock();
  setInterval(tickClock, 1000);

  // A soft light that follows the pointer, only where a real pointer exists.
  if (window.matchMedia("(hover:hover) and (pointer:fine)").matches){
    var spot = document.getElementById("spot"), raf = 0, tx = 0, ty = 0, cx = 0, cy = 0;
    window.addEventListener("pointermove", function(e){
      tx = e.clientX; ty = e.clientY; spot.style.opacity = "1";
      if (!raf) raf = requestAnimationFrame(glide);
    }, {passive:true});
    function glide(){
      cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
      spot.style.setProperty("--px", cx + "px");
      spot.style.setProperty("--py", cy + "px");
      raf = (Math.abs(tx - cx) > 0.5 || Math.abs(ty - cy) > 0.5) ? requestAnimationFrame(glide) : 0;
    }
  }

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Sections arrive as they are reached, once.
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
  if (reduced || !("IntersectionObserver" in window)){
    cards.forEach(function(c){ c.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry, i){
        if (!entry.isIntersecting) return;
        var el = entry.target;
        setTimeout(function(){ el.classList.add("in"); }, i * 70);
        io.unobserve(el);
      });
    }, {rootMargin:"0px 0px -12% 0px", threshold:.15});
    cards.forEach(function(c){ io.observe(c); });
  }

  function setNumber(el, to){ el.textContent = to.toLocaleString("en-US"); }

  function escapeText(s){ var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

  fetch(API + "?limit=8&hours=24", {cache:"no-cache"})
    .then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function(data){
      var stats = document.getElementById("stats");
      if (typeof data.total === "number"){ setNumber(document.getElementById("s-window"), data.total); }
      var thai = (data.region_counts || {})["태국"];
      if (typeof thai === "number"){ setNumber(document.getElementById("s-thai"), thai); }
      if (data.updated_at_ict){
        var m = String(data.updated_at_ict).match(/(\d{1,2}:\d{2})/);
        if (m) document.getElementById("s-upd").textContent = m[1];
      } else {
        document.getElementById("s-upd").textContent = minFmt.format(new Date());
      }
      stats.hidden = false;

      var items = (data.articles || []).filter(function(a){ return a && a.title; });
      if (items.length){
        var rail = document.getElementById("rail");
        var html = items.map(function(a){
          return "<span><b>" + escapeText(a.title) + "</b> &nbsp;" + escapeText(a.source || "") + "</span>";
        }).join("");
        rail.innerHTML = html + html;   // duplicated so the loop has no seam
        document.getElementById("tick").hidden = false;
      }
    })
    .catch(function(){
      // No data is not an error worth showing on a front page: the links below still work.
      document.getElementById("s-upd").textContent = minFmt.format(new Date());
      document.getElementById("stats").hidden = false;
    });
})();
</script>
</body>
</html>
"""


def render_landing() -> str:
    return PAGE
