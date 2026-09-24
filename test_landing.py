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

if __name__=='__main__': unittest.main()
