"""Shared TeemoBKK design tokens and landing-page renderers."""
from datetime import date


CSS_CUSTOM_PROPERTIES = ':root{color-scheme:light;--bg:#faf8f3;--surface:#ffffff;--surface2:#f3f0e8;--text:#1a1c1a;--muted:#5f665f;--dim:#9aa099;--line:#e5e0d3;--accent:#0a7a4a;--accent-dim:rgba(10,122,74,.10);--down:#d33f3f;--radius:6px;--sans:system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"D2Coding","JetBrains Mono","Courier New",monospace}'

BUTTON_CSS = ('.button{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 22px;border-radius:var(--radius);border:1px solid var(--line);font-size:14px;font-weight:700;white-space:nowrap;background:var(--surface);color:var(--text);transition:border-color .25s,transform .25s}\n'
              '.button.primary{background:var(--accent);border-color:var(--accent);color:#ffffff}\n'
              '.button:hover{border-color:var(--accent);color:var(--accent)}\n'
              '.button.primary:hover{color:#ffffff;transform:translateY(-1px)}\n'
              '.button:active{transform:translateY(1px)}')

DARK_THEME_CSS = ('[data-theme=dark]{color-scheme:dark;--bg:#101412;--surface:#171d19;--surface2:#202822;'
                  '--text:#e7eee8;--muted:#b0bcb3;--dim:#849188;--line:#344039;--accent:#42c98a;'
                  '--accent-dim:rgba(66,201,138,.14);--down:#ff7777}')

USAGE_BAR_CSS = ('.urow{display:flex;align-items:center;gap:8px}\n'
                 '.ubar{height:6px;flex:1;overflow:hidden;border-radius:99px;background:var(--surface2)}\n'
                 '.ufill{height:100%;background:var(--accent);border-radius:inherit}')

HEADER_CSS = ('.top{border-bottom:1px solid var(--line);background:rgba(250,248,243,.94);backdrop-filter:blur(8px);position:sticky;top:0;z-index:20}\n'
              '.nav{min-height:66px;display:flex;align-items:center;gap:34px}\n'
              '.brand{font-family:var(--mono);font-weight:700;font-size:18px;letter-spacing:-.02em;white-space:nowrap}\n'
              '.brand .prompt{color:var(--accent)}\n'
              '.brand .cursor{display:inline-block;width:9px;height:17px;background:var(--accent);vertical-align:-3px;margin-left:5px;animation:blink 1.1s steps(1) infinite}\n'
              '@keyframes blink{50%{opacity:0}}\n'
              'nav{display:flex;gap:26px;align-items:center;flex:1}\n'
              'nav a{font-size:13.5px;font-weight:600;padding-block:12px;color:var(--muted)}\n'
              'nav a{min-height:44px;display:inline-flex;align-items:center}\n'
              'nav a:hover{color:var(--accent)}\n'
              'nav a.secondary{margin-left:auto;font-family:var(--mono);font-size:12.5px}')

FOOTER_CSS = ('.footer{border-top:1px solid var(--line);padding:26px 0 38px;color:var(--dim);font-size:12px;background:var(--surface2)}\n'
              '.footer-row{display:flex;flex-wrap:wrap;justify-content:space-between;gap:14px;align-items:center}\n'
              '.footer-row .fbrand{font-family:var(--mono);color:var(--muted)}\n'
              '.footer p{margin:16px 0 0;max-width:860px;line-height:1.7}\n'
              '.footer-links{display:flex;flex-wrap:wrap;gap:10px 20px;margin-top:16px;font-size:12.5px}\n'
              '.footer-links a{color:var(--muted);text-decoration:underline;text-underline-offset:3px}\n'
              '.footer-links a:hover{color:var(--accent)}')

SUBPAGE_CSS = """\
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.75 var(--sans)}
.wrap{max-width:1120px;margin:auto;padding-inline:28px}
.page-main{max-width:900px;margin:auto;padding:52px 28px 72px}
.page-head{padding-bottom:30px;border-bottom:1px solid var(--line)}
.page-eyebrow{margin:0 0 12px;color:var(--accent);font:12px/1.5 var(--mono);letter-spacing:.1em}
.page-title{margin:0;font-size:clamp(32px,6vw,52px);line-height:1.2;letter-spacing:-.04em}
.page-intro{max-width:720px;margin:14px 0 0;color:var(--muted);font-size:16px;word-break:keep-all}
.page-posts{margin-top:24px;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);overflow:hidden}
.page-post{padding:22px 24px;border-bottom:1px solid var(--line)}
.page-post:last-child{border-bottom:0}
.page-post time{color:var(--dim);font:12px/1.5 var(--mono)}
.page-post h2{margin:8px 0;font-size:20px;line-height:1.45}
.page-post p{margin:0;color:var(--muted);font-size:14px;word-break:keep-all}
.page-post .read{display:inline-block;margin-top:12px;color:var(--accent);font:12px/1.5 var(--mono)}
.page-indicators{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:24px}
.page-back{display:inline-block;margin-top:24px;color:var(--accent);font:13px/1.5 var(--mono)}
@media(max-width:767px){
  .wrap{padding-inline:18px}.page-main{padding:36px 18px 52px}
  .page-indicators{grid-template-columns:1fr}.page-post{padding:18px}
}
"""

INDICATOR_CSS = """\
.indicators{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px}
.indicator{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:26px;transition:border-color .25s,transform .25s}
.indicator:hover{border-color:rgba(10,122,74,.45);transform:translateY(-3px)}
.chart-open{display:block;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;margin-bottom:18px;background:#0d1117}
.chart-open img{display:block;width:100%;height:auto;aspect-ratio:1404/1281;object-fit:cover}
.chart-caption{display:block;padding:9px 13px;color:var(--muted);font-size:11.5px;border-top:1px solid var(--line);background:var(--surface)}
.indicator .icode{font-family:var(--mono);font-size:11px;color:var(--dim);letter-spacing:.08em}
.indicator h3{font-size:20px;margin:10px 0 8px;letter-spacing:-.015em;font-weight:700}
.indicator p{color:var(--muted);font-size:14px;margin:0 0 20px;word-break:keep-all;line-height:1.7}
.indicator .free{display:inline-block;font-family:var(--mono);font-size:11px;color:var(--accent);border:1px solid rgba(0,229,160,.3);background:var(--accent-dim);border-radius:3px;padding:3px 9px;margin-bottom:16px}
@media(max-width:767px){.indicators{grid-template-columns:1fr}}
"""


def shared_css() -> str:
    """Return the common tokens and components included in page stylesheets."""
    return '\n'.join((CSS_CUSTOM_PROPERTIES, BUTTON_CSS, HEADER_CSS, FOOTER_CSS,
                      DARK_THEME_CSS, USAGE_BAR_CSS))


def theme_head_script() -> str:
    """Read the saved color theme before paint, without making storage mandatory."""
    return ('<script>(function(){try{var t=localStorage.getItem("tbn-theme");'
            'if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t)'
            '}catch(e){}})();</script>')


def render_header() -> str:
    return ('<header class="top"><div class="wrap nav"><a class="brand" href="/" aria-label="TeemoBKK 홈">'
            '<span class="prompt">teemo@bkk</span>:~$ ./live-news<span class="cursor" aria-hidden="true"></span>'
            '</a><nav aria-label="주요 메뉴"><a href="/news/ko/">경제 뉴스</a><a href="/perspectives/">시장 관점</a>'
            '<a href="/indicators/">트레이딩뷰 지표</a><a href="/tradingtalk/">트레이딩 톡</a>'
            '<a href="/lab/">지표 연구</a><a class="secondary" href="/thai/">/thai ↗</a></nav></div></header>')


