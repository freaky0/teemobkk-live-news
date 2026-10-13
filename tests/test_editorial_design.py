import unittest
from unittest.mock import patch
from pages.build import landing, theme, landing_thai


class EditorialDesignContract(unittest.TestCase):
    def test_home_has_peer_news_and_perspectives(self):
        with patch.object(landing, 'editorial_posts', return_value=[]):
            page = landing.render_landing()
        self.assertIn('<div class="main-sections"><section', page)
        self.assertIn('id="news"', page)
        self.assertIn('id="perspectives"', page)
        self.assertIn('grid-template-columns:1fr 1fr', page)
        for href in ('/news/ko/', '/perspectives/', '/blog/'):
            self.assertIn('href="' + href + '"', page)

    def test_perspectives_keep_author_date_and_original_link(self):
        page = landing.render_perspectives_page([dict(title='관점', date='2026-10-03', summary='해석', url='https://example.com/post')])
        self.assertIn('post-author">TeemoBKK', page)
        self.assertIn('datetime="2026-10-03"', page)
        self.assertIn('href="https://example.com/post"', page)
        self.assertIn('현재 표시할 관점 글이 없습니다', landing.render_perspectives_page([]))

    def test_thai_landing_keeps_its_own_theme(self):
        page = landing_thai.render_thai_landing()
        self.assertNotIn('WantedSansVariable', page)
        self.assertNotIn('--bg:#f5f5f4', page)


if __name__ == '__main__':
    unittest.main()
