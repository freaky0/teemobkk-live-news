"""The Thailand section's front page.

The section root introduces the material and the dashboard sits one level in, the same way the
site root relates to /news. The stylesheet and the motion layer are taken from landing.py rather
than copied: two landings that keep their own copy of the type rules drift apart, and the site
starts to look like two sites.

The list here reads the Thailand half of the same endpoint the dashboard reads, and the topic
links deep-link into the dashboard with the category already applied.
"""
import html

import landing
import ui_text

PAGE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK | 태국 소식</title>
<meta name="description" content="방콕과 태국에서 먼저 볼 소식. 비자·이민, 사고·재난, 생활·경제, 관광·보건을 원문 그대로 모읍니다.">
<meta name="theme-color" content="#0b1118">
<meta property="og:type" content="website">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="TeemoBKK | 태국 소식">
<meta property="og:description" content="태국에 사는 사람에게 먼저 닿아야 하는 소식을 한 화면에 모읍니다.">
<meta property="og:url" content="https://teemobkk.io/thai/">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="https://teemobkk.io/thai/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
__STYLE__
<style>
.topics{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-top:22px}
.topic-link{display:block;padding:16px 18px;background:var(--surface);border:1px solid var(--line);
border-radius:var(--radius);transition:border-color .35s,transform .45s cubic-bezier(.16,1,.3,1)}
.topic-link:hover{border-color:rgba(121,216,221,.5);transform:translateY(-3px);color:inherit}
.topic-link b{display:block;font-size:16px;font-weight:600;letter-spacing:-.02em}
.topic-link span{display:block;margin-top:5px;font-size:12px;color:var(--muted)}
</style>
</head>
<body>
<div class="pointer-light" aria-hidden="true"></div>
<a class="skip" href="#main">본문으로 건너뛰기</a>
<header class="top"><div class="wrap nav">
<a class="brand" href="/" aria-label="TeemoBKK 홈">Teemo<span>BKK</span></a>
<nav aria-label="주요 메뉴">
<a href="/">홈</a>
<a href="/news/ko/">경제 뉴스</a>
<a href="/thai/news/ko/">태국 뉴스 전체</a>
<a class="secondary" href="/thai/news/">English ↗</a>
</nav></div></header>

<main id="main" class="wrap">
<section class="hero" aria-labelledby="headline">
<p class="eyebrow">비자·이민 · 사고·재난 · 생활 · 관광 · 보건</p>
<h1 id="headline"><span class="rise"><i>방콕에서</i></span><span class="rise"><i>먼저 볼 소식</i></span></h1>
<div class="hero-rule"></div>
<p class="intro">태국에 사는 사람에게 먼저 닿아야 하는 소식을 모읍니다.<br>비자와 이민, 사고와 재난, 생활비와 교통, 관광과 보건까지 원문 그대로 정리합니다.</p>
<div class="actions">
<a class="button primary" href="/thai/news/ko/">태국 뉴스 전체 보기</a>
<a class="button" href="#news">최근 소식 먼저 보기</a>
</div>
<div class="stats">
<div class="stat"><b id="stat-total">&mdash;</b><span>최근 24시간 태국 소식</span></div>
<div class="stat"><b>7</b><span>자동 분류 갈래</span></div>
<div class="stat"><b>2분</b><span>자동 갱신</span></div>
</div>
</section>

<div class="marq" aria-hidden="true"><div>
<span>BANGKOK</span><span>VISA &amp; IMMIGRATION</span><span>SAFETY</span><span>LIVING</span><span>TOURISM</span>
<span>BANGKOK</span><span>VISA &amp; IMMIGRATION</span><span>SAFETY</span><span>LIVING</span><span>TOURISM</span>
</div></div>

