"""The Thailand section's front page — Siam design.

Standalone stylesheet (no landing.stylesheet() dependency): the Thai landing
targets Korean expats in Thailand and carries its own visual identity —
royal gold, deep purple, warm cream, Wat Arun hero.
"""

import sys
from pathlib import Path

# Repository-root bootstrap: this file lives under pages/build/, but the code is
# imported as pages.build.<module> with the repository root on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import html
import json


from pages.build import ui_text
from pages.build import theme

HERO_IMG = "https://images.pexels.com/photos/11104872/pexels-photo-11104872.jpeg?auto=compress&cs=tinysrgb&w=1600"

# Category representative images (verified Pexels IDs, Thailand-relevant).
_PX = "https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg?auto=compress&cs=tinysrgb&w=800"
CAT_IMGS = {
    "비자·이민": _PX.format(i=346793),      # passport / travel essentials
    "사고·재난": _PX.format(i=27866564),    # Bangkok street scene
    "태국 생활": _PX.format(i=1682748),      # tuk-tuk, Silom street
    "태국 경제": _PX.format(i=16252642),     # Pattaya floating market
    "태국 정치·사회": _PX.format(i=17186243), # Bangkok city center
    "태국 관광": _PX.format(i=7969155),      # tourists at temple
    "태국 보건": _PX.format(i=8830674),      # travel health documents
    "_default": _PX.format(i=29419561),      # Wat Arun spires
}

PAGE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<script>(function(){try{var t=localStorage.getItem("tbn-theme");if(t)document.documentElement.dataset.theme=t;}catch(e){}})();</script>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK | 태국 소식을 한국어로</title>
<meta name="description" content="태국에 사는 당신을 위한 뉴스. 비자부터 사고까지, 현지 소식을 가장 먼저 한국어로 전합니다.">
<meta name="theme-color" content="#4a1d6b">
<meta name="color-scheme" content="light">
<meta property="og:type" content="website">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="TeemoBKK | 태국 소식을 한국어로">
<meta property="og:description" content="태국에 사는 당신을 위한 뉴스. 비자부터 사고까지, 현지 소식을 가장 먼저 전합니다.">
<meta property="og:url" content="https://teemobkk.io/thai/">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="https://teemobkk.io/thai/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>__THAI_STYLES__</style>
__THEME_BOOTSTRAP__
</head>
<body>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<header class="top"><div class="wrap nav">
<a class="brand" href="/" aria-label="TeemoBKK 홈"><span class="t">Teemo</span><span class="g">BKK</span></a>
<nav aria-label="주요 메뉴">
<a href="/thai/news/ko/">태국 뉴스</a>
<a href="#topics">분류</a>
<a href="#living">생활 정보</a>
<a class="secondary" href="/news/ko/">경제 뉴스 ↗</a>
</nav></div></header>

<main id="main">
<section class="hero" aria-labelledby="headline">
<div class="hero-bg" role="img" aria-label="석양에 물든 왓 아룬"></div>
<div class="hero-veil"></div>
<div class="hero-inner">
<p class="eyebrow">Thai News · TeemoBKK</p>
<h1 id="headline">태국 소식을 <span class="gold">한국어로</span></h1>
<p class="intro">태국에 사는 당신을 위한 뉴스.<br>비자부터 사고까지, 현지 소식을 가장 먼저 전합니다.</p>
<div class="actions">
<a class="button primary" href="/thai/news/ko/">태국 뉴스 전체 보기</a>
<a class="button" href="#news">최근 소식 먼저 보기</a>
</div>
<div class="stats">
<div class="stat"><b id="stat-total">&mdash;</b><span>최근 24시간 태국 소식</span></div>
<div class="stat"><b>7</b><span>자동 분류 갈래</span></div>
<div class="stat"><b>2분</b><span>자동 갱신</span></div>
</div>
</div>
</section>

<div class="wrap">
<hr class="thai-rule">

