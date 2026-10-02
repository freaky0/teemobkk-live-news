"""Market-first public homepage, independent of dashboard templates.

Keep external publishing links in EDITORIAL_POSTS, not in navigation labels.
Script previews are actual publication images, never reconstructed charts.
"""
from html import escape
from datetime import date
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
<title>TeemoBKK | 차트보다 먼저 읽는 뉴스</title>
<meta name="description" content="시장이 움직이는 이유를 전합니다. 금리와 정책, 지정학과 수급까지. 트레이더의 경제 뉴스와 시장 관점, 무료 트레이딩뷰 지표.">
<meta name="theme-color" content="#faf8f3">
<meta name="color-scheme" content="dark">
<meta property="og:type" content="website">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="TeemoBKK | 차트보다 먼저 읽는 뉴스">
<meta property="og:description" content="시장이 움직이는 이유를 전합니다. 금리와 정책, 지정학과 수급까지.">
<meta property="og:url" content="https://teemobkk.io/">
<meta property="og:image" content="https://s3.tradingview.com/e/e3AY6AxC_big.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://teemobkk.io/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
:root{color-scheme:light;--bg:#faf8f3;--surface:#ffffff;--surface2:#f3f0e8;--text:#1a1c1a;--muted:#5f665f;--dim:#9aa099;--line:#e5e0d3;--accent:#0a7a4a;--accent-dim:rgba(10,122,74,.10);--down:#d33f3f;--radius:6px;--sans:system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"D2Coding","JetBrains Mono","Courier New",monospace}
*{box-sizing:border-box}html{scroll-padding-top:92px}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.65;-webkit-font-smoothing:antialiased}a{color:inherit;text-decoration:none}button{font:inherit}a,button{-webkit-tap-highlight-color:transparent}a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:4px}a:hover{color:var(--accent)}button{cursor:pointer}[hidden]{display:none!important}
.wrap{max-width:1120px;margin:auto;padding-inline:28px}
.skip{position:absolute;left:16px;top:-100px;background:var(--accent);color:#ffffff;padding:12px;z-index:50;font-weight:700}.skip:focus{top:12px}
.ticker{background:#060a10;border-bottom:1px solid var(--line);overflow:hidden;white-space:nowrap}
.ticker-inner{display:inline-flex;padding:7px 0;animation:tick 28s linear infinite}
.ticker:hover .ticker-inner{animation-play-state:paused}
.tick{display:inline-flex;align-items:center;gap:8px;padding:0 22px;font:12px/1.6 var(--mono);color:var(--muted);border-right:1px solid var(--line)}
.tick b{color:var(--text);font-weight:700}
.tick .up{color:var(--accent)}.tick .dn{color:var(--down)}
@keyframes tick{to{transform:translateX(-50%)}}
.top{border-bottom:1px solid var(--line);background:rgba(250,248,243,.94);backdrop-filter:blur(8px);position:sticky;top:0;z-index:20}
.nav{min-height:66px;display:flex;align-items:center;gap:34px}
.brand{font-family:var(--mono);font-weight:700;font-size:18px;letter-spacing:-.02em;white-space:nowrap}
.brand .prompt{color:var(--accent)}
.brand .cursor{display:inline-block;width:9px;height:17px;background:var(--accent);vertical-align:-3px;margin-left:5px;animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
nav{display:flex;gap:26px;align-items:center;flex:1}
nav a{font-size:13.5px;font-weight:600;padding-block:12px;color:var(--muted)}
nav a:hover{color:var(--accent)}
nav a.secondary{margin-left:auto;font-family:var(--mono);font-size:12.5px}
.hero{position:relative;padding:72px 0 52px;max-width:900px;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(rgba(10,122,74,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(10,122,74,.06) 1px,transparent 1px);background-size:44px 44px;-webkit-mask-image:radial-gradient(ellipse 90% 90% at 30% 20%,#000 30%,transparent 75%);mask-image:radial-gradient(ellipse 90% 90% at 30% 20%,#000 30%,transparent 75%)}
.hero::after{content:"";position:absolute;top:0;right:0;width:420px;height:340px;pointer-events:none;opacity:.35;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 420 340'%3E%3Cg%3E%3Crect x='40' y='180' width='26' height='90' fill='%230a7a4a' opacity='.45'/%3E%3Cline x1='53' y1='150' x2='53' y2='290' stroke='%230a7a4a' stroke-width='3' opacity='.45'/%3E%3Crect x='90' y='120' width='26' height='110' fill='%230a7a4a' opacity='.5'/%3E%3Cline x1='103' y1='90' x2='103' y2='250' stroke='%230a7a4a' stroke-width='3' opacity='.5'/%3E%3Crect x='140' y='80' width='26' height='130' fill='%230a7a4a' opacity='.55'/%3E%3Cline x1='153' y1='50' x2='153' y2='230' stroke='%230a7a4a' stroke-width='3' opacity='.55'/%3E%3Crect x='190' y='40' width='26' height='100' fill='%23d33f3f' opacity='.45'/%3E%3Cline x1='203' y1='15' x2='203' y2='160' stroke='%23d33f3f' stroke-width='3' opacity='.45'/%3E%3Crect x='240' y='60' width='26' height='120' fill='%230a7a4a' opacity='.5'/%3E%3Cline x1='253' y1='30' x2='253' y2='200' stroke='%230a7a4a' stroke-width='3' opacity='.5'/%3E%3Crect x='290' y='30' width='26' height='60' fill='%23d33f3f' opacity='.4'/%3E%3Cline x1='303' y1='10' x2='303' y2='110' stroke='%23d33f3f' stroke-width='3' opacity='.4'/%3E%3C/g%3E%3C/svg%3E") no-repeat top right;background-size:contain;-webkit-mask-image:linear-gradient(to left,#000 40%,transparent 95%);mask-image:linear-gradient(to left,#000 40%,transparent 95%)}
.hero>*{position:relative}
.eyebrow{font-family:var(--mono);font-size:12.5px;color:var(--accent);margin:0 0 18px;letter-spacing:.02em}
.eyebrow::before{content:"> "}
h1{font-size:clamp(36px,5.2vw,64px);line-height:1.18;letter-spacing:-.04em;margin:0;font-weight:800;word-break:keep-all}
h1 .hl{color:var(--accent)}
.intro{max-width:640px;color:var(--muted);font-size:16.5px;line-height:1.75;margin:20px 0 28px;word-break:keep-all}
.hero-tags{display:flex;gap:18px;flex-wrap:wrap;margin:0;font-family:var(--mono);font-size:11px;letter-spacing:.12em;color:var(--muted)}
.hero-tags span{white-space:nowrap}
.actions{display:flex;flex-wrap:wrap;gap:12px}
.button{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 22px;border-radius:var(--radius);border:1px solid var(--line);font-size:14px;font-weight:700;white-space:nowrap;background:var(--surface);color:var(--text);transition:border-color .25s,transform .25s}
.button.primary{background:var(--accent);border-color:var(--accent);color:#ffffff}
.button:hover{border-color:var(--accent);color:var(--accent)}
.button.primary:hover{color:#ffffff;transform:translateY(-1px)}
.button:active{transform:translateY(1px)}
section{scroll-margin-top:24px}
.section{padding:40px 0 48px;border-top:1px solid var(--line)}
.sec-head{display:flex;align-items:baseline;gap:14px;margin-bottom:6px}
.sec-tag{font-family:var(--mono);font-size:12px;color:var(--accent)}
h2{font-size:24px;line-height:1.3;letter-spacing:-.02em;margin:0;font-weight:700}
.section-intro{margin:8px 0 0;color:var(--muted);font-size:14.5px;max-width:720px;word-break:keep-all}
.section-link{display:inline-block;margin-top:16px;color:var(--accent);font-family:var(--mono);font-size:13px;font-weight:600}
.news-status{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin:20px 0 4px;color:var(--dim);font-family:var(--mono);font-size:11.5px}
.news-status .live{color:var(--accent)}
.retry{background:transparent;color:var(--accent);border:1px solid var(--line);border-radius:4px;min-height:34px;padding:4px 12px;font-family:var(--mono);font-size:12px}
.news-list{margin-top:8px;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);overflow:hidden}
.news-row{display:flex;align-items:baseline;gap:14px;padding:13px 18px;border-bottom:1px solid var(--line);transition:background .2s}
.news-row:last-child{border-bottom:0}
.news-row:hover{background:var(--surface2)}
.news-row a{display:flex;align-items:baseline;gap:14px;flex:1;min-width:0}
.news-row a:hover{color:var(--text)}
.ntime{font-family:var(--mono);font-size:11.5px;color:var(--dim);white-space:nowrap;flex-shrink:0}
.ntopic{font-family:var(--mono);font-size:11px;color:var(--accent);white-space:nowrap;flex-shrink:0;border:1px solid rgba(0,229,160,.3);border-radius:3px;padding:1px 7px;background:var(--accent-dim)}
.ntitle{font-size:15px;font-weight:500;line-height:1.55;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:keep-all}
.ntitle .ext{color:var(--dim);font-size:12px}
.empty{color:var(--muted);padding:26px 18px;font-size:14px}
.loading-line{height:14px;background:var(--surface2);margin:14px 18px;border-radius:3px;max-width:88%}
.loading-line.short{max-width:40%;height:11px}
.posts{display:grid;gap:0;margin-top:18px;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);overflow:hidden}
.post{padding:22px 24px;border-bottom:1px solid var(--line);transition:background .2s}
.post:last-child{border-bottom:0}
.post:hover{background:var(--surface2)}
.post time{font:11.5px/1.5 var(--mono);color:var(--dim)}
.post h3{font-size:19px;line-height:1.45;letter-spacing:-.015em;margin:8px 0;font-weight:700}
.post h3 a:hover{color:var(--accent)}
.post p{font-size:14.5px;color:var(--muted);margin:0;word-break:keep-all}
.post .read{display:inline-block;color:var(--accent);font-family:var(--mono);font-size:12.5px;margin-top:14px}
.note{font-size:12px;color:var(--dim);margin-top:20px;max-width:820px}
.indicators{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px}
.indicator{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:26px;transition:border-color .25s,transform .25s}
.indicator:hover{border-color:rgba(0,229,160,.45);transform:translateY(-3px)}
.indicator .icode{font-family:var(--mono);font-size:11px;color:var(--dim);letter-spacing:.08em}
.indicator h3{font-size:20px;margin:10px 0 8px;letter-spacing:-.015em;font-weight:700}
.indicator p{color:var(--muted);font-size:14px;margin:0 0 20px;word-break:keep-all;line-height:1.7}
.indicator .free{display:inline-block;font-family:var(--mono);font-size:11px;color:var(--accent);border:1px solid rgba(0,229,160,.3);background:var(--accent-dim);border-radius:3px;padding:3px 9px;margin-bottom:16px}
.about{display:grid;grid-template-columns:1fr 1fr;gap:56px}
.about p{color:var(--muted);font-size:14.5px;margin:10px 0;word-break:keep-all}
.about h3{font-size:16px;margin:0 0 10px;font-family:var(--mono);color:var(--accent);font-weight:600}
.about ul{list-style:none;padding:0;margin:0;color:var(--muted);font-size:13.5px}
.about li{margin:10px 0;padding-left:18px;position:relative}
.about li::before{content:"›";position:absolute;left:0;color:var(--accent)}
.footer{border-top:1px solid var(--line);padding:26px 0 38px;color:var(--dim);font-size:12px;background:#060a10}
.footer-row{display:flex;flex-wrap:wrap;justify-content:space-between;gap:14px;align-items:center}
.footer-row .fbrand{font-family:var(--mono);color:var(--muted)}
.footer p{margin:16px 0 0;max-width:860px;line-height:1.7}
.footer-links{display:flex;flex-wrap:wrap;gap:10px 20px;margin-top:16px;font-size:12.5px}
.footer-links a{color:var(--muted);text-decoration:underline;text-underline-offset:3px}
.footer-links a:hover{color:var(--accent)}
@media(max-width:767px){
.wrap{padding-inline:18px}
.nav{min-height:60px;gap:16px;flex-wrap:wrap;padding-block:10px}
.brand{font-size:16px}
nav{gap:18px;flex-basis:100%;order:2}
nav a{font-size:13px;padding:4px 0}
nav a.secondary{margin-left:0}
.hero{padding:44px 0 36px}
.intro{font-size:14.5px}
.intro br{display:none}
.section{padding:30px 0 36px}
h2{font-size:21px}
.indicators{grid-template-columns:1fr}
.about{grid-template-columns:1fr;gap:28px}
.news-row{gap:10px;padding:12px 14px}
.news-row a{flex-wrap:wrap;gap:6px 10px}
.ntime{font-size:10.5px}
.ntitle{font-size:14px;flex-basis:100%}
.tick{font-size:11px;padding:0 14px}
}
@media(prefers-reduced-motion:reduce){
.ticker-inner{animation:none}
.brand .cursor{animation:none}
*,*::before,*::after{transition:none!important}
}
</style>
</head>
<body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<div class="ticker" id="ticker" hidden aria-label="실시간 암호화폐 시세"><div class="ticker-inner" id="ticker-inner"></div></div>
<header class="top"><div class="wrap nav"><a class="brand" href="/" aria-label="TeemoBKK 홈"><span class="prompt">teemo@bkk</span>:~$ ./live-news<span class="cursor" aria-hidden="true"></span></a><nav aria-label="주요 메뉴"><a href="/news/ko/">경제 뉴스</a><a href="#perspectives">시장 관점</a><a href="#indicators">트레이딩뷰 지표</a><a class="secondary" href="/thai/">/thai ↗</a></nav></div></header>
<main id="main" class="wrap">
<section class="hero" aria-labelledby="headline"><p class="eyebrow">뉴스를 읽고, 관점을 세우고, 차트로 살펴봅니다.</p><h1 id="headline">차트보다 먼저 읽는 뉴스</h1><p class="intro">시장이 움직이는 이유를 전합니다.<br>금리와 정책, 지정학과 수급까지.</p><p class="hero-tags"><span>• MACRO</span><span>• CRYPTO</span><span>• MARKET STRUCTURE</span></p></section>
<section class="section" id="news" aria-labelledby="news-title"><div class="sec-head"><span class="sec-tag">01</span><h2 id="news-title">최근 경제 뉴스</h2></div><p class="section-intro">금리와 경기, 기업과 정책, 지정학까지. 시장에 연결되는 소식을 확인하세요.</p><div class="news-status"><span class="live">● 자동 수집 · 한국어로 표시</span><span id="update-status" role="status">수집 상태 확인 중</span><button class="retry" id="retry" type="button" hidden>다시 불러오기</button></div><div class="news-list" id="news-list" aria-busy="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div><noscript><p>뉴스 목록을 불러오려면 자바스크립트가 필요합니다. <a href="/news/ko/">경제 뉴스 페이지에서 확인하세요.</a></p></noscript><a class="section-link" href="/news/ko/">$ open /news/ko/ →</a></section>
<section class="section" id="perspectives" aria-labelledby="perspectives-title"><div class="sec-head"><span class="sec-tag">02</span><h2 id="perspectives-title">시장 관점</h2></div><p class="section-intro">뉴스와 차트를 어떻게 읽는지, 어떤 조건에서 생각을 바꾸는지. 트레이더로서의 판단을 기록합니다.</p><div class="posts">__POSTS__</div><p class="note">각 글은 작성 당시의 개인적인 관점입니다. 가격과 시나리오는 현재 시점과 다를 수 있습니다.</p></section>
<section class="section" id="indicators" aria-labelledby="indicators-title"><div class="sec-head"><span class="sec-tag">03</span><h2 id="indicators-title">직접 만든 트레이딩뷰 지표</h2></div><p class="section-intro">차트의 구조와 파동을 살펴보는 도구입니다. 공식 트레이딩뷰 페이지에서 무료로 사용할 수 있습니다.</p><div class="indicators">
<article class="indicator"><span class="icode">SCRIPT · fpkVFwl2</span><h3>Teemo Supply and Demand Zone</h3><p>수요/공급 구간 자동 식별, S/D Flip 추적, 거래량(HVP) 검증. 핵심 가격대에서 반응을 살펴보는 도구입니다.</p><span class="free">무료 공개</span><br><a class="button" href="https://kr.tradingview.com/script/fpkVFwl2/" target="_blank" rel="noopener noreferrer">트레이딩뷰에서 보기 ↗</a></article>
<article class="indicator"><span class="icode">SCRIPT · e3AY6AxC</span><h3>Teemo Elliott Wave</h3><p>엘리어트 파동 자동 카운팅, 실시간 추적. 파동 구조와 다음 시나리오를 살펴보는 보조 도구로 활용하세요.</p><span class="free">무료 공개</span><br><a class="button" href="https://kr.tradingview.com/script/e3AY6AxC/" target="_blank" rel="noopener noreferrer">트레이딩뷰에서 보기 ↗</a></article>
</div><a class="section-link" href="https://kr.tradingview.com/u/TeemoBKK/#published-scripts" target="_blank" rel="noopener noreferrer me">$ open profile → 전체 지표 보기 ↗</a><p class="note">파동 카운팅과 목표 구간은 진행 중인 가격에 따라 달라질 수 있습니다. 사용 조건과 설정은 각 지표 페이지에서 확인하세요.</p></section>
<section class="section about" aria-labelledby="about-title"><div><div class="sec-head"><span class="sec-tag">04</span><h2 id="about-title">TeemoBKK에 대하여</h2></div><p>경제 뉴스를 모으고, 시장을 바라보는 관점을 쓰며, 차트에서 사용하는 지표를 만듭니다.</p><p>뉴스는 시장의 맥락을 살피는 출발점입니다. 해석과 시나리오는 사실과 구분해 기록하겠습니다.</p></div><div><h3>읽기 전에</h3><ul><li>뉴스는 자동 수집한 원문 제목과 출처를 제공합니다.</li><li>시장 관점은 운영자의 개인적인 해석입니다.</li><li>지표는 분석 보조 도구이며 수익을 보장하지 않습니다.</li></ul></div></section>
</main>
<footer class="footer"><div class="wrap"><div class="footer-row"><span class="fbrand">teemo@bkk:~$ ./live-news --v2026</span><a href="/thai/">별도 소식 · 태국 교민 뉴스 ↗</a></div><p>뉴스는 자동 매매 신호가 아닙니다 · 중요한 사건은 원문과 공시로 확인하세요. 제공되는 글과 지표만으로 투자 결정을 내리지 마세요.</p><nav class="footer-links" aria-label="사이트 정보"><a href="/privacy/">개인정보 처리방침</a><a href="https://kr.tradingview.com/u/TeemoBKK/" target="_blank" rel="noopener noreferrer me">트레이딩뷰 TeemoBKK 공식 프로필 ↗</a><a href="https://t.me/+OegpDrwxnaBiOGNl" target="_blank" rel="noopener noreferrer">트레이딩뷰 TeemoBKK 텔레그램 대화방 초대 링크 ↗</a></nav><p class="note">텔레그램 링크는 외부 대화방으로 이동합니다.</p></div></footer>
<script>
(function(){
'use strict';
var ticker=document.getElementById('ticker'),tickerInner=document.getElementById('ticker-inner');
function kfmt(p){var n=parseFloat(p);if(!isFinite(n))return '—';if(n>=1000)return (n/1000).toFixed(1)+'K';if(n>=100)return n.toFixed(1);return n.toFixed(2);}
function pctfmt(p){var n=parseFloat(p);if(!isFinite(n))return '';return (n>=0?'+':'')+n.toFixed(1)+'%';}
function tickHTML(sym,price,chg){var n=parseFloat(chg);var cls=n>=0?'up':(n<0?'dn':'');
return '<span class="tick"><b>'+sym+'</b> '+kfmt(price)+' <span class="'+cls+'">'+pctfmt(chg)+'</span></span>';}
async function loadTicker(){
try{
var ctrl=new AbortController();var to=setTimeout(function(){ctrl.abort();},8000);
var res=await fetch('https://api.binance.com/api/v3/ticker/24hr?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22%5D',{signal:ctrl.signal});
clearTimeout(to);
if(!res.ok)throw new Error('http');
var data=await res.json();
if(!Array.isArray(data)||!data.length)throw new Error('schema');
var rows=data.map(function(d){var sym=String(d.symbol||'').replace('USDT','');return tickHTML(sym+'/USD',d.lastPrice,d.priceChangePercent);}).join('');
try{
var ctrl2=new AbortController();var to2=setTimeout(function(){ctrl2.abort();},8000);
var res2=await fetch('https://stooq.com/q/l/?s=%5Endq,%5Espx,xauusd,dx.f,%5Etnx,cl.f&f=sd2t2ohlcv&h&e=csv',{signal:ctrl2.signal});
clearTimeout(to2);
if(res2.ok){
var txt=await res2.text();
var lines=txt.trim().split('\n').slice(1);
var names={'^ndq':'NASDAQ','^spx':'S&P 500','xauusd':'GOLD','dx.f':'DXY','^tnx':'US 10Y','cl.f':'WTI'};
for(var i=0;i<lines.length;i++){
var c=lines[i].split(',');
if(c.length<7)continue;
var sym=c[0].toLowerCase(),close=parseFloat(c[6]),open=parseFloat(c[3]);
if(!isFinite(close)||!isFinite(open)||open===0)continue;
var chg=((close-open)/open*100).toFixed(2);
var label=names[sym]||sym.toUpperCase();
rows+=tickHTML(label,close,chg);
}
}
}catch(e2){}
tickerInner.innerHTML=rows+rows;
ticker.hidden=false;
}catch(e){ticker.hidden=true;}
}
if(ticker&&tickerInner){loadTicker();setInterval(function(){if(!document.hidden)loadTicker();},30000);}
})();
</script>
<script>
(function(){
'use strict';
const list=document.getElementById('news-list'), status=document.getElementById('update-status'), retry=document.getElementById('retry');
let busy=false, hasNews=false;
const fmt=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Bangkok',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
function displayStamp(value){const p=fmt.formatToParts(new Date(value)),get=k=>(p.find(x=>x.type===k)||{}).value||'';
return get('month')+'/'+get('day')+' '+get('hour')+':'+get('minute')}
function cleanTitle(value){return String(value||'').replace(/(?:https?:\/\/|www\.)\S+|\b[a-z0-9.-]+\.(?:com|org|net|rs|co\.th|go\.th)\/\S+|\breut\.rs\S*/gi,'').replace(/\s+-\s+[^-]+$/,'').replace(/\s+/g,' ').trim();}
function safeLink(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch(e){return null;}}
function relevant(a){if(a.category&&a.category!=='일반')return true;return /금리|금값|금 가격|금 선물|은값|원유|유가|물가|고용|실업|관세|중앙은행|연준|증시|주식|채권|환율|달러|실적|비트코인|암호화폐|가상자산|이더리움|인플레|경기|\b(?:stocks?|equities|bonds?|yields?|gold|silver|oil|crude|inflation|payrolls|tariffs?|fed|fomc|gdp|cpi|pce|earnings|bitcoin|crypto|ethereum|etf|forex|rates?|central bank)\b/i.test(String(a.title||''));}
function selectNews(articles){const seen=new Set();return articles.filter(a=>{if(a.region!=='글로벌'||!relevant(a))return false;const title=cleanTitle(a.title);const key=title.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');const date=Date.parse(a.published_at);if(key.length<8||!safeLink(a.link)||!Number.isFinite(date)||date>Date.now()+60000||Date.now()-date>86400000||seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at)).slice(0,8);}
function hostOf(u){try{const h=new URL(u).hostname.toLowerCase().replace(/^www[.]/,'');return h}catch(e){return ''}}
function srcLabel(a){if(!a.original_link)return a.source||'';return String(a.original_source||'').trim()||hostOf(a.original_link)||a.source||''}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function render(articles){list.replaceChildren();if(!articles.length){const p=document.createElement('p');p.className='empty';p.textContent='$ no results — 최근 24시간 뉴스가 없습니다.';list.append(p);return;}
for(const a of articles){const row=document.createElement('div');row.className='news-row';const link=document.createElement('a');link.href=safeLink(a.original_link||a.link);link.target='_blank';link.rel='noopener noreferrer';
const time=document.createElement('span');time.className='ntime';time.textContent=displayStamp(a.published_at);
const topic=document.createElement('span');topic.className='ntopic';topic.textContent=a.category||'경제';
const title=document.createElement('span');title.className='ntitle';title.innerHTML=esc(cleanTitle(a.title))+' <span class="ext">↗</span>';
const src=document.createElement('span');src.className='ntime';src.textContent=srcLabel(a)||'';
link.append(time,topic,title);if(src.textContent)link.append(src);row.append(link);list.append(row);}hasNews=true;}
async function refresh(){if(busy)return;busy=true;retry.disabled=true;list.setAttribute('aria-busy','true');const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);try{const response=await fetch('/api/news?region='+encodeURIComponent('글로벌')+'&hours=24&limit=100&lang=ko',{cache:'no-cache',signal:controller.signal});if(!response.ok)throw new Error('http');const data=await response.json();if(!Array.isArray(data.articles))throw new Error('schema');render(selectNews(data.articles));const updated=Date.parse(data.updated_at);if(Number.isFinite(updated)&&updated<=Date.now()+60000){const age=Date.now()-updated;status.textContent=(age>35*60000?'! 갱신 지연 · ':'✓ ')+displayStamp(updated)+' ICT';retry.hidden=age<=35*60000;}else{status.textContent='? 수집 시각 확인 불가';retry.hidden=false;}}
catch(error){status.textContent=hasNews?'! 갱신 실패 · 이전 목록 표시 중':'! 뉴스 로드 실패';retry.hidden=false;if(!hasNews){list.replaceChildren();const p=document.createElement('p');p.className='empty';p.textContent='$ retry — 잠시 후 다시 시도하세요.';list.append(p);}}
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
    return PAGE[start:end]


def display_date(value: str) -> str:
    """Use Korean date words for visible copy, keeping ISO 8601 in datetime."""
    try:
        day = date.fromisoformat(value)
        return f"{day.year}년 {day.month}월 {day.day}일"
    except (TypeError, ValueError):
        return value


def render_landing() -> str:
    posts = []
    for post in editorial_posts():
        fields = {k: escape(v, quote=True) for k, v in post.items()}
        fields['visible_date'] = escape(display_date(post['date']))
        posts.append('<article class="post"><time datetime="{date}">{visible_date}</time><h3><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3><p>{summary}</p><a class="read" href="{url}" target="_blank" rel="noopener noreferrer">관점 읽기 · 외부 글 ↗</a></article>'.format(**fields))
    return PAGE.replace('__POSTS__', ''.join(posts))
