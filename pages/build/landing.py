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
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK | 차트보다 먼저 읽는 뉴스</title>
<meta name="description" content="시장이 움직이는 이유를 전합니다. 금리와 정책, 지정학과 수급까지. 트레이더의 경제 뉴스와 시장 관점, 무료 트레이딩뷰 지표.">
<meta name="theme-color" content="#faf8f3">
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
[data-theme=dark] .top{background:color-mix(in srgb,var(--bg) 94%,transparent)}
*{box-sizing:border-box}html{scroll-padding-top:92px}body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.65;-webkit-font-smoothing:antialiased}a{color:inherit;text-decoration:none}button{font:inherit}a,button{-webkit-tap-highlight-color:transparent}a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:4px}a:hover{color:var(--accent)}button{cursor:pointer}[hidden]{display:none!important}
.wrap{max-width:1120px;margin:auto;padding-inline:28px}
.skip{position:absolute;left:16px;top:-100px;background:var(--accent);color:#ffffff;padding:12px;z-index:50;font-weight:700}.skip:focus{top:12px}
.ticker{background:var(--surface2);border-bottom:1px solid var(--line);overflow:hidden;white-space:nowrap}
.ticker-inner{display:inline-flex;padding:7px 0;animation:tick 28s linear infinite}
.ticker:hover .ticker-inner{animation-play-state:paused}
.tick{display:inline-flex;align-items:center;gap:8px;padding:0 22px;font:12px/1.6 var(--mono);color:var(--muted);border-right:1px solid var(--line)}
.tick b{color:var(--text);font-weight:700}
.tick .up{color:var(--accent)}.tick .dn{color:var(--down)}
@keyframes tick{to{transform:translateX(-50%)}}

.hero{display:grid;grid-template-columns:minmax(0,1.02fr) minmax(320px,.98fr);gap:34px;align-items:center;padding:48px 0 52px;max-width:none;overflow:visible}
.hero-copy{min-width:0}
.hero-visual,.section-visual,.perspective-visual{margin:0;overflow:hidden;background:var(--surface2)}
.hero-visual{aspect-ratio:16/10;max-height:470px}
.hero-visual img,.section-visual img,.perspective-visual img{display:block;width:100%;height:100%;object-fit:cover}
.hero-visual img{object-position:center}
.hero-visual figcaption,.section-visual figcaption,.perspective-visual figcaption{padding:9px 12px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);background:var(--surface)}
.section-visual,.perspective-visual{margin:22px 0 18px;aspect-ratio:16/9}
.perspective-visual{margin:20px 0;aspect-ratio:16/9}
.hero-actions{margin:0 0 18px}
.eyebrow{font-family:var(--mono);font-size:12.5px;color:var(--accent);margin:0 0 18px;letter-spacing:.02em}
.eyebrow::before{content:"> "}
h1{font-size:clamp(36px,5.2vw,64px);line-height:1.18;letter-spacing:-.04em;margin:0;font-weight:800;word-break:keep-all}
h1 .hl{color:var(--accent)}
.intro{max-width:640px;color:var(--muted);font-size:16.5px;line-height:1.75;margin:20px 0 28px;word-break:keep-all}
.hero-tags{display:flex;gap:18px;flex-wrap:wrap;margin:0;font-family:var(--mono);font-size:11px;letter-spacing:.12em;color:var(--muted)}
.hero-tags span{white-space:nowrap}
.actions{display:flex;flex-wrap:wrap;gap:12px}

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
__INDICATOR_CSS__
.about{display:grid;grid-template-columns:1fr 1fr;gap:56px}
.about p{color:var(--muted);font-size:14.5px;margin:10px 0;word-break:keep-all}
.about h3{font-size:16px;margin:0 0 10px;font-family:var(--mono);color:var(--accent);font-weight:600}
.about ul{list-style:none;padding:0;margin:0;color:var(--muted);font-size:13.5px}
.about li{margin:10px 0;padding-left:18px;position:relative}
.about li::before{content:"›";position:absolute;left:0;color:var(--accent)}