<section class="section" id="news" aria-labelledby="news-title">
<h2 id="news-title">최근 태국 소식</h2>
<p class="section-intro">비자와 이민, 사고와 재난, 생활과 경제, 정치와 사회. 태국 안에서 벌어진 일을 원문 언어로 보여줍니다.</p>
<div class="news-status"><span>자동 수집 · 원문 언어로 표시</span><span id="update-status" role="status">수집 상태 확인 중</span>
<button class="retry" id="retry" type="button" hidden>다시 불러오기</button></div>
<div class="news-list" id="news-list" aria-busy="true">
<div class="news-item" aria-hidden="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div>
<div class="news-item" aria-hidden="true"><div class="loading-line short"></div><div class="loading-line"></div><div class="loading-line"></div></div>
</div>
<noscript><p>뉴스 목록을 불러오려면 자바스크립트가 필요합니다. <a href="/thai/news/ko/">태국 뉴스 페이지에서 확인하세요.</a></p></noscript>
<a class="section-link" href="/thai/news/ko/">태국 뉴스 전체 보기 →</a>
</section>

<section class="section" id="topics" aria-labelledby="topics-title">
<h2 id="topics-title">분류로 바로 가기</h2>
<p class="section-intro">갈래를 누르면 대시보드에서 그 분류만 걸러 보여줍니다.</p>
<div class="topics">__TOPICS__</div>
<p class="note">분류는 수집한 제목과 요약의 낱말로 자동으로 나눈 것이며, 사람이 확인해 고른 목록이 아닙니다. 한 기사가 여러 갈래에 걸릴 수 있습니다.</p>
</section>

<section class="section about" aria-labelledby="about-title">
<div>
<h2 id="about-title">이 페이지에 대하여</h2>
<p>태국 소식은 비트코인과 무관해도 모읍니다. 방콕에 사는 사람이 먼저 알아야 하는 일이 기준입니다.</p>
<p>제목과 출처만 보여주고 원문으로 보냅니다. 해석이 필요한 부분은 따로 쓰지 않습니다.</p>
</div>
<div>
<h3>읽기 전에</h3>
<ul>
<li>뉴스는 자동 수집한 원문 제목과 출처입니다.</li>
<li>번역하지 않고 원문 언어로 표시합니다.</li>
<li>비자·법률 판단은 이민국 등 공식 기관의 최신 안내를 확인하세요.</li>
</ul>
</div>
</section>
</main>

<footer class="footer"><div class="wrap">
<div class="footer-row"><span>TeemoBKK · 태국 소식</span><a href="/">경제 뉴스와 지표 보기 ↗</a></div>
<p>자동 수집한 목록이며 자동 매매 신호가 아닙니다 · 중요한 사건은 원문과 공식 발표로 확인하세요.</p>
</div></footer>