<section class="section" id="news" aria-labelledby="news-title">
<div class="filters" id="filters" role="group" aria-label="분류 필터">
<button class="chip active" data-cat="">전체</button>
__FILTERS__
</div>
<div class="section-head"><h2 id="news-title"><span class="n">01</span>태국의 오늘을 생활자의 눈으로</h2></div>
<p class="section-intro">비자와 이민, 사고와 재난, 생활과 교통까지. 태국 안에서 벌어진 일을 한국어로 보여줍니다.</p>
<div class="news-status"><span class="live">● 자동 수집 · 한국어로 표시</span><span id="update-status" role="status">수집 상태 확인 중</span>
<button class="retry" id="retry" type="button" hidden>다시 불러오기</button></div>
<div class="news-feature" id="news-feature" hidden></div>
<div class="news-grid" id="news-grid" aria-busy="true">
<div class="ncard" aria-hidden="true"><div class="ncard-img loading-line" style="aspect-ratio:16/9"></div><div class="ncard-body"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div></div>
<div class="ncard" aria-hidden="true"><div class="ncard-img loading-line" style="aspect-ratio:16/9"></div><div class="ncard-body"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div></div>
<div class="ncard" aria-hidden="true"><div class="ncard-img loading-line" style="aspect-ratio:16/9"></div><div class="ncard-body"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div></div>
</div>
<noscript><p>뉴스 목록을 불러오려면 자바스크립트가 필요합니다. <a href="/thai/news/ko/">태국 뉴스 페이지에서 확인하세요.</a></p></noscript>
<a class="section-link" href="/thai/news/ko/">태국 뉴스 전체 보기 →</a>
</section>

<hr class="thai-rule">

<section class="section" id="topics" aria-labelledby="topics-title">
<div class="section-head"><h2 id="topics-title"><span class="n">02</span>분류로 바로 가기</h2></div>
<p class="section-intro">갈래를 누르면 대시보드에서 그 분류만 걸러 보여줍니다.</p>
<div class="topics">__TOPICS__</div>
<p class="note">분류는 수집한 제목과 요약의 낱말로 자동으로 나눈 것이며, 사람이 확인해 고른 목록이 아닙니다. 한 기사가 여러 갈래에 걸릴 수 있습니다.</p>
</section>

<hr class="thai-rule">

<section class="section" id="living" aria-labelledby="living-title">
<div class="section-head"><h2 id="living-title"><span class="n">03</span>태국 생활 정보</h2></div>
<p class="section-intro">태국에 사는 한국인이 자주 찾는 기본 안내입니다.</p>
<div class="living">
<div class="living-card"><h3>비자 · 체류</h3><p>비자 종류와 체류 연장은 이민국(Immigration) 공식 안내를 기준으로 확인하세요. 90일 신고와 TM30 규정을 놓치지 마세요.</p></div>
<div class="living-card"><h3>긴급 · 안전</h3><p>관광경찰 1155 (한국어 지원), 일반 긴급 191, 의료 긴급 1669. 여권 분실 시 대사관 영사과에 연락하세요.</p></div>
<div class="living-card"><h3>생활 · 교통</h3><p>BTS·MRT 노선과 Grab 앱이 기본 이동 수단입니다. 우기(5–10월) 침수와 건기 미세먼지 시기를 알아두세요.</p></div>
</div>
</section>

<hr class="thai-rule">

<section class="section about" aria-labelledby="about-title">
<div>
<h2 id="about-title"><span class="n">04</span>이 페이지에 대하여</h2>
<p>태국 소식은 방콕에 사는 사람이 먼저 알아야 하는 일을 기준으로 모읍니다.</p>
<p>수집한 뉴스를 한국어로 번역해 보여주고, 원문으로도 바로 보냅니다.</p>
</div>
<div>
<h3>읽기 전에</h3>
<ul>
<li>뉴스는 자동 수집한 제목과 출처입니다.</li>
<li>한국어로 번역하여 표시합니다.</li>
<li>비자·법률 판단은 이민국 등 공식 기관의 최신 안내를 확인하세요.</li>
</ul>
</div>
</section>
</div>
</main>

<footer class="footer"><div class="wrap">
<div class="footer-row"><span class="flogo">Teemo<span class="g">BKK</span> · 태국 소식</span><a href="/">경제 뉴스와 지표 보기 ↗</a></div>
<p>자동 수집한 목록이며 자동 매매 신호가 아닙니다 · 중요한 사건은 원문과 공식 발표로 확인하세요.</p>
<nav class="footer-links" aria-label="사이트 정보"><a href="/privacy/">개인정보 처리방침</a></nav>
</div></footer>

