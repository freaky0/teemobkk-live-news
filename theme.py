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
            '</a><nav aria-label="주요 메뉴"><a href="/news/ko/">경제 뉴스</a><a href="#perspectives">시장 관점</a>'
            '<a href="#indicators">트레이딩뷰 지표</a><a href="/tradingtalk/">트레이딩 톡</a>'
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