@media(max-width:767px){
.wrap{padding-inline:18px}
.nav{min-height:60px;gap:16px;flex-wrap:wrap;padding-block:10px}
.brand{font-size:16px}
.nav nav{gap:4px 12px;flex-basis:100%;order:2;flex-wrap:wrap}
.nav nav a{font-size:12px;padding:4px 2px;min-height:44px}
.nav nav a.secondary{margin-left:0}
.theme-toggle{margin-left:auto;min-height:44px;padding:6px 9px;font-size:11px}
.hero{grid-template-columns:1fr;gap:22px;padding:34px 0 36px}
.hero-visual{aspect-ratio:16/10;max-height:none}
.section-visual,.perspective-visual{aspect-ratio:16/9}
.intro{font-size:14.5px}
.intro br{display:none}
.section{padding:30px 0 36px}
h2{font-size:21px}
.about{grid-template-columns:1fr;gap:28px}
.news-row{gap:10px;padding:12px 14px}
.news-row a{flex-wrap:wrap;gap:6px 10px}
.ntime{font-size:10.5px}
.ntitle{font-size:14px;flex-basis:100%}
.tick{font-size:11px;padding:0 14px}
.retry{min-height:44px;padding:8px 12px}
}
@media(prefers-reduced-motion:reduce){
.ticker-inner{animation:none}
.brand .cursor{animation:none}
*,*::before,*::after{transition:none!important}
}

