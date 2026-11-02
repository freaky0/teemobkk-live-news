"""Homepage contract: platform-neutral, market-first navigation."""
import unittest
from html.parser import HTMLParser
from pathlib import Path
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from pages.build import landing
from pages.build import landing_thai
from pages.build import page_build

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.ignore=0
    def handle_starttag(self, tag, attrs):
        if tag in ('style','script'): self.ignore+=1
    def handle_endtag(self, tag):
        if tag in ('style','script'): self.ignore-=1
    def handle_data(self, data):
        if not self.ignore: self.parts.append(data)

class LandingContract(unittest.TestCase):
    def test_homepage_hero_cta_opens_korean_market_news(self):
        page = landing.render_landing()
        cta = '<a class="button primary" href="/news/ko/">오늘의 시장 보기</a>'
        self.assertEqual(page.count(cta), 1)
        self.assertRegex(page, r'<h1 id="headline">.*차트보다 먼저.*읽는 뉴스.*</h1>')
        self.assertIn('시장이 움직인 이유를 설명하고', page)

    def test_thai_mobile_economy_link_targets_korean_market_news(self):
        page = landing_thai.render_thai_landing()
        self.assertIn('<a class="secondary" href="/news/ko/">경제 뉴스 ↗</a>', page)
        self.assertIn('.nav nav a.secondary{display:inline-flex}', page)

    def test_market_first_and_platform_neutral(self):
        page = landing.render_landing()
        parser=Text(); parser.feed(page); text=' '.join(parser.parts)
        self.assertIn('시장이 움직인 이유를 설명하고', text)
        self.assertIn('최근 경제 뉴스', text)
        self.assertIn('시장 관점', text)
        self.assertNotIn('서브스택', text)
        self.assertIn('무료 공개', text)
        self.assertIn('태국 뉴스', text)
        self.assertIn('href="/thai/"', page)

    def test_thai_category_filters_render_cached_results_immediately(self):
        page = landing_thai.render_thai_landing()
        self.assertIn('let busy = false, hasNews = false, activeCat = "", latestArticles = [];', page)
        self.assertIn('latestArticles = data.articles;', page)
        self.assertIn('activeCat = btn.dataset.cat || "";\n    render(selectNews(latestArticles));', page)
        self.assertNotIn('activeCat = btn.dataset.cat || "";\n    refresh();', page)

    def test_thai_hero_does_not_expand_the_document_width(self):
        page = landing_thai.render_thai_landing()
        self.assertIn('.hero{position:relative;margin:0;padding:0;', page)
        self.assertIn('.wrap{padding-inline:28px}.hero{margin:0}', page)
        self.assertNotIn('margin:0 -28px', page)

    def test_privacy_policy_is_linked_from_both_landing_pages(self):
        homepage = landing.render_landing()
        thai = landing_thai.render_thai_landing()
        for page in (homepage, thai):
            self.assertIn('href="/privacy/"', page)
            self.assertIn('개인정보 처리방침', page)

    def test_the_homepage_keeps_news_readable_on_phones(self):
        page = landing.render_landing()
        self.assertNotIn('class="marq"', page)
        self.assertNotIn('class="pointer-light"', page)
        self.assertIn('@media(max-width:767px)', page)
        self.assertIn('.hero{grid-template-columns:1fr', page)
        self.assertIn('.news-strip{position:relative;margin:26px 0 0;height:160px', page)
        self.assertIn('.news-strip{height:120px', page)
        self.assertIn('--bg:#f0f0ee', page)
        self.assertIn('--accent:#0f7a52', page)
        self.assertIn('<meta name="color-scheme" content="light dark">', page)
        self.assertIn('id="landing-theme-toggle"', page)
        self.assertIn('다크 모드로 전환', page)
        self.assertIn('localStorage.setItem("tbn-theme",t)', page)
        self.assertIn('color-mix(in srgb,var(--bg) 94%,transparent)', page)
        self.assertIn('@media(prefers-reduced-motion:reduce)', page)
        self.assertIn('src="/assets/landing/hero-editorial.webp"', page)
        self.assertIn('src="/assets/landing/news-editorial.webp"', page)

    def test_market_ticker_is_live_accessible_and_limited_to_supported_symbols(self):
        page = landing.render_landing()
        ticker_js = (Path(__file__).resolve().parents[1] / "assets/landing/mexc-ticker.js").read_text(encoding="utf-8")
        runtime = page + ticker_js
        self.assertIn('<link rel="stylesheet" href="/assets/landing/mexc-ticker.css">', page)
        self.assertIn('<script src="/assets/landing/mexc-ticker.js" defer></script>', page)
        self.assertLess(page.index('id="ticker"'), page.index('<header class="top">'))
        self.assertIn('wss://wbs-api.mexc.com/ws', runtime)
        self.assertIn('spot@public.miniTicker.v3.api.pb@', runtime)
        self.assertIn("socket.binaryType='arraybuffer'", runtime)
        for symbol in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT',
                       'BNBUSDT', 'DOGEUSDT', 'ADAUSDT', 'LINKUSDT'):
            self.assertIn(symbol, runtime)
        self.assertNotIn('api.binance.com', runtime)
        self.assertIn("setState('stale'", ticker_js)
        self.assertIn("setState('reconnecting'", ticker_js)
        self.assertIn('<ol class="kinetic-flow">', page)
        self.assertNotIn('kinetic-toggle', page)
        self.assertNotIn('kinetic-status', page)
        self.assertNotIn('애니메이션 재생 중', page)
        self.assertIn('@media(prefers-reduced-motion:no-preference)', page)
        self.assertIn('@media(prefers-reduced-motion:reduce)', page)

    def test_tradingview_invite_is_removed_but_official_profile_remains(self):
        page = landing.render_landing()
        footer = page.split('<footer class="footer">', 1)[1].split('</footer>', 1)[0]
        self.assertNotIn('https://t.me/', footer)
        self.assertNotIn('텔레그램 대화방 초대 링크', page)
        self.assertNotIn('외부 대화방으로 이동합니다', page)
        self.assertIn('트레이딩뷰 TeemoBKK 공식 프로필', page)

    def test_telegram_chat_links_are_absent_from_each_rendered_footer(self):
        invite = 'https://t.me/+OegpDrwxnaBiOGNl'
        pages = {'/': landing.render_landing(), '/thai/': landing_thai.render_thai_landing()}
        for region in ('/news/', '/thai/news/'):
            for lang in ('en', 'ko'):
                route = region + ('ko/' if lang == 'ko' else '')
                pages[route] = page_build.render(public=False, datadir='',
                    want_thai=region == '/thai/news/', icon_prefix='/', admin=False, lang=lang)
        pages['/admin/'] = page_build.render(public=False, datadir='',
            want_thai=False, icon_prefix='/', admin=True, lang='ko')
        for route, name in (('/privacy/', 'privacy.html'),
                            ('/privacy/en/', 'privacy_en.html')):
            pages[route] = (Path(__file__).resolve().parent.parent / 'pages' / 'static' / name).read_text(encoding='utf-8')
        for route, page in pages.items():
            with self.subTest(route=route):
                footer = page.split('<footer ', 1)[1].split('</footer>', 1)[0]
                self.assertNotIn(invite, footer)
                self.assertNotIn('t.me/', footer)
                self.assertNotRegex(footer, r'(?i)telegram|텔레그램')

    def test_mobile_motion_and_thai_identity(self):
        home = landing.render_landing()
        thai = landing_thai.render_thai_landing()
        for page in (home, thai):
            self.assertIn('@media(max-width:767px)', page)
            self.assertIn('@media(prefers-reduced-motion:reduce)', page)
        self.assertIn('.hero{grid-template-columns:1fr', home)
        self.assertIn('<html lang="ko">', thai)
        self.assertIn('<meta property="og:url" content="https://teemobkk.io/thai/">', thai)
        self.assertIn('TeemoBKK | 태국 소식을 한국어로', thai)

if __name__=='__main__': unittest.main()
