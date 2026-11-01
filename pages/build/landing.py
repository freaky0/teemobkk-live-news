"""Market-first public homepage, independent of dashboard templates.

Homepage market-view teasers use the canonical Markdown posts under content/blog.
Script previews are actual publication images, never reconstructed charts.
"""
import sys
from pathlib import Path

# Repository-root bootstrap: this file lives under pages/build/, but the code is
# imported as pages.build.<module> with the repository root on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from html import escape


import json
import re
import time
from urllib.request import Request, urlopen
from pages.build import theme

EDITORIAL_POSTS = [
    {"title": "9월 18일 비트코인 주말 관점", "date": "2026-09-18", "url": "https://teemobkk.substack.com/p/9-18", "summary": "78K는 되찾았습니다. 다만 주말에는 77K대 지지와 현물 수요를 먼저 확인합니다."},
    {"title": "9월 17일 비트코인 TeemoBKK 관점", "date": "2026-09-17", "url": "https://teemobkk.substack.com/p/9-17-teemobkk", "summary": "ETF 유출과 매파적 FOMC 뒤, 76.6K 회복 전까지는 WAIT입니다."},
]

_SUBSTACK_POSTS_URL = "https://teemobkk.substack.com/api/v1/posts?limit=50"
_CACHE_FILE = _REPO_ROOT / "perspectives_cache.json"
_CACHE_TTL_SECONDS = 3600

INDICATORS = (
    {
        "code": "fpkVFwl2",
        "title": "Teemo Supply and Demand Zone",
        "image": "https://s3.tradingview.com/f/fpkVFwl2_big.png",
        "alt": "Teemo Supply and Demand Zone 지표 적용 예시",
        "description": "수요/공급 구간 자동 식별, S/D Flip 추적, 거래량(HVP) 검증. 핵심 가격대에서 반응을 살펴보는 도구입니다.",
    },
    {
        "code": "e3AY6AxC",
        "title": "Teemo Elliott Wave",
        "image": "https://s3.tradingview.com/e/e3AY6AxC_big.png",
        "alt": "Teemo Elliott Wave 지표 적용 예시",
        "description": "엘리어트 파동 자동 카운팅, 실시간 추적. 파동 구조와 다음 시나리오를 살펴보는 보조 도구로 활용하세요.",
    },
)
INDICATOR_PROFILE_URL = "https://kr.tradingview.com/u/TeemoBKK/#published-scripts"


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
    return posts[:10]


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


def editorial_posts(limit=3):
    """Use a one-hour cache, refreshing it when the caller needs more posts."""
    limit = max(1, min(10, int(limit)))
    fresh = _fresh_cache()
    if fresh and len(fresh) >= limit:
        return fresh[:limit]
    try:
        posts = _fetch_posts()
        if posts:
            _write_cache(posts)
            return posts[:limit]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return (_read_cache() or EDITORIAL_POSTS)[:limit]