<script>
(function(){
  "use strict";
  const feature = document.getElementById("news-feature"),
        grid = document.getElementById("news-grid"),
        status = document.getElementById("update-status"),
        retry = document.getElementById("retry"),
        filters = document.getElementById("filters");
  let busy = false, hasNews = false, activeCat = "", latestArticles = [];
  const fmt = new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Bangkok", month:"numeric", day:"numeric",
    hour:"2-digit", minute:"2-digit", hour12:false});
  function displayStamp(value){const p=fmt.formatToParts(new Date(value)),get=k=>(p.find(x=>x.type===k)||{}).value||"";
    return get("month")+"월 "+get("day")+"일 "+get("hour")+":"+get("minute");}

  function cleanTitle(value){
    return String(value || "")
      .replace(/(?:https?:\/\/|www\.)\S+|\b[a-z0-9.-]+\.(?:com|org|net|rs|co\.th|go\.th)\/\S+|\breut\.rs\S*/gi, "")
      .replace(/\s+-\s+[^-]+$/, "")
      .replace(/\s+/g, " ").trim();
  }
  function safeLink(value){
    try { const u = new URL(value); return ["http:","https:"].includes(u.protocol) ? u.href : null; }
    catch (e) { return null; }
  }
  function selectNews(articles){
    const seen = new Set();
    return articles.filter((a) => {
      if (a.region !== "태국") return false;
      if (activeCat && a.category !== activeCat) return false;
      const title = cleanTitle(a.title);
      const key = title.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
      const date = Date.parse(a.published_at);
      if (key.length < 8 || !safeLink(a.link) || !Number.isFinite(date)
          || date > Date.now() + 60000 || Date.now() - date > 86400000 || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at)).slice(0, 7);
  }
  const CAT_IMGS = __CAT_IMGS__;
  const FALLBACK_IMG = CAT_IMGS["_default"];
  function catImg(cat){ return CAT_IMGS[cat] || FALLBACK_IMG; }
  function imgEl(cat, cls, src){
    const d = document.createElement("div");
    d.className = cls;
    const img = document.createElement("img");
    const primary = String(src || "").trim();
    const fallback = catImg(cat);
    img.src = primary || fallback;
    img.alt = "";
    img.loading = "lazy";
    img.style.cssText = "width:100%;height:100%;object-fit:cover;display:block";
    img.onerror = function(){
      // The publisher image failed: try the category image once, then the placeholder.
      if (primary && img.src !== fallback) { img.src = fallback; return; }
      d.classList.add("img-fallback"); d.textContent = "◆"; img.remove();
    };
    d.append(img);
    return d;
  }
  function cleanSummary(value){
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, 140);
  }
  function srcLabel(a){
    if (a.original_link) {
      try { return new URL(a.original_link).hostname.replace(/^www\./, ""); } catch (e) {}
    }
    return a.source || "원문";
  }
  function render(articles){
    feature.replaceChildren();
    grid.replaceChildren();
    feature.hidden = true;
    if (!articles.length){
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = "최근 24시간에 표시할 소식이 없습니다. 태국 뉴스 페이지에서 기간과 분류를 확인하세요.";
      grid.append(p);
      return;
    }
    const first = articles[0], rest = articles.slice(1);
    // Feature card: image left, text right
    const fc = document.createElement("article");
    fc.className = "fcard";
    fc.append(imgEl(first.category, "fcard-img", first.image_url));
    const fbody = document.createElement("div");
    fbody.className = "fcard-body";
    const ftopic = document.createElement("span");
    ftopic.className = "topic";
    ftopic.textContent = LABELS[first.category] || first.category || "일반";
    const ftitle = document.createElement("h3");
    const flink = document.createElement("a");
    flink.href = safeLink(first.original_link || first.link);
    flink.target = "_blank"; flink.rel = "noopener noreferrer";
    flink.textContent = cleanTitle(first.title);
    ftitle.append(flink);
    const fsum = document.createElement("p");
    fsum.className = "sum";
    fsum.textContent = cleanSummary(first.summary_ko || first.summary);
    const fmeta = document.createElement("div");
    fmeta.className = "meta";
    const fsrc = document.createElement("span"); fsrc.textContent = srcLabel(first);
    const ftime = document.createElement("time");
    ftime.dateTime = first.published_at;
    ftime.textContent = displayStamp(first.published_at) + " ICT";
    fmeta.append(fsrc, ftime);
    fbody.append(ftopic, ftitle, fsum, fmeta);
    fc.append(fbody);
    feature.append(fc);
    feature.hidden = false;
    // Grid cards
    for (const a of rest){
      const card = document.createElement("article");
      card.className = "ncard";
      card.append(imgEl(a.category, "ncard-img", a.image_url));
      const body = document.createElement("div");
      body.className = "ncard-body";
      const topic = document.createElement("div");
      topic.className = "topic";
      topic.textContent = LABELS[a.category] || a.category || "일반";
      const title = document.createElement("h3");
      const link = document.createElement("a");
      link.href = safeLink(a.original_link || a.link);
      link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = cleanTitle(a.title);
      title.append(link);
      const sum = document.createElement("p");
      sum.className = "sum";
      sum.textContent = cleanSummary(a.summary_ko || a.summary);
      const meta = document.createElement("div");
      meta.className = "meta";
      const src = document.createElement("span"); src.textContent = srcLabel(a);
      const time = document.createElement("time");
      time.dateTime = a.published_at;
      time.textContent = displayStamp(a.published_at) + " ICT";
      meta.append(src, time);
      body.append(topic, title, sum, meta);
      card.append(body);
      grid.append(card);
    }
    hasNews = true;
  }
  const LABELS = __LABELS__;

  async function refresh(){
    if (busy) return;
    busy = true; retry.disabled = true; grid.setAttribute("aria-busy", "true");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/news?region=" + encodeURIComponent("태국") + "&hours=24&limit=100&lang=ko",
        {cache:"no-cache", signal:controller.signal});
      if (!response.ok) throw new Error("http");
      const data = await response.json();
      if (!Array.isArray(data.articles)) throw new Error("schema");
      latestArticles = data.articles;
      render(selectNews(latestArticles));
      if (typeof data.total === "number"){
        document.getElementById("stat-total").textContent = data.total.toLocaleString("en-US") + "건";
      }
      const updated = Date.parse(data.updated_at);
      if (Number.isFinite(updated) && updated <= Date.now() + 60000){
        const age = Date.now() - updated;
        status.textContent = (age > 35*60000 ? "갱신 지연 · 마지막 수집 " : "마지막 수집 ")
          + displayStamp(updated) + " ICT";
        retry.hidden = age <= 35*60000;
      } else {
        status.textContent = "수집 시각을 확인할 수 없습니다";
        retry.hidden = false;
      }
    } catch (error){
      status.textContent = hasNews ? "갱신 실패 · 이전 목록 표시 중" : "뉴스를 불러오지 못했습니다";
      retry.hidden = false;
      if (!hasNews){
        feature.replaceChildren(); feature.hidden = true;
        grid.replaceChildren();
        const p = document.createElement("p");
        p.className = "empty";
        p.textContent = "잠시 후 다시 시도하거나 태국 뉴스 페이지에서 확인하세요.";
        grid.append(p);
      }
    } finally {
      clearTimeout(timeout); busy = false; retry.disabled = false; grid.setAttribute("aria-busy", "false");
    }
  }
  filters.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    filters.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    activeCat = btn.dataset.cat || "";
    render(selectNews(latestArticles));
  });
  retry.addEventListener("click", refresh);
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 120000);
})();
</script>
</body>
</html>'''


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def filters(lang: str = "ko") -> str:
    """Filter chips for the seven Thai categories."""
    out = []
    for value, label in ui_text.cats(lang)["thai"]:
        if value == "일반":
            continue
        out.append('<button class="chip" data-cat="%s">%s</button>'
                   % (html.escape(value, quote=True), html.escape(label)))
    return "\n".join(out)


def topics(lang: str = "ko") -> str:
    """One link per Thai category, straight into the dashboard with the filter applied."""
    out = []
    for value, label in ui_text.cats(lang)["thai"]:
        if value == "일반":
            continue
        out.append('<a class="topic-link" href="/thai/news/ko/#cat=%s"><b>%s</b><span>%s 소식 보기 →</span></a>'
                   % (html.escape(value, quote=True), html.escape(label), html.escape(label)))
    return "\n".join(out)


def render_thai_landing() -> str:
    labels = dict(ui_text.cats("ko")["thai"])
    page = PAGE.replace("__HERO_IMG__", HERO_IMG)
    page = page.replace("__THAI_STYLES__", theme.THAI_CSS.replace("__HERO_IMG__", HERO_IMG) + "\n" + theme.USAGE_BAR_CSS + "\n")
    page = page.replace("__THEME_BOOTSTRAP__", theme.theme_head_script())
    page = page.replace("__FILTERS__", filters())
    page = page.replace("__TOPICS__", topics())
    page = page.replace("__LABELS__", _json(labels))
    page = page.replace("__CAT_IMGS__", _json(CAT_IMGS))
    return page
