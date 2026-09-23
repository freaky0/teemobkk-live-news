"""Market-first public homepage, independent of dashboard templates.

Keep external publishing links in EDITORIAL_POSTS, not in navigation labels.
Script previews are actual publication images, never reconstructed charts.
"""
from html import escape
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

EDITORIAL_POSTS = [
    {"title": "9월 18일 비트코인 주말 관점", "date": "2026-09-18", "url": "https://teemobkk.substack.com/p/9-18", "summary": "78K는 되찾았습니다. 다만 주말에는 77K대 지지와 현물 수요를 먼저 확인합니다."},
    {"title": "9월 17일 비트코인 TeemoBKK 관점", "date": "2026-09-17", "url": "https://teemobkk.substack.com/p/9-17-teemobkk", "summary": "ETF 유출과 매파적 FOMC 뒤, 76.6K 회복 전까지는 WAIT입니다."},
]

_SUBSTACK_POSTS_URL = "https://teemobkk.substack.com/api/v1/posts?limit=10"
_CACHE_FILE = Path(__file__).with_name("perspectives_cache.json")
_CACHE_TTL_SECONDS = 3600


def _valid_posts(posts):
    return isinstance(posts, list) and all(
        isinstance(post, dict) and post.get("title") and post.get("date")
        and post.get("url", "").startswith("https://teemobkk.substack.com/")
        for post in posts
    )


def _read_cache():
    try:
        with _CACHE_FILE.open(encoding="utf-8") as handle:
            cached = json.load(handle)
        posts = cached.get("posts") if isinstance(cached, dict) else None
        return posts if _valid_posts(posts) else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _fresh_cache():
    try:
        if time.time() - _CACHE_FILE.stat().st_mtime < _CACHE_TTL_SECONDS:
            return _read_cache()
    except OSError:
        pass
    return None


def _fetch_posts():
    request = Request(_SUBSTACK_POSTS_URL, headers={"User-Agent": "TeemoBKK homepage builder/1.0"})
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)
    posts = []
    for item in payload if isinstance(payload, list) else []:
        title = str(item.get("title") or "").strip()
        url = str(item.get("canonical_url") or "").strip()
        date = str(item.get("post_date") or "")[:10]
        tags = {str(tag.get("name") or "") for tag in (item.get("postTags") or []) if isinstance(tag, dict)}
        if "관점" not in title and "관점" not in tags:
            continue
        if not title or not url.startswith("https://teemobkk.substack.com/") or len(date) != 10:
            continue
        posts.append({
            "title": title,
            "date": date,
            "url": url,
            "summary": str(item.get("subtitle") or item.get("description") or "").strip(),
        })
    posts.sort(key=lambda post: post["date"], reverse=True)
    return posts[:3]


