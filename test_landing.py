"""Homepage contract: platform-neutral, market-first navigation."""
import unittest
from html.parser import HTMLParser
import landing
import landing_thai

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
    def test_market_first_and_platform_neutral(self):
        parser=Text(); parser.feed(landing.render_landing()); text=' '.join(parser.parts)
        self.assertIn('트레이딩을 위한', text)
        self.assertIn('경제 뉴스와 시장 관점', text)
        self.assertNotIn('서브스택', text)
        self.assertIn('무료 공개', text)
        self.assertIn('태국 소식', text)

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
        self.assertIn('.news-list{display:block;width:auto;animation:none;overflow:visible}', page)
        self.assertIn('트레이딩을 위한</i></span> <span', page)
        self.assertIn('--bg:#fbfaf7', page)
        self.assertIn('--accent:#a02c22', page)
        self.assertIn('--serif:', page)
        self.assertIn('font-family:var(--serif)', page)
        self.assertIn('<span class="brand-accent">티모</span> <span class="brand-rest">라이브뉴스</span>', page)
        self.assertIn('id="theme-toggle"', page)
        self.assertIn("root.dataset.theme=dark?'dark':'light'", page)
        self.assertIn('color-scheme:dark', page)

    def test_tradingview_invite_is_explicit_and_external(self):
        page = landing.render_landing()
        footer = page.split('<footer class="footer">', 1)[1].split('</footer>', 1)[0]
        self.assertIn('https://t.me/+OegpDrwxnaBiOGNl', footer)
        self.assertIn('트레이딩뷰 TeemoBKK 텔레그램 대화방 초대 링크', page)
        self.assertIn('href="https://t.me/+OegpDrwxnaBiOGNl" target="_blank" rel="noopener noreferrer"', page)
        self.assertIn('외부 대화방으로 이동합니다', page)
        self.assertIn('트레이딩뷰 TeemoBKK 공식 프로필', page)
        self.assertEqual(page.count('https://t.me/+OegpDrwxnaBiOGNl'), 1)

    def test_mobile_motion_and_thai_identity(self):
        home = landing.render_landing()
        thai = landing_thai.render_thai_landing()
        for page in (home, thai):
            self.assertIn('@media(max-width:767px){\n  .hero .eyebrow', page)
            self.assertIn('.marq{display:none}', page)
            self.assertIn('.pointer-light{display:none}', page)
            self.assertIn('.news-list{display:block;width:auto;animation:none;overflow:visible}', page)
            self.assertIn('<span class="brand-accent">티모</span> <span class="brand-rest">라이브뉴스</span>', page)
            self.assertIn('id="theme-toggle"', page)
            self.assertNotIn('animation:rail 42s', page)
            self.assertNotIn('@keyframes rail', page)
        self.assertIn('href="/thai/news/ko/"', thai)
        self.assertIn('href="/thai/news/"', thai)
        self.assertIn('<meta name="theme-color" content="#131417">', thai)
        self.assertIn("t==='light'?'light':'dark'", thai)
        self.assertIn("document.documentElement.dataset.theme='dark'", thai)
        self.assertIn('태국 소식 · TeemoBKK', thai)

if __name__=='__main__': unittest.main()