PAGE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
__THEME_HEAD__
<script>try{if(!window.matchMedia||!window.matchMedia("(prefers-reduced-motion: reduce)").matches)document.documentElement.classList.add("reveal-enabled");}catch(e){}</script>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK | 차트보다 먼저 읽는 뉴스</title>
<meta name="description" content="시장이 움직이는 이유를 전합니다. 금리와 정책, 지정학과 수급까지. 트레이더의 경제 뉴스와 시장 관점, 무료 트레이딩뷰 지표.">
<meta name="theme-color" content="#f0f0ee">
<meta name="color-scheme" content="light dark">
<meta property="og:type" content="website">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="TeemoBKK | 차트보다 먼저 읽는 뉴스">
<meta property="og:description" content="시장이 움직이는 이유를 전합니다. 금리와 정책, 지정학과 수급까지.">
<meta property="og:url" content="https://teemobkk.io/">
<meta property="og:image" content="https://teemobkk.io/assets/landing/hero-editorial.webp">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://teemobkk.io/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
__SHARED_THEME_CSS__
/* Warm stone paper, deep ink, and a single editorial green. */
*{box-sizing:border-box}html{scroll-padding-top:96px}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.75;-webkit-font-smoothing:antialiased}a{color:inherit;text-decoration:none}button{font:inherit}a,button{-webkit-tap-highlight-color:transparent}a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:3px}a:hover{color:var(--accent)}button{cursor:pointer}[hidden]{display:none!important}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.wrap{max-width:var(--content);margin:auto;padding-inline:clamp(20px,4vw,40px)}
.skip{position:fixed;left:16px;top:16px;z-index:60;transform:translateY(-160%);padding:11px 16px;border-radius:2px;background:var(--accent);color:#ffffff;font-weight:700;transition:transform .15s ease}
.skip:focus,.skip:focus-visible{transform:none}
.skip:focus-visible{outline:3px solid var(--text);outline-offset:2px}

/* Motion is progressive enhancement: content is visible without it. */
@keyframes hero-in{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:no-preference){
 .hero-copy h1,.hero-copy .intro,.hero-actions,.hero-index{animation:hero-in .7s cubic-bezier(.2,.7,.2,1) both}
 .hero-copy .intro{animation-delay:.08s}
 .hero-actions{animation-delay:.16s}
 .hero-index{animation-delay:.22s}
}
.reveal-enabled .section > *:not(noscript),.reveal-enabled .about > *{opacity:0;transform:translateY(14px);transition:opacity .55s ease,transform .55s ease}
.reveal-enabled .section.is-visible > *:not(noscript),.reveal-enabled .about.is-visible > *{opacity:1;transform:none}
.reveal-enabled .section > :nth-child(2),.reveal-enabled .about > :nth-child(2){transition-delay:70ms}
.reveal-enabled .section > :nth-child(3),.reveal-enabled .about > :nth-child(3){transition-delay:140ms}
.reveal-enabled .section > :nth-child(4),.reveal-enabled .about > :nth-child(4){transition-delay:210ms}
.reveal-enabled .section > :nth-child(5),.reveal-enabled .about > :nth-child(5){transition-delay:280ms}
.reveal-enabled .section > :nth-child(6),.reveal-enabled .about > :nth-child(6){transition-delay:350ms}
.reveal-enabled .section > :nth-child(7),.reveal-enabled .about > :nth-child(7){transition-delay:420ms}
.reveal-enabled .section > :nth-child(8),.reveal-enabled .about > :nth-child(8){transition-delay:490ms}
.reveal-enabled .news-strip img{transform:scale(1.035);transition:transform 1.3s ease}
.reveal-enabled .section.is-visible .news-strip img{transform:scale(1)}
@media(prefers-reduced-motion:no-preference){
 @keyframes image-settle{from{transform:scale(1.035)}to{transform:none}}
 .hero-image img{animation:image-settle 1.3s ease both}
}

.ticker{display:flex;align-items:center;background:var(--ink-2);color:rgba(242,242,241,.78);overflow:hidden;white-space:nowrap}
.ticker-state{display:inline-flex;align-items:center;gap:8px;flex:0 0 auto;padding:8px 14px;background:rgba(0,0,0,.14);font:600 13.5px/1.5 var(--sans);letter-spacing:0;color:rgba(242,242,241,.82)}
.ticker-state .dot{width:6px;height:6px;flex:0 0 auto;border-radius:50%;background:#e6bd65}
.ticker-state[data-state=live] .dot{background:var(--accent-bright);box-shadow:0 0 0 3px rgba(62,207,142,.16)}
.ticker-state[data-state=stale] .dot,.ticker-state[data-state=reconnecting] .dot{background:#ff9d9d}
.ticker-state[data-state=unsupported] .dot{background:rgba(242,242,241,.35)}
.ticker-age{color:rgba(242,242,241,.58);font-weight:400}
.ticker-viewport{flex:1 1 auto;min-width:0;overflow:hidden}
.ticker-inner{display:inline-flex;padding:8px 0;animation:tick 36s linear infinite}
.ticker-inner:empty{animation:none}
.ticker-seq{display:inline-flex}
.ticker:hover .ticker-inner,.ticker:focus-within .ticker-inner{animation-play-state:paused}
.tick{display:inline-flex;align-items:center;gap:8px;padding:0 20px;font:13.5px/1.6 var(--sans);font-variant-numeric:tabular-nums;color:rgba(242,242,241,.72)}
.tick b{color:#f2f2f1;font-weight:700}
.tick .up{color:var(--accent-bright)}.tick .dn{color:#ff9d9d}.tick .flat{color:rgba(242,242,241,.65)}
@keyframes tick{to{transform:translateX(-50%)}}

/* First viewport: what the publication is, in type. */
.hero{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:clamp(28px,5vw,72px);align-items:start;padding:clamp(40px,6vw,78px) 0 clamp(36px,5vw,64px)}
.hero-copy{min-width:0}
.hero-aside{min-width:0;display:flex;flex-direction:column;gap:24px}
.hero-image{margin:0;overflow:hidden;background:var(--surface2)}
.hero-image img{display:block;width:100%;height:clamp(140px,14vw,180px);object-fit:cover;object-position:center 42%}
h1{font-size:clamp(38px,6.4vw,76px);line-height:1.02;letter-spacing:-.055em;margin:0;font-weight:800;word-break:keep-all}
h1 .hl{color:var(--accent)}
.intro{max-width:56ch;color:var(--muted);font-size:17px;line-height:1.75;margin:22px 0 30px;word-break:keep-all}
.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin:0}
.hero-index{list-style:none;margin:0;padding:0;display:grid;gap:18px}
.hero-index a{display:flex;flex-direction:column;gap:4px;padding:0}
.hero-index strong{font-size:17px;font-weight:750;letter-spacing:-.01em}
.hero-index span:last-child{font-size:13.5px;line-height:1.55;color:var(--muted)}
.hero-index a:hover strong{color:var(--accent)}

section{scroll-margin-top:24px}
.section{padding:clamp(42px,5vw,68px) 0}
.sec-head{display:block;margin-bottom:10px}
h2{font-size:clamp(24px,3vw,34px);line-height:1.18;letter-spacing:-.035em;margin:0;font-weight:800}
.section-intro{margin:10px 0 0;color:var(--muted);font-size:17px;max-width:60ch;word-break:keep-all}
.section-link{display:inline-flex;align-items:center;min-height:44px;margin-top:14px;color:var(--accent);font:600 17px/1.5 var(--sans);letter-spacing:0}
.section-link:hover{text-decoration:underline;text-underline-offset:5px}
.news-status{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin:20px 0 0;color:var(--muted);font-family:var(--sans);font-size:13.5px}
.news-status .live{color:var(--accent)}
.retry{min-height:44px;background:var(--surface2);color:var(--text);border:0;border-radius:2px;padding:7px 14px;font-family:var(--sans);font-size:13.5px}
.retry:hover{background:var(--text);color:var(--bg)}
.news-list{display:grid;gap:16px;margin-top:14px}
.news-row{display:flex;align-items:baseline;gap:16px}
.news-row a{display:flex;align-items:baseline;gap:16px;flex:1;min-width:0}
.news-row a:hover .ntitle{color:var(--accent)}
.ntime{font-family:var(--sans);font-size:13.5px;color:var(--muted);white-space:nowrap;flex-shrink:0}
.ntopic{font-family:var(--sans);font-size:13.5px;color:var(--accent);white-space:nowrap;flex-shrink:0}
.ntitle{font-size:17px;font-weight:600;line-height:1.5;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:keep-all}
.ntitle .ext{color:var(--muted);font-size:13.5px}
.empty{color:var(--muted);padding:26px 0;font-size:17px}
.loading-line{height:14px;background:var(--surface2);margin:14px 0;border-radius:2px;max-width:88%}
.loading-line.short{max-width:40%;height:11px}
/* The news image is a compact strip below the headlines and the section link. */
.news-strip{position:relative;margin:26px 0 0;height:160px;overflow:hidden;background:var(--surface2)}
.news-strip img{display:block;width:100%;height:100%;object-fit:cover;object-position:center 42%}
.news-strip::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(13,26,21,0) 38%,rgba(13,26,21,.8))}
.news-strip figcaption{position:absolute;left:0;right:0;bottom:0;z-index:1;padding:12px 16px;color:#f2f2f1;font-size:13.5px;line-height:1.5;word-break:keep-all}
.posts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px 40px;margin-top:26px}
.post{display:flex;flex-direction:column;padding:0}
.post:first-child{grid-column:1/-1;max-width:60ch}
.post:first-child h3{font-size:20px;line-height:1.35}
.post time{display:block;margin:0 0 10px;font:400 13.5px/1.5 var(--sans);color:var(--muted)}
.post h3{font-size:20px;line-height:1.35;letter-spacing:-.025em;margin:0 0 8px;font-weight:750;word-break:keep-all}
.post h3 a:hover{color:var(--accent)}
.post p{font-size:17px;color:var(--text);margin:0;line-height:1.75;max-width:60ch;word-break:keep-all}
.post .read{display:inline-flex;align-items:center;min-height:40px;color:var(--accent);font:600 13.5px/1.5 var(--sans);margin-top:10px}
.post .read:hover{text-decoration:underline;text-underline-offset:4px}
.note{font-size:13.5px;color:var(--muted);margin-top:22px;max-width:60ch;line-height:1.75}
__INDICATOR_CSS__

/* The one kinetic moment: reading → a point of view → chart verification. */
.kinetic{background:var(--ink);color:#f2f2f1;padding:clamp(44px,6vw,76px) 0}
.kinetic-inner{max-width:var(--content);margin:auto;padding-inline:clamp(20px,4vw,40px);display:grid;gap:18px}
.kinetic-line{margin:0;display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;font-size:clamp(24px,3vw,34px);line-height:1.2;letter-spacing:-.04em;font-weight:800;word-break:keep-all}
.k-step{color:#f2f2f1}
.k-arrow{color:var(--accent-bright);font-weight:400;font-size:.8em}
@keyframes k-step{
 0%,16%{color:#ffffff;transform:translateY(0)}
 24%{color:#ffffff;transform:translateY(-.14em)}
 32%,100%{color:rgba(242,242,241,.45);transform:translateY(0)}
}
.kinetic.motion-enabled .k-step{color:rgba(242,242,241,.45);animation:k-step 6s ease-in-out infinite}
.kinetic.motion-enabled .k-step:nth-child(3){animation-delay:2s}
.kinetic.motion-enabled .k-step:nth-child(5){animation-delay:4s}
.kinetic.motion-enabled[data-paused="1"] .k-step{animation-play-state:paused}
.kinetic-toggle{justify-self:start;display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border:0;border-radius:2px;background:rgba(242,242,241,.12);color:rgba(242,242,241,.8);font:600 13.5px/1.4 var(--sans)}
.kinetic-toggle:hover{background:rgba(62,207,142,.16);color:var(--accent-bright)}
.kinetic-toggle:focus-visible{outline:2px solid var(--accent-bright);outline-offset:3px}
.kinetic-toggle[disabled]{color:rgba(242,242,241,.55);background:rgba(242,242,241,.07);cursor:default}
.kinetic-status{margin:0;min-height:1.5em;font:13.5px/1.5 var(--sans);color:rgba(242,242,241,.68);word-break:keep-all}
.about{display:grid;grid-template-columns:1.1fr .9fr;gap:clamp(28px,6vw,72px);padding:clamp(42px,5vw,68px) 0 0}
.about p{color:var(--text);font-size:17px;margin:10px 0;word-break:keep-all;max-width:58ch}
.about h3{font-size:17px;margin:0 0 12px;font-family:var(--sans);letter-spacing:0;text-transform:none;color:var(--text);font-weight:700}
.about ul{list-style:none;padding:0;margin:0;color:var(--muted);font-size:17px}
.about li{margin:10px 0;padding-left:18px;position:relative;line-height:1.65}
.about li::before{content:"";position:absolute;left:0;top:.72em;width:6px;height:6px;border-radius:50%;background:var(--accent)}
@media(max-width:1023px){
 .hero{grid-template-columns:1fr;align-items:start;gap:34px}
 .hero-index{max-width:520px}
 .posts{grid-template-columns:1fr;gap:26px}
 .post:first-child{grid-column:auto;max-width:none}
 .post:first-child h3{font-size:20px}
 .about{grid-template-columns:1fr;gap:28px}
}
@media(max-width:767px){
 .wrap{padding-inline:20px}
 .hero{padding:32px 0 36px}
 h1{letter-spacing:-.045em}
 .intro{font-size:17px;margin:18px 0 24px}
 .section{padding:34px 0}
 .news-row{gap:10px}
 .news-row a{flex-wrap:wrap;gap:4px 10px}
 .ntime{font-size:13.5px}
 .ntitle{font-size:17px;flex-basis:100%}
 .news-strip{height:120px;margin-top:20px}
 .news-strip figcaption{font-size:13.5px;padding:9px 12px}
 .post h3{font-size:20px;line-height:1.35}
 .post:first-child h3{font-size:20px}
 .post p{font-size:17px}
 .ticker-state{padding:7px 10px;font-size:13.5px;gap:6px}
 .ticker-age{font-size:13.5px}
 .tick{font-size:13.5px;padding:0 14px}
}
@media(max-width:480px){
 /* The price track gets the full width once the status has its own line. */
 .ticker{display:block}
 .ticker-state{padding:7px 10px}
 .ticker-viewport{width:100%}
}
@media(prefers-reduced-motion:reduce){
 .ticker-inner{animation:none}
 .reveal-enabled .section > *:not(noscript),.reveal-enabled .about > *{opacity:1;transform:none;transition:none}
 .reveal-enabled .news-strip img,.hero-image img{transform:none;transition:none;animation:none}
 .kinetic.motion-enabled .k-step,
 .kinetic.motion-enabled .k-step:nth-child(3),
 .kinetic.motion-enabled .k-step:nth-child(5){animation:none;color:#f2f2f1;transform:none}
 *,*::before,*::after{transition:none!important;animation:none!important}
}

/* Page-level duplication of the shared type scale, brand and section rules was retired;
   the newsroom identity now comes from theme.shared_css() once. */
/* Section rhythm and type scale live once above; retired page-level overrides removed. */
</style>
</head>
<body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
__HEADER__
<div class="ticker" id="ticker" role="region" aria-label="암호화폐와 주요 지수 시세" hidden>
 <div class="ticker-state" id="ticker-state" data-state="connecting" title="MEXC 연결 상태">
  <span class="dot" aria-hidden="true"></span><span id="ticker-state-text" role="status" aria-live="polite">MEXC 연결 중</span><span class="ticker-age" id="ticker-age"></span>
 </div>
 <div class="ticker-viewport"><div class="ticker-inner" id="ticker-inner"></div></div>
</div>
<main id="main">
<div class="wrap">
<section class="hero" aria-labelledby="headline">
  <div class="hero-copy">
    <h1 id="headline">차트보다 먼저<br><span class="hl">읽는 뉴스</span></h1>
    <p class="intro">방콕에서 읽는 시장 테이프. 금리와 정책, 지정학과 수급을 모아 오늘 시장이 움직인 이유를 설명하고, 관점과 차트로 다시 검증합니다.</p>
    <div class="hero-actions"><a class="button primary" href="/news/ko/">오늘의 시장 보기</a><a class="button" href="/perspectives/">관점 읽기</a></div>
  </div>
  <div class="hero-aside">
    <figure class="hero-image">
      <img src="/assets/landing/hero-editorial.webp" width="1672" height="941" loading="eager" decoding="async" fetchpriority="high" alt="방콕의 편집 데스크에서 경제 뉴스와 시장 차트를 함께 살펴보는 장면">
    </figure>
    <ul class="hero-index" aria-label="TeemoBKK 구성">
      <li><a href="/news/ko/"><strong>경제 뉴스</strong><span>5분마다 갱신되는 시장 헤드라인</span></a></li>
      <li><a href="/perspectives/"><strong>시장 관점</strong><span>생각이 바뀌는 조건의 기록</span></a></li>
      <li><a href="/indicators/"><strong>트레이딩뷰 지표</strong><span>구조를 읽는 무료 도구</span></a></li>
    </ul>
  </div>
</section>
<section class="section" id="news" aria-labelledby="news-title"><div class="sec-head"><h2 id="news-title">최근 경제 뉴스</h2></div><p class="section-intro">금리와 경기, 기업과 정책, 지정학까지. 시장에 연결되는 소식을 원문과 시각으로 확인하세요.</p><div class="news-status"><span class="live">● 자동 수집 · 한국어로 표시</span><span id="update-status" role="status">수집 상태 확인 중</span><button class="retry" id="retry" type="button" hidden>다시 불러오기</button></div><div class="news-list" id="news-list" aria-busy="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div><noscript><p>뉴스 목록을 불러오려면 자바스크립트가 필요합니다. <a href="/news/ko/">경제 뉴스 페이지에서 확인하세요.</a></p></noscript><a class="section-link" href="/news/ko/">전체 뉴스 보기 →</a><figure class="news-strip"><img src="/assets/landing/news-editorial.webp" width="1536" height="1024" loading="lazy" decoding="async" alt="방콕의 편집 데스크에서 경제 뉴스와 시장 자료를 살펴보는 장면"><figcaption>뉴스는 원문과 게시 시각을 확인해 읽습니다.</figcaption></figure></section>
<section class="kinetic" id="kinetic" aria-label="시장을 읽는 방식"><div class="kinetic-inner"><p class="kinetic-line" aria-hidden="true"><span class="k-step">뉴스를 읽고</span><span class="k-arrow">→</span><span class="k-step">관점을 세우고</span><span class="k-arrow">→</span><span class="k-step">차트로 검증한다</span></p><p class="sr-only">뉴스를 읽고, 관점을 세우고, 차트로 검증한다</p><button class="kinetic-toggle" id="kinetic-toggle" type="button" aria-controls="kinetic" aria-pressed="false" hidden>일시정지</button><p class="kinetic-status" id="kinetic-status" role="status"></p></div></section>
<section class="section" id="perspectives" aria-labelledby="perspectives-title"><div class="sec-head"><h2 id="perspectives-title">시장 관점</h2></div><p class="section-intro">뉴스와 차트를 어떻게 읽는지, 어떤 조건에서 생각을 바꾸는지. 트레이더로서의 판단을 기록합니다.</p><div class="posts">__POSTS__</div><a class="section-link" href="/blog/">관점 글 더 보기 →</a><p class="note">각 글은 작성 당시의 개인적인 관점입니다. 가격과 시나리오는 현재 시점과 다를 수 있습니다.</p></section>
<section class="section" id="indicators" aria-labelledby="indicators-title"><div class="sec-head"><h2 id="indicators-title">직접 만든 트레이딩뷰 지표</h2></div><p class="section-intro">차트의 구조와 파동을 살펴보는 도구입니다. 공식 트레이딩뷰 페이지에서 무료로 사용할 수 있습니다.</p><div class="indicators">__INDICATORS__</div><a class="section-link" href="/indicators/">지표 전체 보기 →</a><a class="section-link" href="https://kr.tradingview.com/u/TeemoBKK/#published-scripts" target="_blank" rel="noopener noreferrer me">트레이딩뷰 전체 지표 보기 ↗</a><p class="note">파동 카운팅과 목표 구간은 진행 중인 가격에 따라 달라질 수 있습니다. 사용 조건과 설정은 각 지표 페이지에서 확인하세요.</p></section>
<section class="about" aria-labelledby="about-title"><div><div class="sec-head"><h2 id="about-title">TeemoBKK에 대하여</h2></div><p>경제 뉴스를 모으고, 시장을 바라보는 관점을 쓰며, 차트에서 사용하는 지표를 만듭니다.</p><p>뉴스는 시장의 맥락을 살피는 출발점입니다. 해석과 시나리오는 사실과 구분해 기록하겠습니다.</p><a class="section-link" href="/about/">사이트 소개 보기 →</a></div><div><h3>읽기 전에</h3><ul><li>뉴스는 자동 수집한 원문 제목과 출처를 제공합니다.</li><li>시장 관점은 운영자의 개인적인 해석입니다.</li><li>지표는 분석 보조 도구이며 수익을 보장하지 않습니다.</li></ul></div></section>
</div>
</main>
__FOOTER__
<script>
(function(){
'use strict';
var ticker=document.getElementById('ticker'),tickerInner=document.getElementById('ticker-inner'),
    stateBox=document.getElementById('ticker-state'),stateText=document.getElementById('ticker-state-text'),
    ageText=document.getElementById('ticker-age');
if(!ticker||!tickerInner||!stateBox||!stateText||!ageText)return;

/* MEXC spot miniTicker, official protobuf wrapper:
   PushDataV3ApiWrapper.publicMiniTicker = field 309, and inside it
   symbol = 1, price = 2, zonedRate = 4. The @24H subscription makes
   zonedRate the rolling 24-hour change. */
var SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ADAUSDT','LINKUSDT'];
var LABELS={BTCUSDT:'BTC/USDT',ETHUSDT:'ETH/USDT',SOLUSDT:'SOL/USDT',XRPUSDT:'XRP/USDT',
            BNBUSDT:'BNB/USDT',DOGEUSDT:'DOGE/USDT',ADAUSDT:'ADA/USDT',LINKUSDT:'LINK/USDT'};
var ALLOW=Object.create(null);
SYMBOLS.forEach(function(symbol){ALLOW[symbol]=LABELS[symbol];});
var WS_URL='wss://wbs-api.mexc.com/ws';
var MACRO_URL='https://stooq.com/q/l/?s=%5Endq,%5Espx,xauusd,dx.f,%5Etnx,cl.f&f=sd2t2ohlcv&h&e=csv';
var MACRO_NAMES={'^ndq':'NASDAQ','^spx':'S&P 500','xauusd':'GOLD','dx.f':'DXY','^tnx':'US 10Y','cl.f':'WTI'};
var STALE_MS=45000,UI_MS=5000,PING_MS=25000,RETRY_BASE=2000,RETRY_MAX=60000,
    ROTATE_MS=23*60*60*1000+50*60*1000;
var cryptoRows=Object.create(null),macroRows=[],ws=null,reconnectTimer=null,pingTimer=null,
    rotateTimer=null,lastValidAt=0,openedAt=0,retryAttempt=0;
var decoder=typeof TextDecoder!=='undefined'?new TextDecoder('utf-8'):null;

function decodeUtf8(bytes){
  if(decoder)return decoder.decode(bytes);
  var text='';
  for(var i=0;i<bytes.length;i++)text+=String.fromCharCode(bytes[i]);
  return text;
}
function readVarint(bytes,state){
  var value=0,mult=1,b;
  do{
    if(state.i>=bytes.length)throw new Error('varint');
    b=bytes[state.i++];
    value+=(b&0x7f)*mult;
    mult*=128;
    if(mult>9007199254740992)throw new Error('varint');
  }while(b&0x80);
  return value;
}
function parseFields(bytes){
  var fields=Object.create(null),state={i:0};
  while(state.i<bytes.length){
    var tag=readVarint(bytes,state),field=Math.floor(tag/8),wire=tag&7;
    if(!field)throw new Error('field');
    if(wire===0){fields[field]={wire:0,value:readVarint(bytes,state)};}
    else if(wire===1){
      if(state.i+8>bytes.length)throw new Error('fixed64');
      state.i+=8;
    }else if(wire===2){
      var length=readVarint(bytes,state);
      if(length<0||state.i+length>bytes.length)throw new Error('length');
      fields[field]={wire:2,value:bytes.subarray(state.i,state.i+length)};
      state.i+=length;
    }else if(wire===5){
      if(state.i+4>bytes.length)throw new Error('fixed32');
      state.i+=4;
    }else{
      throw new Error('wire');
    }
  }
  return fields;
}
function decimalField(entry,min,max){
  if(!entry||entry.wire!==2)return null;
  var raw=decodeUtf8(entry.value).trim();
  if(!raw||raw.length>32||!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw))return null;
  var value=Number(raw);
  if(!isFinite(value)||value<min||value>max)return null;
  return value;
}
function groupFixed(value,digits){
  var parts=value.toFixed(digits).split('.');
  parts[0]=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',');
  return parts.join('.');
}
function formatPrice(value){
  if(value>=1)return groupFixed(value,2);
  if(value>=0.01)return groupFixed(value,4);
  return groupFixed(value,8);
}
function formatChange(value){
  if(Math.abs(value)<0.005)return '0.00%';
  var sign=value>0?'+':(value<0?'':'');
  var abs=Math.abs(value);
  return sign+value.toFixed(abs>=100?0:(abs>=10?1:2))+'%';
}
function formatAge(ms){
  if(ms<8000)return '방금';
  var seconds=Math.round(ms/1000);
  if(seconds<90)return seconds+'초 전';
  var minutes=Math.round(seconds/60);
  return minutes+'분 전';
}
function setState(kind,text){
  if(stateBox.getAttribute('data-state')!==kind)stateBox.setAttribute('data-state',kind);
  if(stateText.textContent!==text)stateText.textContent=text;
}
function makeTick(label,price,change,kind){
  var row=document.createElement('span');row.className='tick';
  var name=document.createElement('b');name.textContent=label;
  var value=document.createElement('span');value.textContent=formatPrice(price);
  var rate=document.createElement('span');rate.className=change>0?'up':(change<0?'dn':'flat');
  rate.textContent=formatChange(change);
  row.title=label+(kind==='crypto'?' · 24시간 변동':' · 당일 변동');
  row.append(name,document.createTextNode(' '),value,document.createTextNode(' '),rate);
  return row;
}
function renderTicker(){
  var sequence=document.createElement('span');sequence.className='ticker-seq';
  SYMBOLS.forEach(function(symbol){
    var row=cryptoRows[symbol];
    if(row)sequence.append(makeTick(ALLOW[symbol],row.price,row.change,'crypto'));
  });
  macroRows.forEach(function(row){
    sequence.append(makeTick(row.label,row.price,row.change,'macro'));
  });
  if(!sequence.childNodes.length){tickerInner.replaceChildren();return;}
  var duplicate=sequence.cloneNode(true);duplicate.setAttribute('aria-hidden','true');
  tickerInner.replaceChildren(sequence,duplicate);
}
function readMiniTicker(buffer){
  try{
    var wrapper=parseFields(new Uint8Array(buffer)),body=wrapper[309];
    if(!body||body.wire!==2)return;
    var item=parseFields(body.value);
    var symbol=item[1]&&item[1].wire===2?decodeUtf8(item[1].value).trim().toUpperCase():'';
    if(!symbol&&wrapper[3]&&wrapper[3].wire===2)symbol=decodeUtf8(wrapper[3].value).trim().toUpperCase();
    if(!ALLOW[symbol])return;
    var price=decimalField(item[2],0,1000000000000);
    var change=decimalField(item[4],-1,1000);
    if(price===null||price<=0||change===null)return;
    /* MEXC returns zonedRate as a fraction (0.0766 is 7.66%), so convert once. */
    cryptoRows[symbol]={price:price,change:change*100};
    lastValidAt=Date.now();retryAttempt=0;
    renderTicker();updateFreshness();
  }catch(error){}
}
function handleText(data){
  var message;
  try{message=JSON.parse(data);}catch(error){return;}
  if(!message||typeof message!=='object')return;
  if(message.msg==='PONG')return;
}
function handleMessage(data){
  if(typeof data==='string'){handleText(data);return;}
  if(data instanceof ArrayBuffer){readMiniTicker(data);return;}
  if(typeof Blob!=='undefined'&&data instanceof Blob){
    try{data.arrayBuffer().then(readMiniTicker).catch(function(){});}catch(error){}
  }
}
function updateFreshness(){
  var now=Date.now();
  if(lastValidAt)ageText.textContent='· '+formatAge(now-lastValidAt);
  else ageText.textContent='';
  if(!ws||ws.readyState!==1)return;
  if(lastValidAt&&now-lastValidAt>STALE_MS){setState('stale','MEXC 지연 · 24시간 변동');}
  else if(lastValidAt){setState('live','MEXC 실시간 · 24시간 변동');}
  else if(openedAt&&now-openedAt>STALE_MS){setState('stale','MEXC 연결됨 · 시세 대기');}
}
function clearSocketTimers(){
  if(pingTimer){clearInterval(pingTimer);pingTimer=null;}
  if(rotateTimer){clearTimeout(rotateTimer);rotateTimer=null;}
}
function closeSocket(){
  clearSocketTimers();
  if(ws){
    ws.onopen=ws.onmessage=ws.onerror=ws.onclose=null;
    try{ws.close();}catch(error){}
    ws=null;
  }
}
function scheduleRetry(){
  clearSocketTimers();
  retryAttempt+=1;
  var delay=Math.min(RETRY_MAX,RETRY_BASE*Math.pow(1.8,retryAttempt-1));
  delay=Math.round(delay*(0.85+Math.random()*0.3));
  setState('reconnecting','MEXC 재연결 중');
  if(reconnectTimer){clearTimeout(reconnectTimer);}
  reconnectTimer=setTimeout(connect,delay);
}
function connect(){
  closeSocket();
  if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}
  lastValidAt=0;openedAt=0;
  setState('connecting',retryAttempt?'MEXC 재연결 중':'MEXC 연결 중');
  if(typeof WebSocket==='undefined'){setState('unsupported','MEXC 실시간 미지원');return;}
  var socket;
  try{socket=new WebSocket(WS_URL);}catch(error){scheduleRetry();return;}
  ws=socket;socket.binaryType='arraybuffer';
  socket.onopen=function(){
    if(ws!==socket)return;
    openedAt=Date.now();
    setState('connecting','MEXC 구독 중');
    try{
      socket.send(JSON.stringify({
        method:'SUBSCRIPTION',
        params:SYMBOLS.map(function(symbol){
          return 'spot@public.miniTicker.v3.api.pb@'+symbol+'@24H';
        })
      }));
    }catch(error){}
    pingTimer=setInterval(function(){
      if(ws===socket&&socket.readyState===1){try{socket.send('{"method":"PING"}');}catch(error){}}
    },PING_MS);
    /* The documented connection limit is 24 hours. Rotate at 23h50m so the
       ticker reconnects before the server closes it. */
    rotateTimer=setTimeout(function(){if(ws===socket)connect();},ROTATE_MS);
  };
  socket.onmessage=function(event){if(ws===socket)handleMessage(event.data);};
  socket.onerror=function(){if(ws!==socket)return;try{socket.close();}catch(error){}};
  socket.onclose=function(){
    if(ws!==socket)return;
    ws=null;clearSocketTimers();lastValidAt=0;openedAt=0;ageText.textContent='';
    scheduleRetry();
  };
}
async function loadMacro(){
  try{
    var controller=new AbortController(),timeout=setTimeout(function(){controller.abort();},8000);
    var response=await fetch(MACRO_URL,{signal:controller.signal,cache:'no-store'});
    clearTimeout(timeout);
    if(!response.ok)return;
    var text=await response.text(),lines=text.trim().split(/\r?\n/).slice(1),rows=[];
    for(var i=0;i<lines.length;i++){
      var cells=lines[i].split(',');
      if(cells.length<7)continue;
      var symbol=String(cells[0]||'').toLowerCase(),close=Number(cells[6]),open=Number(cells[3]);
      if(!isFinite(close)||!isFinite(open)||open<=0||close<=0)continue;
      var change=(close-open)/open*100;
      if(!isFinite(change))continue;
      rows.push({label:MACRO_NAMES[symbol]||symbol.toUpperCase(),price:close,change:change});
    }
    if(rows.length){macroRows=rows;renderTicker();}
  }catch(error){}
}
ticker.hidden=false;
renderTicker();
connect();
updateFreshness();
loadMacro();
setInterval(updateFreshness,UI_MS);
setInterval(function(){if(!document.hidden)loadMacro();},300000);
window.addEventListener('online',function(){
  if(!ws||ws.readyState>1){if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}connect();}
});
document.addEventListener('visibilitychange',function(){
  if(document.hidden)return;
  updateFreshness();
  if(!ws||ws.readyState>1){if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}connect();}
});
window.addEventListener('pagehide',function(){closeSocket();if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}});
window.addEventListener('pageshow',function(event){if(event.persisted)connect();});
})();
</script>
<script>
(function(){
'use strict';
var section=document.getElementById('kinetic'),button=document.getElementById('kinetic-toggle'),
    status=document.getElementById('kinetic-status');
if(!section||!button||!status)return;
var query=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
function setPaused(paused){
  section.setAttribute('data-paused',paused?'1':'0');
  button.textContent=paused?'다시 재생':'일시정지';
  button.setAttribute('aria-pressed',String(paused));
  status.textContent=paused?'애니메이션 일시정지됨':'애니메이션 재생 중';
}
function applyPreference(){
  var reduced=!!(query&&query.matches);
  button.hidden=true;
  if(reduced){
    section.classList.remove('motion-enabled');
    section.setAttribute('data-paused','1');
    button.textContent='동작 줄임 · 정지';
    button.setAttribute('aria-pressed','true');
    button.disabled=true;
    status.textContent='동작 줄임 설정이 켜져 있어 애니메이션을 재생하지 않습니다.';
  }else{
    button.disabled=false;
    setPaused(false);
    section.classList.add('motion-enabled');
    button.hidden=false;
  }
}
button.addEventListener('click',function(){
  if(button.disabled||!section.classList.contains('motion-enabled'))return;
  setPaused(section.getAttribute('data-paused')!=='1');
});
if(query){
  if(query.addEventListener)query.addEventListener('change',applyPreference);
  else if(query.addListener)query.addListener(applyPreference);
}
applyPreference();
})();
</script>
<script>
(function(){
'use strict';
var root=document.documentElement;
try{
  if(!root.classList.contains('reveal-enabled'))return;
  if(!('IntersectionObserver' in window)){root.classList.remove('reveal-enabled');return;}
  var items=[].slice.call(document.querySelectorAll('.section,.about'));
  if(!items.length){root.classList.remove('reveal-enabled');return;}
  var observer=new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(!entry.isIntersecting)return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  },{threshold:.08,rootMargin:'0px 0px -8% 0px'});
  items.forEach(function(item){observer.observe(item);});
  var query=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
  function stopReveal(){
    if(!query||!query.matches)return;
    observer.disconnect();
    root.classList.remove('reveal-enabled');
    items.forEach(function(item){item.classList.add('is-visible');});
  }
  if(query){
    if(query.addEventListener)query.addEventListener('change',stopReveal);
    else if(query.addListener)query.addListener(stopReveal);
  }
}catch(error){root.classList.remove('reveal-enabled');}
})();
</script>
<script>
(function(){
'use strict';
const list=document.getElementById('news-list'), status=document.getElementById('update-status'), retry=document.getElementById('retry');
let busy=false, hasNews=false;
const fmt=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Bangkok',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
function displayStamp(value){const p=fmt.formatToParts(new Date(value)),get=k=>(p.find(x=>x.type===k)||{}).value||'';
return get('month')+'월 '+get('day')+'일 '+get('hour')+':'+get('minute')+' ICT'}
function cleanTitle(value){return String(value||'').replace(/(?:https?:\/\/|www\.)\S+|\b[a-z0-9.-]+\.(?:com|org|net|rs|co\.th|go\.th)\/\S+|\breut\.rs\S*/gi,'').replace(/\s+-\s+[^-]+$/,'').replace(/\s+/g,' ').trim();}
function safeLink(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch(e){return null;}}
function relevant(a){if(a.category&&a.category!=='일반')return true;return /금리|금값|금 가격|금 선물|은값|원유|유가|물가|고용|실업|관세|중앙은행|연준|증시|주식|채권|환율|달러|실적|비트코인|암호화폐|가상자산|이더리움|인플레|경기|\b(?:stocks?|equities|bonds?|yields?|gold|silver|oil|crude|inflation|payrolls|tariffs?|fed|fomc|gdp|cpi|pce|earnings|bitcoin|crypto|ethereum|etf|forex|rates?|central bank)\b/i.test(String(a.title||''));}
function selectNews(articles){const seen=new Set();return articles.filter(a=>{if(a.region!=='글로벌'||!relevant(a))return false;const title=cleanTitle(a.title);const key=title.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');const date=Date.parse(a.published_at);if(key.length<8||!safeLink(a.link)||!Number.isFinite(date)||date>Date.now()+60000||Date.now()-date>86400000||seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at)).slice(0,8);}
function hostOf(u){try{const h=new URL(u).hostname.toLowerCase().replace(/^www[.]/,'');return h}catch(e){return ''}}
function srcLabel(a){if(!a.original_link)return a.source||'';return String(a.original_source||'').trim()||hostOf(a.original_link)||a.source||''}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function render(articles){list.replaceChildren();if(!articles.length){const p=document.createElement('p');p.className='empty';p.textContent='최근 24시간에 표시할 뉴스가 없습니다.';list.append(p);return;}
for(const a of articles){const row=document.createElement('div');row.className='news-row';const link=document.createElement('a');link.href=safeLink(a.original_link||a.link);link.target='_blank';link.rel='noopener noreferrer';
const time=document.createElement('span');time.className='ntime';time.textContent=displayStamp(a.published_at);
const topic=document.createElement('span');topic.className='ntopic';topic.textContent=a.category||'경제';
const title=document.createElement('span');title.className='ntitle';title.innerHTML=esc(cleanTitle(a.title))+' <span class="ext">↗</span>';
const src=document.createElement('span');src.className='ntime';src.textContent=srcLabel(a)||'';
link.append(time,topic,title);if(src.textContent)link.append(src);row.append(link);list.append(row);}hasNews=true;}
async function refresh(){if(busy)return;busy=true;retry.disabled=true;list.setAttribute('aria-busy','true');const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);try{const response=await fetch('/api/news?region='+encodeURIComponent('글로벌')+'&hours=24&limit=100&lang=ko',{cache:'no-cache',signal:controller.signal});if(!response.ok)throw new Error('http');const data=await response.json();if(!Array.isArray(data.articles))throw new Error('schema');render(selectNews(data.articles));const updated=Date.parse(data.updated_at);if(Number.isFinite(updated)&&updated<=Date.now()+60000){const age=Date.now()-updated;status.textContent=(age>35*60000?'! 갱신 지연 · ':'✓ ')+displayStamp(updated);retry.hidden=age<=35*60000;}else{status.textContent='? 수집 시각 확인 불가';retry.hidden=false;}}
catch(error){status.textContent=hasNews?'! 갱신 실패 · 이전 목록 표시 중':'! 뉴스 로드 실패';retry.hidden=false;if(!hasNews){list.replaceChildren();const p=document.createElement('p');p.className='empty';p.textContent='잠시 후 다시 시도해 주세요.';list.append(p);}}
finally{clearTimeout(timeout);busy=false;retry.disabled=false;list.setAttribute('aria-busy','false');}}
retry.addEventListener('click',refresh);refresh();setInterval(()=>{if(!document.hidden)refresh();},120000);
})();
</script>
</body></html>
'''


def stylesheet() -> str:
    """The whole <style> block.

    The Thailand landing shows the same type and motion. Keeping its own copy would let the two
    pages drift, and the site would start to read as two sites.
    """
    start = PAGE.index("<style>")
    end = PAGE.index("</style>") + len("</style>")
    return (PAGE[start:end]
            .replace("__SHARED_THEME_CSS__", theme.shared_css())
            .replace("__INDICATOR_CSS__", theme.INDICATOR_CSS))


display_date = theme.display_date


def render_indicator_cards() -> str:
    cards = []
    for indicator in INDICATORS:
        fields = {key: escape(str(value), quote=True) for key, value in indicator.items()}
        fields["url"] = "https://kr.tradingview.com/script/{}/".format(fields["code"])
        cards.append(
            '<article class="indicator"><a class="chart-open" href="{url}" target="_blank" rel="noopener noreferrer">'
            '<img src="{image}" width="1404" height="1281" loading="lazy" decoding="async" alt="{alt}">'
            '<span class="chart-caption">적용 예시 · 눌러서 지표 페이지로</span></a>'
            '<h3>{title}</h3><p>{description}</p>'
            '<span class="free">무료 공개</span><br><a class="button" href="{url}" target="_blank" rel="noopener noreferrer">'
            '트레이딩뷰에서 보기 ↗</a></article>'.format(**fields)
        )
    return "".join(cards)


def _blog_teaser_summary(markdown: str) -> str:
    """Choose the first market-condition paragraph and flatten it for a short teaser."""
    lines = str(markdown or "").splitlines()
    preferred = False
    fallback = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = line.lstrip("# ").strip()
            if heading == "관점 전환 조건":
                preferred = True
            elif preferred:
                break
            continue
        if not fallback:
            fallback = line
        if preferred:
            text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
            text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
            text = re.sub(r"[*_~]", "", text).replace("\x60", "")
            return " ".join(text.split())[:180]
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", fallback)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_~]", "", text).replace("\x60", "")
    return " ".join(text.split())[:180]


def _homepage_title(title: str) -> str:
    """Drop only the redundant dated suffix from a homepage headline.

    The full title stays on /blog/<slug>/; the homepage already prints the date
    below the headline, so repeating it in the title only pushes the text wider.
    """
    value = str(title or "")
    shortened = re.sub(r"\s*[|·]\s*\d{1,2}월\s*\d{1,2}일.*$", "", value).strip()
    return shortened or value


def _homepage_post_cards(posts) -> str:
    from urllib.parse import quote

    cards = []
    for post in posts:
        slug = str(post.get("original_slug") or "").strip()
        if not slug:
            continue
        cards.append({
            "date": str(post.get("date") or ""),
            "title": _homepage_title(str(post.get("title") or "")),
            "url": "/blog/{}/".format(quote(slug, safe="-._~")),
            "summary": _blog_teaser_summary(post.get("body") or ""),
        })
    return _render_post_cards(cards[:3])


def _render_post_cards(posts) -> str:
    cards = []
    for post in posts:
        fields = {key: escape(str(value or ""), quote=True) for key, value in post.items()}
        fields["visible_date"] = escape(theme.display_date(str(post.get("date", ""))))
        cards.append(
            '<article class="post"><h3><a href="{url}">{title}</a></h3>'
            '<time datetime="{date}">{visible_date}</time>'
            '<p>{summary}</p><a class="read" href="{url}">블로그 글 읽기 →</a></article>'.format(**fields)
        )
    return "".join(cards)


def _standalone_page(title: str, description: str, content: str, extra_css: str = "",
                     active: str = "") -> str:
    safe_title = escape(title)
    safe_description = escape(description)
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="description" content="{description}"><title>{title} | TeemoBKK</title>'
        '<style>{shared_css}{extra_css}{page_css}</style>{head_script}</head><body>'
        '<a class="skip" href="#main">본문으로 건너뛰기</a>{header}'
        '<main class="page-main" id="main"><header class="page-head">'
        '<h1 class="page-title">{title}</h1>'
        '<p class="page-intro">{description}</p></header>{content}'
        '<a class="page-back" href="/">← 홈으로</a></main>{footer}</body></html>'
    ).format(
        description=safe_description,
        title=safe_title,
        shared_css=theme.shared_css(),
        extra_css=extra_css,
        page_css=theme.SUBPAGE_CSS,
        head_script=theme.theme_head_script(),
        header=theme.render_header(active),
        content=content,
        footer=theme.render_footer(),
    )


def render_perspectives_page(posts=None) -> str:
    """Render the market-perspective archive from canonical blog posts."""
    if posts is None:
        from pages.build.page_build import editorial_snapshot_from_blog

        selected = editorial_snapshot_from_blog()[:10]
    else:
        selected = list(posts)[:10]
    entries = []
    for post in selected:
        fields = {key: escape(str(value or ""), quote=True) for key, value in post.items()}
        date = str(post.get("date", ""))
        fields["visible_date"] = escape(theme.display_date(date))
        fields["date"] = escape(date, quote=True)
        entries.append(
            '<article class="page-post"><h2><a href="{url}">{title}</a></h2>'
            '<time datetime="{date}">{visible_date}</time>'
            '<p>{summary}</p><a class="read" href="{url}">'
            '블로그 글 읽기 →</a></article>'.format(**fields)
        )
    if not entries:
        entries.append('<p class="empty">현재 표시할 관점 글이 없습니다.</p>')
    content = '<div class="page-posts">{}</div>'.format("".join(entries))
    return _standalone_page(
        "시장 관점", "시장 관점은 짧은 요약으로 살펴보고, 전체 글은 블로그에서 읽을 수 있습니다.", content,
        active="perspectives",
    )


def blog_markdown_to_html(body: str) -> str:
    """Minimal Markdown → HTML for imported briefing posts (stdlib only).

    Covers what the converted files use: ``#``/``##`` headings, ``**bold**``,
    ``*italic*``, ``>`` quotes, ``-`` lists, paragraphs. Everything is
    HTML-escaped first, so raw HTML in the source can never break the page.
    """
    import re

    blocks = []
    in_list = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append("<li>%s</li>" % _blog_inline(line[2:]))
            continue
        if in_list:
            blocks.append("</ul>")
            in_list = False
        if not line:
            continue
        if line.startswith("### "):
            blocks.append("<h4>%s</h4>" % _blog_inline(line[4:]))
        elif line.startswith("## "):
            blocks.append("<h3>%s</h3>" % _blog_inline(line[3:]))
        elif line.startswith("# "):
            blocks.append("<h3>%s</h3>" % _blog_inline(line[2:]))
        elif line.startswith("> "):
            blocks.append("<blockquote><p>%s</p></blockquote>" % _blog_inline(line[2:]))
        else:
            blocks.append("<p>%s</p>" % _blog_inline(line))
    if in_list:
        blocks.append("</ul>")
    return "\n".join(blocks)


def _blog_inline(text: str) -> str:
    import re

    safe = escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"\*(.+?)\*", r"<em>\1</em>", safe)
    safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
    return safe


def _render_blog_list(posts) -> str:
    """Render /blog/ list from imported posts (frontmatter date order)."""
    entries = []
    for post in sorted(posts, key=lambda p: str(p.get("date", "")), reverse=True):
        slug = escape(str(post.get("original_slug", "")), quote=True)
        title = escape(str(post.get("title", "")))
        date = escape(str(post.get("date", "")), quote=True)
        visible = escape(theme.display_date(str(post.get("date", ""))))
        entries.append(
            '<article class="page-post"><h2><a href="/blog/{slug}/">{title}</a></h2>'
            '<time datetime="{date}">{visible}</time></article>'.format(
                date=date, visible=visible, slug=slug, title=title))
    if not entries:
        entries.append('<p class="empty">현재 표시할 블로그 글이 없습니다.</p>')
    return _standalone_page(
        "블로그", "공개된 관점 브리핑 글을 모았습니다.",
        '<div class="page-posts">{}</div>'.format("".join(entries)),
        active="blog",
    )


def _render_blog_post(post, body_html: str) -> str:
    """Render one /blog/<slug>/ page. Title/date come from frontmatter."""
    title = str(post.get("title", ""))
    date = str(post.get("date", ""))
    content = (
        '<p class="post-meta"><time datetime="{date}">{visible}</time>'
        ' · 관점 브리핑</p>'
        '<div class="post-body">{body}</div>'
        '<a class="page-back" href="/blog/">← 목록으로</a>'.format(
            date=escape(date, quote=True),
            visible=escape(theme.display_date(date)),
            body=body_html,
        )
    )
    return _standalone_page(title, title, content, active="blog")


def _with_canonical(page: str, url: str) -> str:
    tag = '<link rel="canonical" href="{}">'.format(escape(url, quote=True))
    return page.replace("</head>", tag + "</head>", 1)


def render_blog_list(posts) -> str:
    """Render the blog index with its stable apex-domain canonical URL."""
    return _with_canonical(
        _render_blog_list(posts),
        "https://teemobkk.io/blog/",
    )


def render_blog_post(post, body_html: str) -> str:
    """Render a post with a host-independent canonical URL."""
    from urllib.parse import quote

    slug = quote(str(post.get("original_slug", "")), safe="-._~")
    return _with_canonical(
        _render_blog_post(post, body_html),
        "https://teemobkk.io/blog/{}/".format(slug),
    )


def render_indicators_page() -> str:
    """Render the complete public TradingView indicator catalogue."""
    content = (
        '<div class="indicators">{}</div>'
        '<a class="page-back" href="{}" target="_blank" rel="noopener noreferrer me">'
        '트레이딩뷰 프로필에서 전체 지표 보기 ↗</a>'
    ).format(render_indicator_cards(), escape(INDICATOR_PROFILE_URL, quote=True))
    return _standalone_page(
        "트레이딩뷰 지표",
        "차트 구조와 파동을 살펴보는 공개 지표입니다. 분석 보조 도구로 활용하세요.",
        content, extra_css=theme.INDICATOR_CSS, active="indicators",
    )


def render_landing(posts=None) -> str:
    selected = [] if posts is None else list(posts)
    if not selected or not any(post.get("original_slug") for post in selected):
        from pages.build.page_build import read_blog_posts

        selected = read_blog_posts()
    cards = _homepage_post_cards(selected[:3])
    return (PAGE.replace('__POSTS__', cards)
            .replace('__SHARED_THEME_CSS__', theme.shared_css())
            .replace('__INDICATOR_CSS__', theme.INDICATOR_CSS)
            .replace('__INDICATORS__', render_indicator_cards())
            .replace('__THEME_HEAD__', theme.theme_head_script())
            .replace('__HEADER__', theme.render_header("home"))
            .replace('__FOOTER__', theme.render_footer()))