def _write_cache(posts):
    temporary = _CACHE_FILE.with_name(_CACHE_FILE.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump({"fetched_at": int(time.time()), "posts": posts}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(_CACHE_FILE)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass


def editorial_posts():
    """Use a one-hour file cache, then stale cache, then the built-in fallback."""
    fresh = _fresh_cache()
    if fresh:
        return fresh
    try:
        posts = _fetch_posts()
        if posts:
            _write_cache(posts)
            return posts
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return _read_cache() or EDITORIAL_POSTS

PAGE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK | 경제 뉴스와 트레이더의 시장 관점</title>
<meta name="description" content="주식·코인·금 등 여러 시장을 움직이는 경제 뉴스, 트레이더의 시장 관점, 무료 트레이딩뷰 지표를 공유합니다.">
<meta name="theme-color" content="#0b1118">
<meta property="og:type" content="website">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="TeemoBKK | 경제 뉴스와 시장 관점">
<meta property="og:description" content="시장을 움직이는 뉴스부터 직접 기록한 관점과 무료 차트 도구까지.">
<meta property="og:url" content="https://teemobkk.io/">
<meta property="og:image" content="https://s3.tradingview.com/e/e3AY6AxC_big.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://teemobkk.io/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
:root{color-scheme:dark;--bg:#0b1118;--surface:#111b26;--text:#edf2f7;--muted:#a2b0bf;--line:#293541;--accent:#79d8dd;--radius:12px}
*{box-sizing:border-box}html{scroll-padding-top:92px}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif;line-height:1.65;-webkit-font-smoothing:antialiased}a{color:inherit;text-decoration:none}button{font:inherit}a,button{-webkit-tap-highlight-color:transparent}a:focus-visible,button:focus-visible{outline:3px solid var(--accent);outline-offset:5px}a:hover{color:var(--accent)}button{cursor:pointer}[hidden]{display:none!important}.wrap{max-width:1184px;margin:auto;padding-inline:32px}.skip{position:absolute;left:16px;top:-100px;background:var(--accent);color:var(--bg);padding:12px;z-index:50}.skip:focus{top:12px}.top{border-bottom:1px solid var(--line);background:var(--bg)}.nav{min-height:76px;display:flex;align-items:center;gap:38px}.brand{font-weight:800;font-size:23px;letter-spacing:-.8px;white-space:nowrap}.brand span{color:var(--accent)}nav{display:flex;gap:28px;align-items:center;flex:1}nav a{font-size:14px;font-weight:600;padding-block:14px}.secondary{margin-left:auto;color:var(--muted);font-size:13px}.hero{padding:66px 0 46px;max-width:960px}.eyebrow{font-size:13px;color:var(--accent);font-weight:600;margin:0 0 16px}h1{font-size:clamp(32px,4.5vw,56px);line-height:1.22;letter-spacing:-.045em;margin:0;word-break:keep-all}h1 span{display:block}.intro{max-width:700px;color:var(--muted);font-size:17px;line-height:1.8;margin:22px 0 26px;word-break:keep-all}.actions{display:flex;flex-wrap:wrap;gap:12px}.button{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 20px;border-radius:8px;border:1px solid var(--line);font-size:14px;font-weight:700;white-space:nowrap;background:transparent;color:var(--text)}.button.primary{background:var(--accent);border-color:var(--accent);color:#0b2428}.button:hover{border-color:var(--accent)}.button:active{transform:translateY(1px)}section{scroll-margin-top:24px}.section{padding:38px 0 48px;border-top:1px solid var(--line)}h2{font-size:27px;line-height:1.3;letter-spacing:-.035em;margin:0 0 10px}.section-intro{margin:0;color:var(--muted);font-size:15px;max-width:740px;word-break:keep-all}.section-link{display:inline-block;margin-top:15px;color:var(--accent);font-size:14px;font-weight:600}.news-status{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin:22px 0 6px;color:var(--muted);font-size:12px}.retry{background:transparent;color:var(--accent);border:1px solid var(--line);border-radius:6px;min-height:36px;padding:5px 12px}.news-list{display:grid;grid-template-columns:1fr 1fr;column-gap:44px}.news-item{min-width:0;padding:20px 0;border-bottom:1px solid var(--line)}.meta{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--muted)}.topic{color:var(--accent)}.news-item h3{font-size:18px;line-height:1.55;letter-spacing:-.02em;font-weight:600;margin:8px 0 0;overflow-wrap:anywhere}.news-item a{display:block}.empty{color:var(--muted);padding:25px 0;grid-column:1/-1}.loading-line{height:15px;background:var(--surface);margin:13px 0;border-radius:4px;max-width:90%}.loading-line.short{max-width:45%;height:11px}.posts{display:grid;grid-template-columns:1.15fr 1fr;gap:36px;margin-top:25px}.post{padding:26px;background:var(--surface);border-radius:var(--radius);border:1px solid var(--line)}.post h3{font-size:23px;line-height:1.45;letter-spacing:-.025em;margin:12px 0}.post p{font-size:15px;color:var(--muted);margin:0}.post .read{display:inline-block;color:var(--accent);font-size:13px;margin-top:23px}.indicators{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:27px}.indicator{min-width:0}.chart-open{display:block;width:100%;padding:0;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:#080c11;color:var(--text);text-align:left}.chart-open img{display:block;width:100%;height:auto;aspect-ratio:1404/1281;object-fit:contain}.chart-caption{display:block;padding:11px 15px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}.indicator h3{font-size:23px;margin:20px 0 8px;letter-spacing:-.025em}.indicator p{color:var(--muted);font-size:15px;margin:0 0 18px;word-break:keep-all}.free{font-size:12px;color:var(--accent);margin-top:18px;display:block}.note{font-size:12px;color:var(--muted);margin-top:23px;max-width:850px}.about{display:grid;grid-template-columns:1fr 1fr;gap:60px}.about p{color:var(--muted);font-size:15px;margin:10px 0}.about h3{font-size:17px;margin:0 0 10px}.about ul{list-style:none;padding:0;margin:0;color:var(--muted);font-size:14px}.about li{margin:10px 0}.footer{border-top:1px solid var(--line);padding:25px 0 36px;color:var(--muted);font-size:12px}.footer-row{display:flex;flex-wrap:wrap;justify-content:space-between;gap:15px}.footer p{margin:16px 0 0;max-width:890px}dialog{max-width:min(1100px,96vw);max-height:95dvh;padding:16px;background:var(--bg);border:1px solid var(--line);border-radius:var(--radius);color:var(--text)}dialog::backdrop{background:rgba(0,0,0,.85)}dialog img{display:block;max-width:100%;max-height:77dvh;object-fit:contain;margin:auto}.dialog-head{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:12px}.dialog-head p{margin:0;font-size:14px}.dialog-head button{background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px 16px;min-height:44px}.mobile-thai{display:none}
@media(max-width:767px){.wrap{padding-inline:20px}.nav{min-height:70px;gap:20px;flex-wrap:wrap;padding-block:14px}.brand{font-size:21px}nav{gap:20px;flex-basis:100%;order:2}nav a{font-size:13px;padding:5px 0;min-height:36px;display:flex;align-items:center}.secondary{display:none}.hero{padding:38px 0 34px}.intro{font-size:15px}.news-list,.posts,.indicators,.about{grid-template-columns:1fr;gap:0}.section{padding:30px 0 35px}h2{font-size:24px}.news-item h3{font-size:17px}.post{margin-bottom:16px;padding:22px}.post h3{font-size:21px}.indicator+.indicator{margin-top:34px}.about>div+div{margin-top:25px}.mobile-thai{display:inline}.news-status{font-size:11px}.footer-row{align-items:center}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}

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
</style>
</head>
<body>
<div class="pointer-light" aria-hidden="true"></div>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<header class="top"><div class="wrap nav"><a class="brand" href="/" aria-label="TeemoBKK 홈">Teemo<span>BKK</span></a><nav aria-label="주요 메뉴"><a href="/news/ko/">경제 뉴스</a><a href="#perspectives">시장 관점</a><a href="#indicators">트레이딩뷰 지표</a><a class="secondary" href="/thai/">태국 소식 ↗</a></nav></div></header>
<main id="main" class="wrap">
<section class="hero" aria-labelledby="headline"><p class="eyebrow">뉴스를 읽고, 관점을 세우고, 차트로 살펴봅니다.</p><h1 id="headline"><span class="rise"><i>트레이딩을 위한</i></span><span class="rise"><i>경제 뉴스와 시장 관점</i></span></h1><p class="intro">주식·코인·금 등 여러 시장을 움직이는 뉴스를 모읍니다.<br>직접 기록한 시장 관점과 무료 트레이딩뷰 지표도 함께 공유합니다.</p><div class="actions"><a class="button primary" href="/news/ko/">경제 뉴스 보기</a><a class="button" href="#perspectives">시장 관점 읽기</a></div><div class="hero-rule"></div>
<div class="stats">
<div class="stat"><b id="stat-total">&mdash;</b><span>&#52572;&#44540; 24&#49884;&#44036; &#49688;&#51665;</span></div>
<div class="stat"><b id="stat-thai">&mdash;</b><span>&#44536;&#51473; &#53468;&#44397; &#49548;&#49885;</span></div>
<div class="stat"><b>2&#48516;</b><span>&#51088;&#46041; &#44081;&#49888;</span></div>
</div></section>
<div class="marq" aria-hidden="true"><div>
<span>ECONOMIC NEWS</span><span>MARKET PERSPECTIVES</span><span>TRADINGVIEW INDICATORS</span><span>BANGKOK</span>
<span>ECONOMIC NEWS</span><span>MARKET PERSPECTIVES</span><span>TRADINGVIEW INDICATORS</span><span>BANGKOK</span>
</div></div>
<section class="section" id="news" aria-labelledby="news-title"><h2 id="news-title">최근 경제 뉴스</h2><p class="section-intro">금리와 경기, 기업과 정책, 지정학까지. 시장에 연결되는 소식을 확인하세요.</p><div class="news-status"><span>자동 수집 · 원문 언어로 표시</span><span id="update-status" role="status">수집 상태 확인 중</span><button class="retry" id="retry" type="button" hidden>다시 불러오기</button></div><div class="news-list" id="news-list" aria-busy="true"><div class="news-item" aria-hidden="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div><div class="news-item" aria-hidden="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div></div><noscript><p>뉴스 목록을 불러오려면 자바스크립트가 필요합니다. <a href="/news/ko/">경제 뉴스 페이지에서 확인하세요.</a></p></noscript><a class="section-link" href="/news/ko/">경제 뉴스 전체 보기 →</a></section>
<section class="section" id="perspectives" aria-labelledby="perspectives-title"><h2 id="perspectives-title">시장 관점</h2><p class="section-intro">뉴스와 차트를 어떻게 읽는지, 어떤 조건에서 생각을 바꾸는지. 트레이더로서의 판단을 기록합니다.</p><div class="posts">__POSTS__</div><p class="note">각 글은 작성 당시의 개인적인 관점입니다. 가격과 시나리오는 현재 시점과 다를 수 있습니다.</p></section>
<section class="section" id="indicators" aria-labelledby="indicators-title"><h2 id="indicators-title">직접 만든 트레이딩뷰 지표</h2><p class="section-intro">차트의 구조와 추세를 살펴보는 도구입니다. 공식 트레이딩뷰 페이지에서 무료로 사용할 수 있습니다.</p><div class="indicators">
<article class="indicator"><button class="chart-open" type="button" data-chart="https://s3.tradingview.com/e/e3AY6AxC_big.png" data-title="Teemo Elliott Wave" aria-label="Teemo Elliott Wave 차트 확대"><img src="https://s3.tradingview.com/e/e3AY6AxC_big.png" width="1404" height="1281" loading="lazy" decoding="async" alt="엔비디아 5분봉 위에 엘리어트 파동과 피보나치 구간을 표시한 실제 지표 화면"><span class="chart-caption">엔비디아 5분봉 적용 예시 · 눌러서 확대</span></button><span class="free">무료 공개 · 소스 코드는 비공개</span><h3>Teemo Elliott Wave</h3><p>엘리어트 파동 카운팅과 피보나치 구간을 차트에 표시합니다. 파동 구조를 살펴보는 보조 도구로 활용하세요.</p><a class="button" href="https://www.tradingview.com/script/e3AY6AxC/" target="_blank" rel="noopener noreferrer">트레이딩뷰에서 보기 ↗</a></article>
<article class="indicator"><button class="chart-open" type="button" data-chart="https://s3.tradingview.com/g/Gg4UXPqH_big.png" data-title="Teemo Scout Suite" aria-label="Teemo Scout Suite 차트 확대"><img src="https://s3.tradingview.com/g/Gg4UXPqH_big.png" width="1404" height="1281" loading="lazy" decoding="async" alt="비트코인 5분봉 위에 이동평균선, 구름대와 이격도 표를 표시한 실제 지표 화면"><span class="chart-caption">비트코인 5분봉 적용 예시 · 눌러서 확대</span></button><span class="free">무료 공개 · 소스 코드는 비공개</span><h3>Teemo Scout Suite</h3><p>이동평균선, 볼린저 밴드, 일목구름과 세션 VWAP을 함께 봅니다. 추세와 기준선 대비 가격 이격을 살펴보세요.</p><a class="button" href="https://www.tradingview.com/script/Gg4UXPqH/" target="_blank" rel="noopener noreferrer">트레이딩뷰에서 보기 ↗</a></article>
</div><a class="section-link" href="https://www.tradingview.com/u/TeemoBKK/" target="_blank" rel="noopener noreferrer me">공식 프로필에서 전체 지표 보기 ↗</a><p class="note">이미지는 각 지표의 공식 공개 페이지에 게시된 과거 적용 예시이며 실시간 차트나 수익률 증명이 아닙니다. 사용 조건과 설정은 해당 페이지에서 확인하세요. 파동 카운팅과 목표 구간은 진행 중인 가격에 따라 달라질 수 있습니다.</p></section>
<section class="section about" aria-labelledby="about-title"><div><h2 id="about-title">TeemoBKK에 대하여</h2><p>경제 뉴스를 모으고, 시장을 바라보는 관점을 쓰며, 차트에서 사용하는 지표를 만듭니다.</p><p>뉴스는 시장의 맥락을 살피는 출발점입니다. 해석과 시나리오는 사실과 구분해 기록하겠습니다.</p></div><div><h3>읽기 전에</h3><ul><li>뉴스는 자동 수집한 원문 제목과 출처를 제공합니다.</li><li>시장 관점은 운영자의 개인적인 해석입니다.</li><li>지표는 분석 보조 도구이며 수익을 보장하지 않습니다.</li></ul></div></section>
</main>
<footer class="footer"><div class="wrap"><div class="footer-row"><span>TeemoBKK · 경제 뉴스와 트레이더의 기록</span><a href="/thai/">별도 소식 · 태국 교민 뉴스 ↗</a></div><p>뉴스는 자동 매매 신호가 아닙니다 · 중요한 사건은 원문과 공시로 확인하세요. 제공되는 글과 지표만으로 투자 결정을 내리지 마세요.</p></div></footer>
<dialog id="chart-dialog" aria-labelledby="chart-title"><div class="dialog-head"><p id="chart-title"></p><button id="close-chart" type="button">닫기</button></div><img id="expanded-chart" alt=""></dialog>
<script>
(function(){
'use strict';
const list=document.getElementById('news-list'), status=document.getElementById('update-status'), retry=document.getElementById('retry');
let busy=false, hasNews=false;
const fmt=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Bangkok',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
function cleanTitle(value){return String(value||'').replace(/(?:https?:\/\/|www\.)\S+|\b[a-z0-9.-]+\.(?:com|org|net|rs)\/\S+/gi,'').replace(/\s+-\s+[^-]+$/,'').replace(/\s+/g,' ').trim();}
function safeLink(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch(e){return null;}}
function relevant(a){if(a.category&&a.category!=='일반')return true;return /금리|금값|금 가격|금 선물|은값|원유|유가|물가|고용|실업|관세|중앙은행|연준|증시|주식|채권|환율|달러|실적|비트코인|암호화폐|가상자산|이더리움|인플레|경기|\b(?:stocks?|equities|bonds?|yields?|gold|silver|oil|crude|inflation|payrolls|tariffs?|fed|fomc|gdp|cpi|pce|earnings|bitcoin|crypto|ethereum|etf|forex|rates?|central bank)\b/i.test(String(a.title||''));}
function selectNews(articles){const seen=new Set();return articles.filter(a=>{if(a.region!=='글로벌'||!relevant(a))return false;const title=cleanTitle(a.title);const key=title.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');const date=Date.parse(a.published_at);if(key.length<8||!safeLink(a.link)||!Number.isFinite(date)||date>Date.now()+60000||Date.now()-date>86400000||seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at)).slice(0,6);}
function render(articles){list.replaceChildren();if(!articles.length){const p=document.createElement('p');p.className='empty';p.textContent='최근 24시간에 표시할 뉴스가 없습니다. 전체 뉴스에서 기간과 분류를 확인하세요.';list.append(p);return;}
for(const a of articles){const item=document.createElement('article');item.className='news-item';const link=document.createElement('a');link.href=safeLink(a.link);link.target='_blank';link.rel='noopener noreferrer';const meta=document.createElement('div');meta.className='meta';const source=document.createElement('span');source.textContent=a.source||'원문';const category=document.createElement('span');category.className='topic';category.textContent=a.category||'경제';const time=document.createElement('time');time.dateTime=a.published_at;time.textContent=fmt.format(new Date(a.published_at))+' ICT';meta.append(source,category,time);const title=document.createElement('h3');title.textContent=cleanTitle(a.title)+' ↗';link.append(meta,title);item.append(link);list.append(item);}hasNews=true;}
async function refresh(){if(busy)return;busy=true;retry.disabled=true;list.setAttribute('aria-busy','true');const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);try{const response=await fetch('/api/news?region='+encodeURIComponent('글로벌')+'&hours=24&limit=100',{cache:'no-cache',signal:controller.signal});if(!response.ok)throw new Error('http');const data=await response.json();if(!Array.isArray(data.articles))throw new Error('schema');render(selectNews(data.articles));const updated=Date.parse(data.updated_at);if(Number.isFinite(updated)&&updated<=Date.now()+60000){const age=Date.now()-updated;status.textContent=(age>35*60000?'갱신 지연 · 마지막 수집 ':'마지막 수집 ')+fmt.format(new Date(updated))+' ICT';retry.hidden=age<=35*60000;}else{status.textContent='수집 시각을 확인할 수 없습니다';retry.hidden=false;}}
catch(error){status.textContent=hasNews?'갱신 실패 · 이전 목록 표시 중':'뉴스를 불러오지 못했습니다';retry.hidden=false;if(!hasNews){list.replaceChildren();const p=document.createElement('p');p.className='empty';p.textContent='잠시 후 다시 시도하거나 경제 뉴스 페이지에서 확인하세요.';list.append(p);}}
finally{clearTimeout(timeout);busy=false;retry.disabled=false;list.setAttribute('aria-busy','false');}}
retry.addEventListener('click',refresh);refresh();setInterval(()=>{if(!document.hidden)refresh();},120000);
const dialog=document.getElementById('chart-dialog');document.querySelectorAll('[data-chart]').forEach(button=>button.addEventListener('click',()=>{document.getElementById('expanded-chart').src=button.dataset.chart;document.getElementById('expanded-chart').alt=button.dataset.title+' 실제 적용 화면';document.getElementById('chart-title').textContent=button.dataset.title;dialog.showModal();}));document.getElementById('close-chart').addEventListener('click',()=>dialog.close());
})();
</script>
<script>
(function(){
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // A light that follows the pointer, where a real pointer exists. Fixed layer, hidden from
  // assistive tech, and switched off for anyone who asked for less motion.
  if (!reduce && window.matchMedia("(hover:hover) and (pointer:fine)").matches){
    var light = document.querySelector(".pointer-light"), raf = 0, tx = 0, ty = 0, cx = 0, cy = 0;
    var glide = function(){
      cx += (tx - cx) * .09; cy += (ty - cy) * .09;
      light.style.setProperty("--px", cx + "px");
      light.style.setProperty("--py", cy + "px");
      raf = (Math.abs(tx - cx) > .5 || Math.abs(ty - cy) > .5) ? requestAnimationFrame(glide) : 0;
    };
    window.addEventListener("pointermove", function(e){
      tx = e.clientX; ty = e.clientY; light.style.opacity = "1";
      if (!raf) raf = requestAnimationFrame(glide);
    }, {passive:true});
  }

  // The counts come from the same endpoint the list uses, so the strip shows what the collector
  // actually holds instead of a number maintained in a second place. A missing field leaves the
  // dash alone, and every path is caught: a failure here must never surface as a page error.
  function paint(data){
    if (!data || typeof data !== "object") return;
    var set = function(id, value){
      var el = document.getElementById(id);
      if (el && typeof value === "number") el.textContent = value.toLocaleString("en-US") + "\uac74";
    };
    set("stat-total", data.total);
    set("stat-thai", data.region_counts && data.region_counts["\ud0dc\uad6d"]);
  }
  function counts(){
    fetch("/api/news?region=" + encodeURIComponent("\uae00\ub85c\ubc8c") + "&hours=24&limit=1", {cache:"no-cache"})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(paint)
      .catch(function(){});
  }
  counts();
  setInterval(function(){ if (!document.hidden) counts(); }, 120000);
})();
</script>
</body></html>'''


def stylesheet() -> str:
    """The whole <style> block.

    The Thailand landing shows the same type and motion. Keeping its own copy would let the two
    pages drift, and the site would start to read as two sites.
    """
    start = PAGE.index("<style>")
    end = PAGE.index("</style>") + len("</style>")
    return PAGE[start:end]


def render_landing() -> str:
    posts = []
    for post in editorial_posts():
        posts.append('<article class="post"><time datetime="{date}">{date}</time><h3><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3><p>{summary}</p><a class="read" href="{url}" target="_blank" rel="noopener noreferrer">관점 읽기 · 외부 글 ↗</a></article>'.format(**{k: escape(v, quote=True) for k, v in post.items()}))
    return PAGE.replace('__POSTS__', ''.join(posts))