def render_footer() -> str:
    return ('<footer class="footer"><div class="wrap"><div class="footer-row">'
            '<span class="fbrand">teemo@bkk:~$ ./live-news --v2026</span>'
            '<a href="/thai/">별도 소식 · 태국 교민 뉴스 ↗</a></div>'
            '<p>뉴스는 자동 매매 신호가 아닙니다 · 중요한 사건은 원문과 공시로 확인하세요. 제공되는 글과 지표만으로 투자 결정을 내리지 마세요.</p>'
            '<nav class="footer-links" aria-label="사이트 정보"><a href="/privacy/">개인정보 처리방침</a>'
            '<a href="https://kr.tradingview.com/u/TeemoBKK/" target="_blank" rel="noopener noreferrer me">트레이딩뷰 TeemoBKK 공식 프로필 ↗</a>'
            '<a href="https://t.me/+OegpDrwxnaBiOGNl" target="_blank" rel="noopener noreferrer">트레이딩뷰 TeemoBKK 텔레그램 대화방 초대 링크 ↗</a></nav>'
            '<p class="note">텔레그램 링크는 외부 대화방으로 이동합니다.</p></div></footer>')


def display_date(value: str) -> str:
    """Use Korean date words for visible copy, keeping ISO 8601 in datetime."""
    try:
        day = date.fromisoformat(value)
        return f"{day.year}년 {day.month}월 {day.day}일"
    except (TypeError, ValueError):
        return value