<script>
(function(){
  "use strict";
  const list = document.getElementById("news-list"),
        status = document.getElementById("update-status"),
        retry = document.getElementById("retry");
  let busy = false, hasNews = false;
  const fmt = new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Bangkok", month:"2-digit", day:"2-digit",
    hour:"2-digit", minute:"2-digit", hour12:false});

  // A collected title is not trusted markup: the URL and the trailing publisher are stripped for
  // display, and the text is inserted as text so a title can never become an element.
  function cleanTitle(value){
    return String(value || "")
      .replace(/(?:https?:\/\/|www\.)\S+|\b[a-z0-9.-]+\.(?:com|org|net|rs|co\.th|go\.th)\/\S+/gi, "")
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
      const title = cleanTitle(a.title);
      const key = title.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
      const date = Date.parse(a.published_at);
      if (key.length < 8 || !safeLink(a.link) || !Number.isFinite(date)
          || date > Date.now() + 60000 || Date.now() - date > 86400000 || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at)).slice(0, 6);
  }
  function render(articles){
    list.replaceChildren();
    if (!articles.length){
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = "최근 24시간에 표시할 소식이 없습니다. 태국 뉴스 페이지에서 기간과 분류를 확인하세요.";
      list.append(p);
      return;
    }
    for (const a of articles){
      const item = document.createElement("article"); item.className = "news-item";
      const link = document.createElement("a"); link.href = safeLink(a.link);
      link.target = "_blank"; link.rel = "noopener noreferrer";
      const meta = document.createElement("div"); meta.className = "meta";
      const source = document.createElement("span"); source.textContent = a.source || "원문";
      const topic = document.createElement("span"); topic.className = "topic";
      topic.textContent = a.category || "일반";
      const time = document.createElement("time"); time.dateTime = a.published_at;
      time.textContent = fmt.format(new Date(a.published_at)) + " ICT";
      meta.append(source, topic, time);
      const title = document.createElement("h3"); title.textContent = cleanTitle(a.title) + " ↗";
      link.append(meta, title); item.append(link); list.append(item);
      // the stored value is Korean; the label shown is the same one the dashboard uses
      const label = LABELS[a.category];
      if (label) topic.textContent = label;
    }
    hasNews = true;
  }
  const LABELS = __LABELS__;

  async function refresh(){
    if (busy) return;
    busy = true; retry.disabled = true; list.setAttribute("aria-busy", "true");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/news?region=" + encodeURIComponent("태국") + "&hours=24&limit=100",
        {cache:"no-cache", signal:controller.signal});
      if (!response.ok) throw new Error("http");
      const data = await response.json();
      if (!Array.isArray(data.articles)) throw new Error("schema");
      render(selectNews(data.articles));
      if (typeof data.total === "number"){
        document.getElementById("stat-total").textContent = data.total.toLocaleString("en-US") + "건";
      }
      const updated = Date.parse(data.updated_at);
      if (Number.isFinite(updated) && updated <= Date.now() + 60000){
        const age = Date.now() - updated;
        status.textContent = (age > 35*60000 ? "갱신 지연 · 마지막 수집 " : "마지막 수집 ")
          + fmt.format(new Date(updated)) + " ICT";
        retry.hidden = age <= 35*60000;
      } else {
        // Never present the current time as the time the collector last ran: that would make a
        // stalled collector look healthy.
        status.textContent = "수집 시각을 확인할 수 없습니다";
        retry.hidden = false;
      }
    } catch (error){
      status.textContent = hasNews ? "갱신 실패 · 이전 목록 표시 중" : "뉴스를 불러오지 못했습니다";
      retry.hidden = false;
      if (!hasNews){
        list.replaceChildren();
        const p = document.createElement("p"); p.className = "empty";
        p.textContent = "잠시 후 다시 시도하거나 태국 뉴스 페이지에서 확인하세요.";
        list.append(p);
      }
    } finally {
      clearTimeout(timeout); busy = false; retry.disabled = false; list.setAttribute("aria-busy", "false");
    }
  }
  retry.addEventListener("click", refresh);
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 120000);

  // The light that follows the pointer, where a real pointer exists.
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches
      && window.matchMedia("(hover:hover) and (pointer:fine)").matches){
    const light = document.querySelector(".pointer-light");
    let raf = 0, tx = 0, ty = 0, cx = 0, cy = 0;
    const glide = function(){
      cx += (tx - cx) * .09; cy += (ty - cy) * .09;
      light.style.setProperty("--px", cx + "px");
      light.style.setProperty("--py", cy + "px");
      raf = (Math.abs(tx - cx) > .5 || Math.abs(ty - cy) > .5) ? requestAnimationFrame(glide) : 0;
    };
    window.addEventListener("pointermove", (e) => {
      tx = e.clientX; ty = e.clientY; light.style.opacity = "1";
      if (!raf) raf = requestAnimationFrame(glide);
    }, {passive:true});
  }
})();
</script>
</body>
</html>'''


def topics(lang: str = "ko") -> str:
    """One link per Thai category, straight into the dashboard with the filter applied."""
    out = []
    for value, label in ui_text.cats(lang)["thai"]:
        if value == "일반":
            continue
        out.append('<a class="topic-link" href="/thai/news/ko/#cat=%s"><b>%s</b><span>%s</span></a>'
                   % (html.escape(value, quote=True), html.escape(label), html.escape(value)))
    return "\n".join(out)


def render_thai_landing() -> str:
    labels = dict(ui_text.cats("ko")["thai"])
    page = PAGE.replace("__STYLE__", landing.stylesheet())
    page = page.replace("__TOPICS__", topics())
    page = page.replace("__LABELS__", _json(labels))
    return page


def _json(data) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