/* Editorial homepage: clear paper, ink and leaf-green; the shared dark theme remains available. */
:root{color-scheme:light;--bg:#f5f8f5;--surface:#fff;--surface2:#eef4ef;--text:#15231b;--muted:#405146;--dim:#526158;--line:#dce6dd;--accent:#28714f;--accent-dim:rgba(40,113,79,.1);--down:#bc4c4c;--radius:14px;--type-meta:13px;--type-body:16px;--type-subhead:20px;--type-heading:30px;--type-display:clamp(44px,6vw,86px)}
[data-theme=dark]{color-scheme:dark;--bg:#111914;--surface:#18231c;--surface2:#202e25;--text:#ebf1ec;--muted:#bac8bd;--dim:#aebbb2;--line:#33443a;--accent:#66cc91;--accent-dim:rgba(102,204,145,.14);--down:#ff8585}
body{line-height:1.72}
.wrap{max-width:1240px;padding-inline:clamp(22px,5vw,68px)}
.brand,.nav nav a.secondary,.footer-row .fbrand,.ticker .tick,.eyebrow,.hero-tags,.sec-tag,.section-link,.news-status,.retry,.ntime,.ntopic,.post time,.post .read,.note,.about h3{font-family:var(--sans)}
.brand{font-size:0;letter-spacing:0}
.brand::before{content:"TeemoBKK";display:inline-block;font:700 18px/1 var(--sans);letter-spacing:-.04em;color:var(--text)}
.brand .prompt,.brand .cursor{display:none}
.nav nav a.secondary{font-size:var(--type-meta)}
.nav nav a{font-size:var(--type-meta)}
.top{border:0;backdrop-filter:none;background:var(--bg)}
.footer{border:0;font-size:var(--type-meta);color:var(--muted)}
.footer-links{font-size:13px}
.footer p{max-width:70ch}
.footer-row .fbrand{font-size:0!important;font-family:var(--sans)}
.footer-row .fbrand::before{content:"TeemoBKK";display:inline-block;font-size:var(--type-meta);font-weight:700;letter-spacing:-.02em}
.theme-toggle{border:0;border-radius:999px;background:var(--surface2);font-size:var(--type-meta)}
.button{min-height:48px;padding:11px 22px;border:0;border-radius:999px;font-size:var(--type-body);transition:background-color .2s,color .2s}
.button:hover,.button.primary:hover{transform:none}
.hero{display:grid;grid-template-columns:minmax(0,1.16fr) minmax(0,.84fr);align-items:center;gap:clamp(22px,3.5vw,44px);padding:38px 0 46px;max-width:none}
.hero-visual{order:1;position:relative;height:clamp(280px,31vw,400px);max-height:none;aspect-ratio:auto;border-radius:20px}
.hero-visual img{position:absolute;inset:0;width:100%;height:100%;border-radius:inherit;object-fit:cover}
.hero-visual figcaption,.section-visual figcaption,.perspective-visual figcaption{position:absolute;right:0;bottom:0;border:0!important;outline:0!important;box-shadow:none!important;border-radius:12px 0 20px 0;padding:8px 13px;font-size:var(--type-meta);background:var(--bg);color:var(--muted)}
.hero-copy{order:0;display:block;min-width:0;padding-top:0}
.hero-copy .eyebrow,.hero-tags,.sec-tag,.indicator .icode{display:none!important}
.hero-copy h1{font-size:var(--type-display);line-height:1.04;letter-spacing:-.045em;max-width:15ch}
.hero-copy .intro{font-size:var(--type-body);line-height:1.7;max-width:540px;margin:20px 0 26px}
.section{padding:64px 0 0;border-top:0}
.sec-head{gap:0;margin-bottom:10px}
.sec-head::before{content:"";width:5px;height:26px;flex:0 0 5px;margin-right:14px;border-radius:5px;background:var(--accent)}
h2{font-size:var(--type-heading);line-height:1.2;letter-spacing:-.035em}
.section-intro{max-width:60ch;font-size:var(--type-body);line-height:1.7}
.section-visual,.perspective-visual{position:relative;aspect-ratio:2.15/1;margin:24px 0 20px;border-radius:18px}
.section-visual img,.perspective-visual img{border-radius:inherit}
.section-link{margin-top:18px;font-size:var(--type-body);font-weight:650}
.section-link::after{content:"  →"}
.news-status{font-size:var(--type-meta);gap:10px 16px}
.retry{border:0;border-radius:999px;background:var(--surface2);font-size:var(--type-meta);padding:8px 14px}
.news-list{display:flex;flex-direction:column;gap:0;margin-top:14px;border:0;border-radius:0;background:transparent;overflow:visible}
.news-row{display:flex;align-items:baseline;gap:12px;padding:14px 0;border:0;transition:color .2s}
.news-row:last-child{border:0}
.news-row:hover{background:transparent}
.news-row a{gap:12px}
.ntime{font-size:13px;color:var(--muted)}
.ntopic{border:0;border-radius:999px;padding:3px 9px;background:var(--accent-dim);font-size:13px;color:var(--accent)}
.ntitle{font-size:var(--type-body);font-weight:550;line-height:1.55}
.ntitle .ext{font-size:var(--type-meta)}
.empty{padding:20px 0;font-size:16px}
.posts{grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;margin-top:24px;border:0;border-radius:0;background:transparent;overflow:visible}
.post{padding:4px 0 0;border:0;background:transparent}
.post:hover{background:transparent}
.post time{font-size:13px;color:var(--muted)}
.post h3{font-size:var(--type-subhead);line-height:1.4;margin:10px 0}
.post p{max-width:60ch;font-size:var(--type-body);line-height:1.7}
.post .read{font-size:var(--type-meta);font-weight:650;margin-top:16px}
.note{max-width:60ch;font-size:var(--type-body);line-height:1.7;color:var(--muted)}
.about{gap:clamp(32px,7vw,88px)}
.about p,.about ul{max-width:60ch;font-size:var(--type-body);line-height:1.75}
.about h3{font-size:var(--type-subhead)}
.about li{padding-left:18px}
.about li::before{content:"";top:.72em;width:6px;height:6px;border-radius:50%;background:var(--accent)}
.indicator{border:0!important;border-radius:16px!important;background:var(--surface)!important;box-shadow:none!important}
.indicator .chart-open{border:0!important;outline:0!important;box-shadow:none!important}
.indicator .icode{font-family:var(--sans)!important;font-size:var(--type-meta)!important}
.indicator .chart-caption,.indicator .free{border:0!important;outline:0!important;box-shadow:none!important;font-family:var(--sans)!important;font-size:var(--type-meta)!important}
.indicator h3{font-size:var(--type-subhead)!important}
.indicator p{max-width:60ch;font-size:var(--type-body)!important;line-height:1.65}
.ticker{border:0;background:var(--surface2);}
.ticker-inner{animation-duration:42s}
.tick{border:0;font-size:13px;padding-inline:18px}
.tick b{font-weight:700}
@media(min-width:768px) and (max-width:900px){
.nav{gap:12px;flex-wrap:wrap;padding-block:8px}
.nav nav{order:2;flex-basis:100%;gap:4px 14px;flex-wrap:wrap}
.nav nav a{white-space:nowrap}
.theme-toggle{margin-left:auto}
}
@media(max-width:767px){
:root{--type-display:clamp(36px,9vw,44px)}
.wrap{padding-inline:20px}
.hero{grid-template-columns:minmax(0,1fr);gap:22px;padding:26px 0 30px}
.hero-visual{order:1;height:clamp(210px,62vw,270px);border-radius:16px}
.hero-copy{order:0;padding-top:0}
.hero-copy h1{font-size:var(--type-display);max-width:15ch}
.hero-copy .intro{font-size:var(--type-body);margin:15px 0 21px}
.hero-visual figcaption,.section-visual figcaption,.perspective-visual figcaption{font-size:13px;padding:7px 10px}
.nav nav a{font-size:13px}
.section{padding:46px 0 0}
.section-visual,.perspective-visual{aspect-ratio:16/9;border-radius:15px;margin:20px 0 16px}
.section-intro{font-size:var(--type-body)}
.sec-head::before{height:24px}
.news-row{padding:12px 0}
.news-row a{gap:6px 9px}
.ntime{font-size:13px}
.ntopic{font-size:13px}
.ntitle{font-size:var(--type-body);flex-basis:100%}
.posts{grid-template-columns:1fr;gap:22px}
.post h3{font-size:var(--type-subhead)}
.about{gap:24px}
.tick{font-size:var(--type-meta);padding-inline:14px}
}
</style>
</head>
<body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<div class="ticker" id="ticker" hidden aria-label="실시간 암호화폐 시세"><div class="ticker-inner" id="ticker-inner"></div></div>
__HEADER__
<main id="main" class="wrap">
<section class="hero" aria-labelledby="headline"><div class="hero-copy"><p class="eyebrow">뉴스를 읽고, 관점을 세우고, 차트로 살펴봅니다.</p><h1 id="headline">차트보다 먼저 읽는 뉴스</h1><p class="intro">시장이 움직이는 이유를 전합니다.<br>금리와 정책, 지정학과 수급까지.</p><div class="actions hero-actions"><a class="button primary" href="/news/ko/">오늘의 시장 보기</a></div><p class="hero-tags"><span>• MACRO</span><span>• CRYPTO</span><span>• MARKET STRUCTURE</span></p></div><figure class="hero-visual"><img src="/assets/landing/hero-editorial.webp" width="1672" height="941" fetchpriority="high" decoding="async" alt="방콕의 저녁, 금융 뉴스와 시장 자료를 살펴보는 책상"><figcaption>경제 뉴스와 시장 관점을 읽는 자리</figcaption></figure></section>
<section class="section" id="news" aria-labelledby="news-title"><div class="sec-head"><span class="sec-tag">01</span><h2 id="news-title">최근 경제 뉴스</h2></div><p class="section-intro">금리와 경기, 기업과 정책, 지정학까지. 시장에 연결되는 소식을 확인하세요.</p><figure class="section-visual"><img src="/assets/landing/news-editorial.webp" width="1536" height="1024" loading="lazy" decoding="async" alt="방콕의 편집 데스크에서 경제 뉴스와 시장 자료를 살펴보는 장면"><figcaption>뉴스는 원문과 게시 시각을 확인해 읽습니다.</figcaption></figure><div class="news-status"><span class="live">● 자동 수집 · 한국어로 표시</span><span id="update-status" role="status">수집 상태 확인 중</span><button class="retry" id="retry" type="button" hidden>다시 불러오기</button></div><div class="news-list" id="news-list" aria-busy="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div><noscript><p>뉴스 목록을 불러오려면 자바스크립트가 필요합니다. <a href="/news/ko/">경제 뉴스 페이지에서 확인하세요.</a></p></noscript><a class="section-link" href="/news/ko/">$ open /news/ko/ →</a></section>
<section class="section" id="perspectives" aria-labelledby="perspectives-title"><div class="sec-head"><span class="sec-tag">02</span><h2 id="perspectives-title">시장 관점</h2></div><p class="section-intro">뉴스와 차트를 어떻게 읽는지, 어떤 조건에서 생각을 바꾸는지. 트레이더로서의 판단을 기록합니다.</p><figure class="perspective-visual"><img src="/assets/landing/btc-analysis.webp" width="1536" height="1024" loading="lazy" decoding="async" alt="비트코인 가격 구조를 살펴보는 분석 화면과 노트"><figcaption>차트 이미지는 시장 분석의 참고 시각 자료입니다.</figcaption></figure><div class="posts">__POSTS__</div><a class="section-link" href="/blog/">$ open /blog/ →</a><p class="note">각 글은 작성 당시의 개인적인 관점입니다. 가격과 시나리오는 현재 시점과 다를 수 있습니다.</p></section>
<section class="section" id="indicators" aria-labelledby="indicators-title"><div class="sec-head"><span class="sec-tag">03</span><h2 id="indicators-title">직접 만든 트레이딩뷰 지표</h2></div><p class="section-intro">차트의 구조와 파동을 살펴보는 도구입니다. 공식 트레이딩뷰 페이지에서 무료로 사용할 수 있습니다.</p><div class="indicators">__INDICATORS__</div><a class="section-link" href="/indicators/">$ open /indicators/ →</a><a class="section-link" href="https://kr.tradingview.com/u/TeemoBKK/#published-scripts" target="_blank" rel="noopener noreferrer me">$ open profile → 전체 지표 보기 ↗</a><p class="note">파동 카운팅과 목표 구간은 진행 중인 가격에 따라 달라질 수 있습니다. 사용 조건과 설정은 각 지표 페이지에서 확인하세요.</p></section>
<section class="section about" aria-labelledby="about-title"><div><div class="sec-head"><span class="sec-tag">04</span><h2 id="about-title">TeemoBKK에 대하여</h2></div><p>경제 뉴스를 모으고, 시장을 바라보는 관점을 쓰며, 차트에서 사용하는 지표를 만듭니다.</p><p>뉴스는 시장의 맥락을 살피는 출발점입니다. 해석과 시나리오는 사실과 구분해 기록하겠습니다.</p><a class="section-link" href="/about/">$ open /about/ → 자세히 보기</a></div><div><h3>읽기 전에</h3><ul><li>뉴스는 자동 수집한 원문 제목과 출처를 제공합니다.</li><li>시장 관점은 운영자의 개인적인 해석입니다.</li><li>지표는 분석 보조 도구이며 수익을 보장하지 않습니다.</li></ul></div></section>
</main>
__FOOTER__
<script>
(function(){
'use strict';
var ticker=document.getElementById('ticker'),tickerInner=document.getElementById('ticker-inner');
document.querySelectorAll('.section-link').forEach(function(link){
var labels={'/news/ko/':'\uC804\uCCB4 \uB274\uC2A4 \uBCF4\uAE30','/blog/':'\uAD00\uC810 \uAE00 \uB354 \uBCF4\uAE30','/indicators/':'\uC9C0\uD45C \uC804\uCCB4 \uBCF4\uAE30','/about/':'\uC0AC\uC774\uD2B8 \uC18C\uAC1C \uBCF4\uAE30'};
var href=link.getAttribute('href');
if(labels[href])link.textContent=labels[href];
else if(href&&href.indexOf('tradingview.com/u/')!==-1)link.textContent='\uD2B8\uB808\uC774\uB529\uBDF0 \uC804\uCCB4 \uC9C0\uD45C \uBCF4\uAE30';
});
document.querySelectorAll('.posts .read').forEach(function(link){
var heading=link.closest('.post')&&link.closest('.post').querySelector('h3');
var label='\uBE14\uB85C\uADF8 \uAE00 \uC77D\uAE30';
link.textContent=label;
if(heading)link.setAttribute('aria-label',label+': '+heading.textContent.trim());
});
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
return get('month')+'월 '+get('day')+'일 '+get('hour')+':'+get('minute')+' ICT'}
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
async function refresh(){if(busy)return;busy=true;retry.disabled=true;list.setAttribute('aria-busy','true');const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);try{const response=await fetch('/api/news?region='+encodeURIComponent('글로벌')+'&hours=24&limit=100&lang=ko',{cache:'no-cache',signal:controller.signal});if(!response.ok)throw new Error('http');const data=await response.json();if(!Array.isArray(data.articles))throw new Error('schema');render(selectNews(data.articles));const updated=Date.parse(data.updated_at);if(Number.isFinite(updated)&&updated<=Date.now()+60000){const age=Date.now()-updated;status.textContent=(age>35*60000?'! 갱신 지연 · ':'✓ ')+displayStamp(updated);retry.hidden=age<=35*60000;}else{status.textContent='? 수집 시각 확인 불가';retry.hidden=false;}}
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
            '<span class="icode">SCRIPT · {code}</span><h3>{title}</h3><p>{description}</p>'
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


def _homepage_post_cards(posts) -> str:
    from urllib.parse import quote

    cards = []
    for post in posts:
        slug = str(post.get("original_slug") or "").strip()
        if not slug:
            continue
        cards.append({
            "date": str(post.get("date") or ""),
            "title": str(post.get("title") or ""),
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
            '<article class="post"><time datetime="{date}">{visible_date}</time>'
            '<h3><a href="{url}">{title}</a></h3>'
            '<p>{summary}</p><a class="read" href="{url}">블로그 글 읽기 →</a></article>'.format(**fields)
        )
    return "".join(cards)


def _standalone_page(title: str, eyebrow: str, description: str, content: str, extra_css: str = "") -> str:
    safe_title = escape(title)
    safe_eyebrow = escape(eyebrow)
    safe_description = escape(description)
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="description" content="{description}"><title>{title} | TeemoBKK</title>'
        '<style>{shared_css}{extra_css}{page_css}</style>{head_script}</head><body>'
        '<a class="skip" href="#main">본문으로 건너뛰기</a>{header}'
        '<main class="page-main" id="main"><header class="page-head">'
        '<p class="page-eyebrow">{eyebrow}</p><h1 class="page-title">{title}</h1>'
        '<p class="page-intro">{description}</p></header>{content}'
        '<a class="page-back" href="/">$ cd / → 홈으로</a></main>{footer}</body></html>'
    ).format(
        description=safe_description,
        title=safe_title,
        shared_css=theme.shared_css(),
        extra_css=extra_css,
        page_css=theme.SUBPAGE_CSS,
        head_script=theme.theme_head_script(),
        header=theme.render_header(),
        eyebrow=safe_eyebrow,
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
            '<article class="page-post"><time datetime="{date}">{visible_date}</time>'
            '<h2><a href="{url}">{title}</a></h2>'
            '<p>{summary}</p><a class="read" href="{url}">'
            '블로그 글 읽기 →</a></article>'.format(**fields)
        )
    if not entries:
        entries.append('<p class="empty">현재 표시할 관점 글이 없습니다.</p>')
    content = '<div class="page-posts">{}</div>'.format("".join(entries))
    return _standalone_page(
        "시장 관점", "BLOG · 관점 브리핑", "시장 관점은 짧은 요약으로 살펴보고, 전체 글은 블로그에서 읽을 수 있습니다.", content
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
            '<article class="page-post"><time datetime="{date}">{visible}</time>'
            '<h2><a href="/blog/{slug}/">{title}</a></h2></article>'.format(
                date=date, visible=visible, slug=slug, title=title))
    if not entries:
        entries.append('<p class="empty">현재 표시할 블로그 글이 없습니다.</p>')
    return _standalone_page(
        "블로그", "BLOG · 관점 브리핑", "공개된 관점 브리핑 글을 모았습니다.",
        '<div class="page-posts">{}</div>'.format("".join(entries))
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
    return _standalone_page(title, "BLOG · 관점 브리핑", title, content)


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
        '$ open profile → 전체 지표 보기 ↗</a>'
    ).format(render_indicator_cards(), escape(INDICATOR_PROFILE_URL, quote=True))
    return _standalone_page(
        "트레이딩뷰 지표", "INDICATORS · TRADINGVIEW",
        "차트 구조와 파동을 살펴보는 공개 지표입니다. 분석 보조 도구로 활용하세요.",
        content, extra_css=theme.INDICATOR_CSS,
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
            .replace('__HEADER__', theme.render_header())
            .replace('__FOOTER__', theme.render_footer()))