# Page-specific stylesheet sources retained byte-for-byte during centralization.
THAI_CSS = ':root{color-scheme:light;--bg:#faf6ee;--surface:#fffdf8;--text:#2b2135;--muted:#6f6580;--line:#e8ddc8;\n--purple:#4a1d6b;--purple-deep:#341347;--gold:#c9a227;--gold-soft:#e8d48b;--gold-dim:rgba(201,162,39,.14);\n--radius:10px;--sans:system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;\n--serif:"Noto Serif KR","Nanum Myeongjo",Georgia,serif;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}\n*{box-sizing:border-box}html{scroll-padding-top:80px}\nbody{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.65;-webkit-font-smoothing:antialiased}\na{color:inherit;text-decoration:none}button{font:inherit;cursor:pointer}\na:hover{color:var(--purple)}a:focus-visible,button:focus-visible{outline:3px solid var(--gold);outline-offset:3px}\n[hidden]{display:none!important}\n.wrap{max-width:1080px;margin:auto;padding-inline:28px}\n.skip{position:absolute;left:16px;top:-100px;background:var(--purple);color:#fff;padding:12px;z-index:50;border-radius:6px}\n.skip:focus{top:12px}\n/* Thai kanok-inspired divider pattern */\n.thai-rule{height:14px;border:0;margin:0;background:url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'14\' viewBox=\'0 0 48 14\'%3E%3Cpath d=\'M0 7 Q12 0 24 7 T48 7\' fill=\'none\' stroke=\'%23c9a227\' stroke-width=\'1.6\' opacity=\'.55\'/%3E%3Ccircle cx=\'24\' cy=\'7\' r=\'2.4\' fill=\'%23c9a227\' opacity=\'.7\'/%3E%3C/svg%3E") repeat-x center;background-size:48px 14px;opacity:.8}\n/* Header */\n.top{background:rgba(250,246,238,.96);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}\n.nav{min-height:68px;display:flex;align-items:center;gap:30px}\n.brand{font-family:var(--serif);font-weight:700;font-size:21px;letter-spacing:-.03em;white-space:nowrap}\n.brand .t{color:var(--purple)}.brand .g{color:var(--gold)}\nnav{display:flex;gap:24px;align-items:center;flex:1}\nnav a{font-size:14px;font-weight:600;padding-block:12px}\nnav a:hover{color:var(--purple)}\n.secondary{margin-left:auto;color:var(--muted);font-size:13px}\n/* Hero */\n.hero{position:relative;margin:0;padding:0;overflow:hidden;border-radius:0 0 18px 18px}\n.hero-bg{position:absolute;inset:0;background:url("__HERO_IMG__") center 38%/cover no-repeat}\n.hero-veil{position:absolute;inset:0;background:linear-gradient(180deg,rgba(52,19,71,.62) 0%,rgba(52,19,71,.42) 45%,rgba(52,19,71,.78) 100%)}\n.hero-inner{position:relative;max-width:1080px;margin:auto;padding:96px 28px 72px;color:#fff}\n.eyebrow{display:inline-flex;align-items:center;gap:10px;font-size:12.5px;letter-spacing:.14em;font-weight:700;color:var(--gold-soft);margin:0 0 20px;text-transform:uppercase}\n.eyebrow::before{content:"";width:34px;height:2px;background:var(--gold);display:inline-block}\nh1{font-family:var(--serif);font-size:clamp(38px,5.4vw,64px);line-height:1.18;letter-spacing:-.03em;margin:0;font-weight:800}\nh1 .gold{color:var(--gold-soft)}\n.intro{max-width:620px;font-size:17px;line-height:1.8;margin:22px 0 30px;color:rgba(255,255,255,.92);word-break:keep-all}\n.actions{display:flex;flex-wrap:wrap;gap:12px}\n.button{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:700;border:1px solid rgba(255,255,255,.4);color:#fff;background:rgba(255,255,255,.08);backdrop-filter:blur(4px)}\n.button.primary{background:var(--gold);border-color:var(--gold);color:#3a2a05}\n.button:hover{transform:translateY(-1px)}\n.button.primary:hover{background:var(--gold-soft)}\n.stats{display:flex;flex-wrap:wrap;gap:14px 40px;margin-top:38px}\n.stat b{display:block;font-family:var(--mono);font-size:24px;color:var(--gold-soft)}\n.stat span{font-size:12.5px;color:rgba(255,255,255,.75)}\n/* Category filter chips */\n.filters{display:flex;flex-wrap:wrap;gap:10px;margin:26px 0 42px}\n.chip{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:9px 18px;font-size:13px;font-weight:600;color:var(--muted);transition:all .2s}\n.chip:hover{border-color:var(--gold);color:var(--purple)}\n.chip.active{background:var(--purple);border-color:var(--purple);color:#fff}\n/* Sections */\n.section{padding:44px 0 52px}\n.section-head{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:6px}\nh2{font-family:var(--serif);font-size:29px;letter-spacing:-.02em;margin:0;font-weight:700}\nh2 .n{font-family:var(--mono);font-size:13px;color:var(--gold);letter-spacing:.1em;margin-right:10px;vertical-align:middle}\n.section-intro{margin:8px 0 0;color:var(--muted);font-size:15px;max-width:720px;word-break:keep-all}\n.news-status{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin:20px 0 8px;color:var(--muted);font-size:12.5px}\n.news-status .live{color:var(--purple);font-weight:700}\n.retry{background:transparent;color:var(--purple);border:1px solid var(--line);border-radius:6px;min-height:36px;padding:5px 14px;font-size:12.5px}\n.retry:hover{border-color:var(--purple)}\n.news-list{display:grid;grid-template-columns:1fr 1fr;column-gap:36px}\n.news-item{min-width:0;padding:20px 0;border-bottom:1px solid var(--line)}\n.news-item .meta{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--muted)}\n.news-item .topic{color:var(--purple);font-weight:700}\n.news-item h3{font-size:17.5px;line-height:1.55;letter-spacing:-.015em;font-weight:600;margin:8px 0 0;overflow-wrap:anywhere}\n.news-item a{display:block}\n.news-item a:hover h3{color:var(--purple)}\n/* News cards: feature + 3-col grid */\n.news-feature{margin:24px 0 4px}\n.fcard{display:grid;grid-template-columns:1.15fr 1fr;background:var(--surface);border:1px solid var(--line);border-radius:0;overflow:hidden}\n.fcard-img{min-height:300px;background:var(--purple-deep) center/cover no-repeat}\n.fcard-body{padding:32px;display:flex;flex-direction:column;justify-content:center}\n.fcard .topic{display:inline-block;font-size:12px;font-weight:700;color:var(--gold);letter-spacing:.1em;margin-bottom:12px}\n.fcard h3{font-family:var(--serif);font-size:25px;line-height:1.42;margin:0 0 12px;letter-spacing:-.02em;font-weight:700}\n.fcard h3 a:hover{color:var(--purple)}\n.fcard .sum{color:var(--muted);font-size:14.5px;margin:0 0 18px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}\n.fcard .meta{font-size:12px;color:var(--muted);display:flex;gap:12px;flex-wrap:wrap}\n.news-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:20px}\n.ncard{background:var(--surface);border:1px solid var(--line);border-radius:0;overflow:hidden;display:flex;flex-direction:column;transition:transform .25s,box-shadow .25s}\n.ncard:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(74,29,107,.14)}\n.ncard-img{aspect-ratio:16/9;background:var(--purple-deep) center/cover no-repeat}\n.ncard-body{padding:18px 18px 16px;display:flex;flex-direction:column;flex:1}\n.ncard .topic{font-size:11.5px;font-weight:700;color:var(--purple);letter-spacing:.06em;margin-bottom:8px}\n.ncard h3{font-size:16px;line-height:1.52;margin:0 0 8px;font-weight:700;letter-spacing:-.015em;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}\n.ncard h3 a:hover{color:var(--purple)}\n.ncard .sum{color:var(--muted);font-size:13px;margin:0 0 14px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;flex:1}\n.ncard .meta{font-size:11.5px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}\n.img-fallback{background:linear-gradient(135deg,var(--purple) 0%,var(--purple-deep) 100%)!important;display:flex!important;align-items:center;justify-content:center;color:var(--gold-soft);font-family:var(--serif);font-size:30px;font-weight:700;min-height:120px}\n.fcard-img.img-fallback{min-height:300px}\n.empty{color:var(--muted);padding:24px 0;grid-column:1/-1}\n.loading-line{height:14px;background:var(--line);opacity:.5;margin:12px 0;border-radius:4px;max-width:88%}\n.loading-line.short{max-width:42%;height:11px}\n.section-link{display:inline-block;margin-top:18px;color:var(--purple);font-size:14px;font-weight:700}\n.section-link:hover{color:var(--gold)}\n/* Topics grid */\n.topics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:24px}\n.topic-link{display:block;padding:20px;background:var(--surface);border:1px solid var(--line);border-radius:0;border-top:3px solid var(--gold);transition:transform .25s,box-shadow .25s}\n.topic-link:hover{transform:translateY(-3px);box-shadow:0 10px 28px rgba(74,29,107,.12);color:inherit}\n.topic-link b{display:block;font-size:16px;font-weight:700}\n.topic-link span{display:block;margin-top:6px;font-size:12.5px;color:var(--muted)}\n/* Living info */\n.living{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:24px}\n.living-card{background:linear-gradient(135deg,var(--purple) 0%,var(--purple-deep) 100%);color:#fff;border-radius:var(--radius);padding:24px}\n.living-card h3{margin:0 0 8px;font-size:17px;color:var(--gold-soft)}\n.living-card p{margin:0;font-size:13.5px;color:rgba(255,255,255,.82);line-height:1.7}\n/* About */\n.about{display:grid;grid-template-columns:1fr 1fr;gap:48px}\n.about p{color:var(--muted);font-size:15px;margin:10px 0;word-break:keep-all}\n.about h3{font-size:17px;margin:0 0 10px}\n.about ul{list-style:none;padding:0;margin:0;color:var(--muted);font-size:14px}\n.about li{margin:10px 0;padding-left:18px;position:relative}\n.about li::before{content:"◆";position:absolute;left:0;color:var(--gold);font-size:10px;top:4px}\n/* Footer */\n.footer{border-top:1px solid var(--line);background:var(--purple-deep);color:rgba(255,255,255,.72);padding:30px 0 40px;font-size:12.5px;margin-top:20px}\n.footer-row{display:flex;flex-wrap:wrap;justify-content:space-between;gap:14px;align-items:center}\n.footer-row .flogo{font-family:var(--serif);font-weight:700;font-size:16px;color:#fff}\n.footer-row .flogo .g{color:var(--gold-soft)}\n.footer a{color:rgba(255,255,255,.85)}\n.footer a:hover{color:var(--gold-soft)}\n.footer p{margin:14px 0 0;max-width:860px}\n.footer-links{display:flex;flex-wrap:wrap;gap:10px 20px;margin-top:14px}\n.note{font-size:12px;color:var(--muted);margin-top:20px;max-width:860px}\n@media(max-width:900px){.news-grid{grid-template-columns:repeat(2,1fr)}}\n@media(max-width:767px){\n.wrap{padding-inline:28px}.hero{margin:0}\n.hero-inner{padding:88px 28px 72px}\n.nav{min-height:62px;gap:16px;flex-wrap:wrap;padding-block:14px}\nnav{gap:18px;flex-basis:100%;order:2}\nnav a{font-size:13px;padding:6px 0}\n.secondary{display:none}\n.section{padding:48px 0}\n.section-head{margin-bottom:28px}\n.news-list{grid-template-columns:1fr}\n.fcard{grid-template-columns:1fr}\n.fcard-img{min-height:210px}\n.fcard-img.img-fallback{min-height:210px}\n.fcard-body{padding:28px}\n.fcard h3{font-size:21px}\n.news-grid{grid-template-columns:1fr;gap:24px}\n.ncard-body{padding:22px}\n.about{grid-template-columns:1fr;gap:0}\n.about>div+div{margin-top:28px}\n.filters{gap:8px;margin-bottom:56px}.chip{padding:8px 14px;font-size:12.5px}\n}\n@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}'
DASHBOARD_CSS = """\
:root{
  --bg:#0a0e1a; --panel:#111a2c; --panel2:#16213a; --text:#eef3ff; --muted:#8b9bbd;
  --line:#243252; --line2:#2e3d61; --accent:#64d7ff; --thai:#ffd479; --hot:#ffb86b;
  --official:#8fe3a8; --warn:#ff9a3c; --r-card:14px; --r-ctl:10px; --r-pill:999px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
a{color:inherit;text-decoration:none}
button,input,select{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;border:0}
.wrap{max-width:1180px;margin:0 auto;padding:26px 22px 40px}
.bar{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--line);
  background:rgba(10,14,26,.92);backdrop-filter:blur(10px)}
.bar-in{max-width:1180px;margin:0 auto;padding:14px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:11px;color:var(--accent)}
h1{font-size:19px;margin:0;letter-spacing:-.01em}
.spacer{flex:1}
.stamp{color:var(--muted);font-size:12px;text-align:right;line-height:1.5}
.stamp b{color:var(--text);font-weight:600}
.theme-toggle{flex:0 0 auto;min-height:40px;padding:7px 11px;border:1px solid var(--line);
  border-radius:4px;background:transparent;color:var(--text);font-size:12px;font-weight:650;cursor:pointer}
.theme-toggle:hover{border-color:var(--accent);color:var(--accent)}
.stale{display:none;margin-top:5px;border:1px solid var(--warn);color:var(--warn);
  border-radius:var(--r-pill);padding:3px 10px;font-size:11.5px}
.stale[data-show="1"]{display:inline-block}
.tabs{display:flex;gap:6px;margin:22px 0 12px;border-bottom:1px solid var(--line)}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:11px 16px;cursor:pointer;
  color:var(--muted);font-weight:600;font-size:17px;letter-spacing:-.01em;margin-bottom:-1px}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab.th.active{color:var(--thai);border-bottom-color:var(--thai)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
input[type=search],select{background:var(--panel2);border:1px solid var(--line);border-radius:var(--r-ctl);padding:9px 12px;min-width:0}
input[type=search]{flex:1 1 220px}
input[type=search]::placeholder{color:var(--muted)}
select{cursor:pointer}
#logout{cursor:pointer;background:none;border:1px solid var(--line);color:var(--muted);
  border-radius:var(--r-ctl);padding:8px 12px}
#logout:hover{border-color:var(--accent);color:var(--accent)}
.count{color:var(--muted);font-size:12px;margin-left:auto}
.newpill{display:none;align-items:center;background:#123047;border:1px solid var(--accent);color:var(--accent);
  border-radius:var(--r-pill);padding:7px 14px;cursor:pointer;font-size:12.5px;font-weight:600}
.newpill[data-show="1"]{display:inline-flex}
.pills{display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px;margin-bottom:6px}
.pills::-webkit-scrollbar{height:6px}
.pills::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}
@media (min-width:900px){.pills{flex-wrap:wrap;overflow-x:visible}}
.pills[hidden]{display:none!important}
.trend{display:flex;gap:0;align-items:stretch;flex-wrap:nowrap;overflow:visible;margin:0 0 10px;padding:0}
.trend .tlabel{flex:0 0 auto;display:flex;align-items:center;padding:2px 10px 8px 2px;
  border-right:1px solid var(--line);margin-right:10px}
.trend .ttrack{flex:1 1 auto;min-width:0;display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px}
.trend .ttrack::-webkit-scrollbar{height:6px}
.trend .ttrack::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}
@media (hover:hover){}
.trend .tbtn.on{border-color:var(--accent);background:var(--accent);color:#08111f;font-weight:600}
.trend .tbtn.on .n{color:#08111f;opacity:.65}
.trend .tbtn.clear{border-style:dashed;border-color:var(--warn);color:var(--warn);font-weight:600}
@media (hover:hover){.trend .tbtn:hover{border-color:var(--accent);color:var(--accent)}}
@media (min-width:900px){.trend .ttrack{flex-wrap:wrap;overflow-x:visible}}
.trend[hidden]{display:none!important}
.trend .tlabel{color:var(--muted);font-size:12px;white-space:nowrap}
.trend .n{color:var(--muted);font-size:11px;margin-left:6px}
/* The selected conditions, in one row: every filter that is currently narrowing the list, each
   with its own count and a way out. The number after the arrow is what all of them together
   return, which is the difference between this row and the pill rows above it. */
.conds{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0 0 10px;padding:6px 8px;
  border:1px solid var(--line);border-radius:var(--r);background:var(--bg2)}
.conds[hidden]{display:none!important}
.conds .clabel{color:var(--muted);font-size:12px;white-space:nowrap;margin-right:2px}
.conds .cbtn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--accent);
  background:var(--accent);color:#08111f;font-weight:600;font-size:12px;
  border-radius:var(--r-pill);padding:4px 10px;cursor:pointer}
.conds .cbtn .n{color:#08111f;opacity:.7;font-size:11px}
/* A keyword condition is outlined, a category or source condition is filled: the difference has to
   be visible without a word, because a word here would need translating. */
.conds .cbtn.kw{background:none;color:var(--accent);border-color:var(--accent)}
.conds .cbtn.kw .n{color:var(--accent);opacity:.75}
.conds .sum{color:var(--muted);font-size:12px;margin-left:4px}
.conds .warn{color:var(--warn);font-weight:600}
.conds button.wide{border:1px dashed var(--accent);background:none;color:var(--accent);
  border-radius:var(--r-pill);padding:4px 10px;font-size:12px;cursor:pointer}
.qadd{border:1px solid var(--line);background:none;color:var(--muted);border-radius:var(--r-pill);
  padding:5px 10px;font-size:12px;white-space:nowrap;cursor:pointer}
/* The operator's way out of a story, and the strip that says what just went away. Hiding is not a
   delete, so the undo stays until the next action: the way back has to be where the click was. */
.acts{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.acts .hide{background:none;border:0;cursor:pointer;font-family:inherit;padding:0}
.acts .hide:hover{color:var(--warn)}
.undobar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 12px;padding:8px 12px;
  border:1px solid var(--warn);border-radius:var(--r-card)}
.undobar[hidden]{display:none!important}
.undobar .clabel{color:var(--warn);font-size:12px;font-weight:600;white-space:nowrap}
.undobar .utext{color:var(--muted);font-size:12.5px;max-width:52ch;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.hidrow{display:flex;gap:10px;align-items:baseline;justify-content:space-between;padding:5px 0;
  border-bottom:1px solid var(--line);font-size:12.5px}
.hidrow:last-child{border-bottom:0}
.hidrow a{color:#c3cfe6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;flex:1}
.hidrow a:hover{color:var(--accent)}
/* Admin sidebar tables must not push past the page width: long source names and
   article titles ellipsis instead of overflowing. */
.side.admin{min-width:0;overflow:hidden}
.side.admin .box{min-width:0;overflow:hidden}
.source>*{min-width:0}
.source span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.unhide{background:none;border:1px solid var(--line);border-radius:var(--r-pill);padding:3px 10px;
  color:var(--muted);cursor:pointer;font-size:11.5px;flex:0 0 auto}
.unhide:hover{border-color:var(--accent);color:var(--accent)}
@media (hover:hover){.qadd:hover{border-color:var(--accent);color:var(--accent)}}
/* Own class rather than the filter chips' ".chip.tap": those are toggles carrying
   aria-pressed, while a trend button is a one-shot search action. Reusing the class
   made every ".chip.tap" invariant assertion count a chip that is not a toggle. */
.trend .tbtn{border:1px solid var(--line);border-radius:var(--r-pill);padding:5px 11px;
  background:none;font-family:inherit;font-size:12.5px;color:var(--text);cursor:pointer;white-space:nowrap}

.pill{flex:0 0 auto;background:none;border:1px solid var(--line);border-radius:var(--r-pill);
  padding:7px 14px;cursor:pointer;font-size:12.5px;color:var(--muted);white-space:nowrap}
.pill.active{background:var(--panel2);border-color:var(--accent);color:var(--accent)}
.pill.th.active{border-color:var(--thai);color:var(--thai)}
.pill.on{border-color:var(--accent);color:var(--accent)}
/* Source chips sit in the same row as the category pills but are a different axis, so they
   are dashed and separated. */
.pill.src{border-style:dashed}
/* Teemo's Pick: the operator's judgement, shown to readers. Warmer than the filter pills and never
   a rank - selecting it narrows the list, the order stays newest first. */
.pill.pick{border-color:#21c997;color:#21c997}
.pill.pick.active{background:#0d2b22;border-color:#21c997;color:#b9f5e1;font-weight:600}
.pickbadge{display:inline-flex;align-items:center;gap:8px;margin:0 0 8px;padding:3px 10px;
  border:1px solid #21c997;border-radius:var(--r-pill);color:#7de8c4;font-size:12px;font-weight:600}
/* The phrase is one line in the row, and the whole thing on hover: a long note used to be cut off
   with no way to read it. The overlay is absolute so it does not move the headline under it. */
.pickbadge .pnote{color:#d6f7ec;font-weight:500;max-width:46ch;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;cursor:help}
.pickbadge:hover .pnote{position:absolute;z-index:5;margin-top:2px;max-width:min(72ch,84vw);white-space:normal;
  overflow:visible;background:var(--panel);border:1px solid #21c997;border-radius:var(--r-ctl);
  padding:8px 12px;box-shadow:0 6px 20px rgba(0,0,0,.5)}
.pill.src.th.active{border-color:var(--thai);color:var(--thai)}
.pillsep{flex:0 0 auto;width:1px;margin:0 3px;background:var(--line2);align-self:stretch}
.langbar{display:flex;gap:6px;align-items:center;font-size:13px}
.langbar a,.langbar b{padding:4px 10px;border:1px solid var(--line);border-radius:var(--r-pill);
  color:var(--muted);font-weight:500;text-decoration:none}
.langbar b{border-color:var(--accent);color:var(--accent);font-weight:600}
.pill i{font-style:normal;opacity:.6;margin-left:5px;font-size:11.5px}
.sec{display:flex;align-items:center;gap:10px;margin:18px 0 8px;color:var(--muted);font-size:12px;font-weight:600}
.sec::after{content:"";flex:1;height:1px;background:var(--line)}
.feed{display:grid;grid-template-columns:1fr;gap:12px;margin-top:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-card);padding:16px;
  border-left:3px solid var(--accent)}
.card.th{border-left-color:var(--thai)}
.card.new{border-left-color:var(--hot);box-shadow:0 0 0 1px rgba(255,184,107,.22)}
.meta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:12px;margin-bottom:9px}
.chip{border:1px solid var(--line);border-radius:var(--r-pill);padding:5px 11px;white-space:nowrap;
  background:none;font-size:12px;font-family:inherit}
.chip.src{background:var(--panel);color:var(--text)}
.chip.official{border-color:var(--official);color:var(--official)}
.chip.hot{border-color:var(--hot);color:var(--hot)}
.chip.th{border-color:#5a4a24;color:var(--thai)}
.chip.speak{border-color:#ffb86b;color:#ffb86b}
.chip.verif{border-color:var(--line2);color:var(--muted);letter-spacing:.02em}
.chip.verif.off{border-color:var(--official);color:var(--official)}
.chip.verif.sns{border-color:#b48cff;color:#c7a8ff}
.chip.static{cursor:default}
.chip.tap{cursor:pointer}
.chip.tap:hover,.chip.tap.on{border-color:var(--accent);color:var(--accent)}
.title{font-size:17px;line-height:1.45;letter-spacing:-.01em;font-weight:600;margin:0 0 7px}
.title a:hover{color:var(--accent)}
.title a::after{content:"";position:absolute;inset:0}
.card{position:relative}
.chip.tap,.expand,.cal-n a{position:relative;z-index:1}
.summary{color:#c3cfe6;font-size:14px;max-width:65ch;margin:0 0 8px}
.summary.clamp{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.expand{background:none;border:0;padding:0 0 6px;color:var(--accent);font-size:12.5px;cursor:pointer;font-weight:600}
.card.th .expand{color:var(--thai)}
.open{color:var(--muted);font-size:12.5px;border-bottom:1px solid var(--line)}
.open:hover{color:var(--accent);border-bottom-color:var(--accent)}
mark{background:#3f3418;color:#ffe9b0;border-radius:3px;padding:0 2px}
.skel{border:1px solid var(--line);border-radius:var(--r-card);padding:16px;background:var(--panel)}
.skel span{display:block;height:12px;border-radius:6px;background:linear-gradient(90deg,#18233b,#22304f,#18233b);
  background-size:200% 100%;animation:sh 1.4s linear infinite;margin-bottom:10px}
.skel span:nth-child(1){width:35%}
.skel span:nth-child(2){width:90%}
.skel span:nth-child(3){width:70%}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){.skel span{animation:none}}
.empty{border:1px dashed var(--line);border-radius:var(--r-card);padding:44px 18px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--text);margin-bottom:6px;font-size:15px}
.layout{display:grid;grid-template-columns:minmax(0,1fr);gap:18px}
.side{display:grid;gap:12px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-card);padding:14px}
.box h2{font-size:12.5px;margin:0 0 9px;color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.box p{margin:0 0 8px}
.source{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;padding:4px 0;border-bottom:1px solid var(--line)}
.source:last-child{border-bottom:0}
/* the switch sits in the collection-status row, left of the name */
.source.off > span:first-of-type{color:var(--muted);text-decoration:line-through}
.source > span:first-of-type{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sw{flex:0 0 auto;width:34px;height:18px;border-radius:999px;border:1px solid var(--line2);background:var(--panel2);position:relative;cursor:pointer;padding:0}
.sw .knob{position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:var(--muted);transition:left .14s}
.sw[aria-checked="true"]{border-color:var(--accent);background:rgba(100,215,255,.18)}
.sw[aria-checked="true"] .knob{left:18px;background:var(--accent)}
.rule{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--line2)}
.rule .rp{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}
.rule.off .rp{color:var(--muted);text-decoration:line-through}
.rule .rh{flex:0 0 auto;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px}
.rule .rx{flex:0 0 auto;border:0;background:none;color:var(--muted);cursor:pointer;font-size:12px;padding:0 2px}
.rule .rx:hover{color:var(--accent)}
.frow{display:flex;gap:6px;margin:8px 0 6px}
.frow input{flex:1 1 auto;min-width:0;background:var(--panel2);border:1px solid var(--line2);color:inherit;
border-radius:6px;padding:5px 7px;font-size:12px}
.wide{width:100%;background:var(--panel2);border:1px solid var(--line2);color:inherit;border-radius:6px;
padding:5px 7px;font-size:12px;cursor:pointer}
.caught{display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid var(--line2)}
.caught .ct{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:var(--muted)}
.caught .keep{flex:0 0 auto;border:0;background:none;color:var(--accent);cursor:pointer;font-size:11px;padding:0}
.source .ok{color:var(--official)}
.source .bad{color:var(--hot)}
.note{color:var(--muted);font-size:12px}
.more-wrap{display:flex;justify-content:center;gap:10px;padding:20px 0 6px}
#more,#totop{padding:11px 28px;font-weight:700;background:var(--panel2);border:1px solid var(--line);
  border-radius:var(--r-ctl);cursor:pointer}
#more:hover,#totop:hover{border-color:var(--accent);color:var(--accent)}
.cal{display:none;margin:0 0 14px;padding:14px 16px;border:1px solid var(--line);border-radius:var(--r-card);background:var(--panel)}
.cal h2{margin:0 0 4px;font-size:12.5px;color:var(--muted);font-weight:600}
.cal-sum{color:var(--muted);font-size:11.5px;margin:0 0 12px}
.cal-grid{display:grid;grid-template-columns:1fr;gap:2px 22px}
.cal-day h3{margin:0 0 6px;font-size:13px}
.cal-row{display:grid;grid-template-columns:68px minmax(0,1fr) auto;gap:8px;align-items:baseline;
  padding:4px 0 4px 8px;border-bottom:1px solid var(--line);border-left:2px solid transparent;font-size:13px}
.cal-row.i5{border-left-color:#e04242}
.cal-row.i4{border-left-color:#ff7a45}
.cal-t{font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}
.cal-n{color:#c3cfe6}
.cal-v{color:var(--muted);font-size:12px}
.cal-v b.up{color:#5fd08a}
.cal-v b.down{color:#ff6b6b}
.cal-v b.flat{color:#ffd479}
.cal-v b{color:var(--official)}
.cal-row.speech .cal-t{color:#8ea3c4}
.cal-row.earnings .cal-t{color:#e1ceb6}
.cal-row.potus .cal-t,.cal-row.potus .cal-n a{color:#ffb86b}
.cal-n a{color:inherit;text-decoration:none}
.cal-n a:hover{text-decoration:underline}
.cal-err{border:1px dashed var(--line);border-radius:var(--r-ctl);padding:14px;color:var(--muted);font-size:12.5px}
.cal-err button{margin-left:10px;background:var(--panel2);border:1px solid var(--line);
  border-radius:var(--r-ctl);padding:6px 14px;cursor:pointer}
@media (max-width:900px){.cal-row{grid-template-columns:68px minmax(0,1fr)}.cal-row .cal-v{grid-column:1 / -1;padding-left:0}}
body.tab-cal .cal{display:block}
body.tab-cal .toolbar,body.tab-cal .pills,body.tab-cal .trend,body.tab-cal #feed,body.tab-cal .more-wrap,body.tab-cal .side{display:none!important}
body.tab-cal .layout{grid-template-columns:minmax(0,1fr)}
.foot{color:var(--muted);font-size:12px;border-top:1px solid var(--line);margin-top:26px;padding-top:16px;line-height:1.8}
body.public .admin{display:none!important}
body.public .side{display:none}
body.public .layout{grid-template-columns:minmax(0,1fr)}
/* The stretched title link (whole card clickable) is for readers. The local instance is
   a working copy: text has to stay selectable so a headline can be dragged out, so the
   overlay is switched off there and a plain 원문 열기 link is shown instead. */
body.local .title a::after{content:none}
body.local .card{cursor:auto}
@media (max-width:1000px){.layout{grid-template-columns:minmax(0,1fr)}.side{grid-template-columns:1fr}}
@media (min-width:1080px){.feed{grid-template-columns:1fr 1fr}.card.lead{grid-column:1 / -1}}
@media (max-width:820px){
  .wrap{padding:16px 14px 32px}
  .bar-in{padding:12px 14px}
  h1{font-size:17px}
  .stamp{text-align:left;font-size:11.5px}
  .lead .title{font-size:20px}
  .count{margin-left:0;width:100%}
  /* Three tab labels at the desktop size overflow a phone; step down and allow a scroll
     rather than letting the row break. */
  .tabs{overflow-x:auto}
  .tab{padding:10px 12px;font-size:16px}
}
/* Reader and operator share the editorial palette; operator controls keep their own layout. */
body.public,body.local{
  color-scheme:light;--bg:#fbfaf7;--panel:#fff;--panel2:#f4f0e9;
  --text:#17181a;--muted:#454a50;--line:#e3ded4;--line2:#cec7b9;
  --accent:#a02c22;--thai:#8a5a12;--hot:#8a5a12;--official:#1f6b46;--warn:#8a5a12;
  --serif:"Noto Serif KR","Nanum Myeongjo","AppleMyungjo","Batang","바탕",Georgia,serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"D2Coding","Courier New",monospace;
  --sans:system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;
  background:var(--bg);font-family:var(--sans);
}
body.public .bar{background:var(--bg);backdrop-filter:none}
body.public .bar-in{max-width:1040px;min-height:76px;gap:16px;padding-block:12px}
body.public .brand{font-family:var(--serif);font-size:25px;line-height:1.2;letter-spacing:-.035em;text-transform:none;font-weight:700;color:var(--text)}
body.public .brand-accent{color:var(--accent)}
body.public h1{font-family:var(--serif);font-size:26px;line-height:1.25;letter-spacing:-.045em;font-weight:700}
body.public .stamp{font:11.5px/1.5 var(--mono);font-variant-numeric:tabular-nums}
body.public .wrap{max-width:1040px;padding-top:12px}
body.public .tabs{margin:8px 0 20px;gap:22px}
body.public .tab{font-size:15px;padding:12px 2px;color:var(--muted)}
body.public .tab.active,body.public .tab.th.active{color:var(--text);border-bottom-color:var(--accent)}
body.public .toolbar{padding:0 0 16px;margin-bottom:12px;border-bottom:1px solid var(--line)}
body.public input[type=search],body.public select{background:var(--panel);border-radius:4px}
body.public .qadd,body.public .pill,body.public .trend .tbtn,body.public .langbar a,body.public .langbar b{
  background:transparent;border-radius:4px;color:var(--muted)}
body.public .pill.active,body.public .pill.on,body.public .pill.pick.active,
body.public .trend .tbtn.on{background:color-mix(in srgb,var(--accent) 8%,var(--panel));border-color:var(--accent);color:var(--accent)}
body.public .pill.pick.active{border-color:var(--official);color:var(--official)}
body.public .pill.pick{border-color:var(--line);color:var(--muted)}
body.public .pill.th.active,body.public .pill.src.th.active{background:color-mix(in srgb,var(--thai) 8%,var(--panel));color:var(--thai);border-color:var(--thai)}
body.public .pills{margin-bottom:12px}
body.public .feed{display:block;margin-top:4px}
body.public .sec{margin:24px 0 8px;font-family:var(--serif);font-size:17px;letter-spacing:-.01em;color:var(--text)}
body.public .card,body.public .card.th,body.public .card.new,body.public .card.lead{
  background:transparent;border:0;border-bottom:1px solid var(--line);border-radius:0;
  box-shadow:none;padding:18px 2px 20px;max-width:none}
body.public .card.lead{padding-top:24px}
body.public .card:hover{background:var(--panel)}
body.public .meta{margin-bottom:7px;gap:7px 10px;font:11.5px/1.5 var(--mono);color:var(--muted)}
body.public .chip,body.public .chip.src,body.public .chip.th,body.public .chip.hot,
body.public .chip.official,body.public .chip.speak,body.public .chip.verif{
  background:transparent;border:0;border-radius:0;padding:0;color:var(--muted);font:inherit}
body.public .chip.tap{color:var(--accent);text-decoration:underline;text-underline-offset:3px}
body.public .title{font-family:var(--serif);font-size:20px;line-height:1.5;letter-spacing:-.015em;font-weight:600;margin-bottom:7px;overflow-wrap:anywhere}
body.public .card.lead .title{font-size:clamp(22px,2.6vw,29px);line-height:1.38}
body.public .title a:hover{color:var(--accent)}
body.public .summary,body.public .cal-n{color:var(--muted);font-size:14px;line-height:1.65}
body.public .pickbadge{border:0;border-radius:0;padding:0;color:var(--accent)}
body.public .pickbadge .pnote{color:var(--muted)}
body.public .empty,body.public .skel{background:var(--panel);border-radius:4px}
body.public .skel span{background:var(--line)}
body.public .cal{background:var(--panel);border-radius:4px}
body.public .cal-row{border-left-color:transparent}
body.public .foot{max-width:none}
@media(max-width:820px){
  body.public .bar-in{min-height:0;gap:6px 12px;padding:11px 16px}
  body.public .bar-in>div:first-child{width:100%}
  body.public h1{font-size:23px}
  body.public .spacer{display:none}
  body.public .stamp{margin-left:auto;text-align:right;font-size:11px}
  body.public .wrap{padding:8px 16px 28px}
  body.public .tabs{margin:4px 0 18px;gap:18px}
  body.public .tab{font-size:14px;white-space:nowrap}
  body.public .card,body.public .card.th,body.public .card.new{padding:16px 0 18px}
  body.public .title,body.public .card.lead .title{font-size:19px;line-height:1.45}
  body.public .summary{font-size:13px}
}
@media(prefers-color-scheme:dark){body.public,body.local{
  color-scheme:dark;--bg:#131417;--panel:#1b1d21;--panel2:#25272c;
  --text:#ececeb;--muted:#b9bcc0;--line:#2c2f34;--line2:#3b3f46;
  --accent:#e0776c;--thai:#d8ab5c;--hot:#d8ab5c;--official:#6fbf95;--warn:#d8ab5c}
  body.public .pill.active,body.public .pill.on,body.public .pill.pick.active,
  body.public .trend .tbtn.on,body.public .pill.th.active,body.public .pill.src.th.active{color:#17181a}
}}
/* The signed-in workspace uses the same reading language without hiding operator actions. */
body.local .bar{background:var(--bg);backdrop-filter:none}
body.local .bar-in{max-width:1040px;min-height:76px;gap:16px;padding-block:12px}
body.local .brand{font-family:var(--serif);font-size:25px;line-height:1.2;letter-spacing:-.035em;text-transform:none;font-weight:700;color:var(--text)}
body.local .brand-accent{color:var(--accent)}
body.local h1{font-family:var(--serif);font-size:26px;line-height:1.25;letter-spacing:-.045em;font-weight:700}
body.local .stamp{font:11.5px/1.5 var(--mono);font-variant-numeric:tabular-nums}
body.local .wrap{max-width:1040px;padding-top:12px}
body.local .tabs{margin:8px 0 20px;gap:22px}
body.local .tab{font-size:17px;padding:12px 2px;color:var(--muted)}
body.local .tab.active,body.local .tab.th.active{color:var(--text);border-bottom-color:var(--accent)}
body.local .toolbar{padding:0 0 16px;margin-bottom:12px;border-bottom:1px solid var(--line)}
body.local input[type=search],body.local select,body.local .frow input{
  background:var(--panel);border-color:var(--line);border-radius:4px}
body.local #logout,body.local .qadd,body.local .pill,body.local .trend .tbtn,
body.local .langbar a,body.local .langbar b{border-radius:4px;color:var(--muted)}
body.local .pill.active,body.local .pill.on,body.local .pill.pick.active,
body.local .trend .tbtn.on{background:color-mix(in srgb,var(--accent) 8%,var(--panel));border-color:var(--accent);color:var(--accent)}
body.local .pill.pick.active{border-color:var(--official);color:var(--official)}
body.local .pill.pick{border-color:var(--line);color:var(--muted)}
body.local .pill.th.active,body.local .pill.src.th.active{
  background:color-mix(in srgb,var(--thai) 8%,var(--panel));border-color:var(--thai);color:var(--thai)}
body.local .pills{margin-bottom:12px}
body.local .feed{display:block;margin-top:4px}
body.local .sec{margin:24px 0 8px;font-family:var(--serif);font-size:17px;letter-spacing:-.01em;color:var(--text)}
body.local .card,body.local .card.th,body.local .card.new,body.local .card.lead{
  background:transparent;border:0;border-bottom:1px solid var(--line);border-radius:0;
  box-shadow:none;padding:18px 2px 20px;max-width:none}
body.local .card.lead{padding-top:24px}
body.local .meta{margin-bottom:7px;gap:7px 10px;font:11.5px/1.5 var(--mono);color:var(--muted)}
body.local .chip,body.local .chip.src,body.local .chip.th,body.local .chip.hot,
body.local .chip.official,body.local .chip.speak,body.local .chip.verif{
  background:transparent;border:0;border-radius:0;padding:0;color:var(--muted);font:inherit}
body.local .chip.tap{color:var(--accent);text-decoration:underline;text-underline-offset:3px}
body.local .title{font-family:var(--serif);font-size:20px;line-height:1.5;letter-spacing:-.015em;font-weight:600;margin-bottom:7px;overflow-wrap:anywhere}
body.local .card.lead .title{font-size:clamp(22px,2.6vw,29px);line-height:1.38}
body.local .summary,body.local .cal-n{color:var(--muted);font-size:14px;line-height:1.65}
body.local .open,body.local .expand,body.local .acts .hide{color:var(--accent)}
body.local .pickbadge{border:0;border-radius:0;padding:0;color:var(--accent)}
body.local .pickbadge .pnote{color:var(--muted)}
body.local .layout{grid-template-columns:minmax(0,1fr);gap:32px}
body.local .side{display:grid;align-content:start;gap:16px}
body.local .box,body.local .cal,body.local .empty,body.local .skel{
  background:transparent;border-color:var(--line);border-radius:4px}
body.local .box{padding:14px 0;border:0;border-bottom:1px solid var(--line)}
body.local .box h2{font-family:var(--serif);text-transform:none;letter-spacing:-.01em;color:var(--text);font-size:17px}
body.local .source .ok{color:var(--official)}
body.local .source .bad{color:var(--hot)}
body.local .sw[aria-checked="true"]{background:var(--panel2)}
body.local .sw[aria-checked="true"] .knob{background:var(--accent)}
body.local .cal-row{border-left-color:transparent}
body.local .skel span{background:var(--line)}
body.local .foot{max-width:none}
@media(min-width:1001px){body.local:not(.tab-cal) .layout{grid-template-columns:minmax(0,1fr) 280px}}
@media(max-width:820px){
  body.local .bar-in{min-height:0;gap:6px 12px;padding:11px 16px}
  body.local .bar-in>div:first-child{width:100%}
  body.local h1{font-size:23px}
  body.local .spacer{display:none}
  body.local .stamp{margin-left:auto;text-align:right;font-size:11px}
  body.local .wrap{padding:8px 16px 28px}
  body.local .tabs{margin:4px 0 18px;gap:18px}
  body.local .tab{font-size:14px;white-space:nowrap}
  body.local .card,body.local .card.th,body.local .card.new{padding:16px 0 18px}
  body.local .title,body.local .card.lead .title{font-size:19px;line-height:1.45}
  body.local .summary{font-size:13px}
}
@media(prefers-color-scheme:dark){
  body.local .pill.active,body.local .pill.on,body.local .pill.pick.active,
  body.local .trend .tbtn.on,body.local .pill.th.active,body.local .pill.src.th.active{color:#15201d}
}
html[data-theme="dark"] body.public,html[data-theme="dark"] body.local{
  color-scheme:dark;--bg:#131417;--panel:#1b1d21;--panel2:#25272c;
  --text:#ececeb;--muted:#b9bcc0;--line:#2c2f34;--line2:#3b3f46;
  --accent:#e0776c;--thai:#d8ab5c;--hot:#d8ab5c;--official:#6fbf95;--warn:#d8ab5c}
html[data-theme="dark"] body.public .pill.active,html[data-theme="dark"] body.public .pill.on,
html[data-theme="dark"] body.public .pill.pick.active,html[data-theme="dark"] body.public .trend .tbtn.on,
html[data-theme="dark"] body.public .pill.th.active,html[data-theme="dark"] body.public .pill.src.th.active,
html[data-theme="dark"] body.local .pill.active,html[data-theme="dark"] body.local .pill.on,
html[data-theme="dark"] body.local .pill.pick.active,html[data-theme="dark"] body.local .trend .tbtn.on,
html[data-theme="dark"] body.local .pill.th.active,html[data-theme="dark"] body.local .pill.src.th.active{color:#17181a}
html[data-theme="light"] body.public,html[data-theme="light"] body.local{
  color-scheme:light;--bg:#fbfaf7;--panel:#fff;--panel2:#f4f0e9;
  --text:#17181a;--muted:#454a50;--line:#e3ded4;--line2:#cec7b9;
  --accent:#a02c22;--thai:#8a5a12;--hot:#8a5a12;--official:#1f6b46;--warn:#8a5a12}
html[data-theme="dark"] body.public .bar,html[data-theme="dark"] body.local .bar,
html[data-theme="light"] body.public .bar,html[data-theme="light"] body.local .bar{
  background:var(--bg);color:var(--text);backdrop-filter:none}
html[data-theme="light"] body.public .pill.active,html[data-theme="light"] body.public .pill.on,
html[data-theme="light"] body.public .pill.pick.active,html[data-theme="light"] body.public .trend .tbtn.on,
html[data-theme="light"] body.local .pill.active,html[data-theme="light"] body.local .pill.on,
html[data-theme="light"] body.local .pill.pick.active,html[data-theme="light"] body.local .trend .tbtn.on{
  background:color-mix(in srgb,var(--accent) 8%,var(--panel));border-color:var(--accent);color:var(--accent)}
html[data-theme="light"] body.public .pill.pick.active,html[data-theme="light"] body.local .pill.pick.active{
  background:color-mix(in srgb,var(--official) 8%,var(--panel));border-color:var(--official);color:var(--official)}
html[data-theme="light"] body.public .pill.th.active,html[data-theme="light"] body.public .pill.src.th.active,
html[data-theme="light"] body.local .pill.th.active,html[data-theme="light"] body.local .pill.src.th.active{
  background:color-mix(in srgb,var(--thai) 8%,var(--panel));border-color:var(--thai);color:var(--thai)}
html[data-theme="light"] body.public .trend .tbtn.on .n,html[data-theme="light"] body.local .trend .tbtn.on .n{
  color:var(--muted);opacity:1}
html[data-theme="light"] body.public .conds .cbtn:not(.kw),html[data-theme="light"] body.local .conds .cbtn:not(.kw){
  background:var(--panel2);border-color:var(--line2);color:var(--text)}
html[data-theme="light"] body.public .conds .cbtn:not(.kw) .n,
html[data-theme="light"] body.local .conds .cbtn:not(.kw) .n{color:var(--muted);opacity:1}
html[data-theme="light"] body.public .newpill[data-show="1"],html[data-theme="light"] body.local .newpill[data-show="1"]{
  background:var(--panel2);border-color:var(--accent);color:var(--accent)}
/* A short editor's desk briefing, then the full feed as a time-led newsroom timeline. */
.briefing{margin:30px 0 28px}
.briefing[hidden],body.tab-cal .briefing{display:none!important}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:14px;flex-wrap:wrap;
  padding-bottom:8px;border-bottom:1px solid var(--text)}
.sec-head h2{margin:0;font:700 17px/1.4 var(--serif);letter-spacing:-.01em;color:var(--text)}
.sec-note{margin:0 0 0 auto;color:var(--muted);font:11.5px/1.5 var(--mono)}
.brief-list{list-style:none;margin:0;padding:0}
.brief{display:grid;grid-template-columns:72px minmax(0,1fr);gap:14px;padding:18px 0 20px;border-bottom:1px solid var(--line)}
.brief .bnum{font:600 26px/1.2 var(--serif);color:var(--line2);font-variant-numeric:tabular-nums}
.brief.picked .bnum{color:var(--accent)}
.brief .btitle{margin:0;font:600 19px/1.45 var(--serif);letter-spacing:-.015em;overflow-wrap:anywhere}
.brief .btitle a:hover{color:var(--accent)}
.brief .bsum{margin:6px 0 0;color:var(--muted);font-size:13px;line-height:1.65;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.brief .bnote{margin:7px 0 0;padding-left:12px;border-left:2px solid var(--accent);color:var(--muted);font-size:12px}
.brief .bmeta{display:flex;flex-wrap:wrap;gap:5px 10px;margin:8px 0 0;color:var(--muted);font:11px/1.5 var(--mono)}
.brief .tag-pick{color:var(--official)}
.bucket{margin-top:22px}
.bucket-h{display:flex;justify-content:space-between;gap:12px;margin:0 0 0;padding:0 0 6px;border-bottom:1px solid var(--text);
  color:var(--muted);font:11.5px/1.5 var(--mono)}
body.public .timeline-row,body.local .timeline-row{display:grid;grid-template-columns:72px 14px minmax(0,1fr);gap:0;position:relative;
  min-width:0;padding:17px 0 19px;border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent;box-shadow:none}
body.public .timeline-row .t,body.local .timeline-row .t{grid-column:1;grid-row:1;margin:2px 12px 0 0;text-align:right;color:var(--muted);font:11.5px/1.5 var(--mono);font-variant-numeric:tabular-nums}
body.public .timeline-row .timeline-dot,body.local .timeline-row .timeline-dot{grid-column:2;grid-row:1;position:relative;min-height:100%;}
body.public .timeline-row .timeline-dot::before,body.local .timeline-row .timeline-dot::before{content:"";position:absolute;left:50%;top:-17px;bottom:-20px;width:1px;background:var(--line2)}
body.public .timeline-row.first-in-day .timeline-dot::before,body.local .timeline-row.first-in-day .timeline-dot::before{top:6px}
body.public .timeline-row.last-in-day .timeline-dot::before,body.local .timeline-row.last-in-day .timeline-dot::before{bottom:6px}
body.public .timeline-row .timeline-dot::after,body.local .timeline-row .timeline-dot::after{content:"";position:absolute;left:50%;top:5px;width:7px;height:7px;transform:translateX(-50%);
  border:1px solid var(--line2);border-radius:50%;background:var(--bg)}
body.public .timeline-row .body,body.local .timeline-row .body{grid-column:3;grid-row:1;min-width:0}
body.public .timeline-row .meta,body.local .timeline-row .meta{display:flex;align-items:center;flex-wrap:wrap;gap:5px 9px;margin:0 0 5px;color:var(--muted);font:11.5px/1.5 var(--mono)}
body.public .timeline-row .meta .chip,body.local .timeline-row .meta .chip{font:inherit}
body.public .timeline-row .title,body.local .timeline-row .title{margin:0;font:600 20px/1.48 var(--serif);letter-spacing:-.015em;overflow-wrap:anywhere}
body.public .timeline-row .summary,body.local .timeline-row .summary{margin:7px 0 0;color:var(--muted);font-size:14px;line-height:1.7;overflow-wrap:anywhere}
body.public .timeline-row .summary.clamp,body.local .timeline-row .summary.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
body.public .timeline-row .expand,body.local .timeline-row .expand{display:inline-block;margin:5px 12px 0 0;padding:0;font-size:12px}
body.public .timeline-row .acts,body.local .timeline-row .acts{display:flex;flex-wrap:wrap;gap:8px 12px;margin:6px 0 0;align-items:center}
body.public .timeline-row .acts .open,body.local .timeline-row .acts .open,body.local .timeline-row .acts .hide{font-size:12px}
body.public .timeline-row .pickbadge,body.local .timeline-row .pickbadge{margin:0 0 5px}
body.public .timeline-row:hover,body.local .timeline-row:hover{background:transparent}
@media(max-width:767px){
  .briefing{margin:24px 0}
  .brief{grid-template-columns:36px minmax(0,1fr);gap:10px;padding:15px 0 17px}
  .brief .bnum{font-size:22px}
  .brief .btitle{font-size:17px;line-height:1.5}
  .brief .bsum{font-size:12px}
  .brief .bmeta{font-size:10.5px}
  .bucket{margin-top:18px}
  body.public .timeline-row,body.local .timeline-row{grid-template-columns:52px 12px minmax(0,1fr);padding:15px 0 17px}
  body.public .timeline-row .t,body.local .timeline-row .t{margin-right:8px;font-size:10.5px}
  body.public .timeline-row .meta,body.local .timeline-row .meta{font-size:10.5px;gap:4px 7px}
  body.public .timeline-row .title,body.local .timeline-row .title{font-size:18px;line-height:1.48}
  body.public .timeline-row .summary,body.local .timeline-row .summary{font-size:13px;line-height:1.65}
}
.foot .legal-links{margin:14px 0 0;font-size:12px}
.foot .legal-links a{color:var(--muted);text-decoration:underline;text-underline-offset:3px}
.timeline-row .title,.brief .btitle{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;text-overflow:ellipsis;overflow-wrap:normal;word-break:normal}
/* Do not split ordinary words at the edge of the three-line preview. Keep the full
   headline in the DOM for links, readers and indexing; break only unspaced URLs. */
body.public .timeline-row .title,body.local .timeline-row .title{overflow-wrap:break-word;word-break:normal}
"""

NEWS_THEME_SCRIPT = """\
(function(){
  var root=document.documentElement,button=document.getElementById('theme-toggle');
  if(!button)return;
  var labels={ko:{dark:'다크 모드 켜기',light:'다크 모드 끄기'},en:{dark:'Enable dark mode',light:'Disable dark mode'},
    th:{dark:'เปิดโหมดมืด',light:'ปิดโหมดมืด'}};
  var words=labels[root.lang]||labels.ko;
  function mode(){
    if(root.dataset.theme==='dark'||root.dataset.theme==='light')return root.dataset.theme;
    return 'light';
  }
  function update(){
    var dark=mode()==='dark';
    button.textContent=dark?words.light:words.dark;
    button.setAttribute('aria-label',dark?words.light:words.dark);
    button.setAttribute('aria-pressed',String(dark));
  }
  button.addEventListener('click',function(){
    var next=mode()==='dark'?'light':'dark';
    root.dataset.theme=next;
    try{localStorage.setItem('tbn-theme',next)}catch(e){}
    update();
  });
  update();
})();
"""
DASHBOARD_THEME_BOOTSTRAP = "<script>(function(){try{var t=localStorage.getItem('tbn-theme');document.documentElement.dataset.theme=t==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='light'}})();</script>"
