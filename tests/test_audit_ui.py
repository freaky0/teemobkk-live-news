"""Regression contracts for the public not-found page and headline/date UI."""
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import landing
import landing_thai
import page_build


class AuditUI(unittest.TestCase):
    def test_not_found_document_is_dark_accessible_and_unindexed(self):
        page = page_build.not_found_page()
        for fragment in ('<html lang="ko">', '<meta name="robots" content="noindex">',
                         '<h1>', 'href="/"', 'href="/news/ko/"', 'color-scheme:dark'):
            self.assertIn(fragment, page)

    def test_date_is_human_readable_without_changing_machine_date(self):
        self.assertEqual(landing.display_date('2026-09-30'), '2026년 9월 30일')
        with mock.patch.object(landing, 'editorial_posts', return_value=[{
                'date': '2026-09-30', 'title': '제목',
                'url': 'https://teemobkk.substack.com/p/example', 'summary': '요약'}]):
            page = landing.render_landing()
        self.assertIn('<time datetime="2026-09-30">2026년 9월 30일</time>', page)
        self.assertIn('다크 모드 켜기', page)
        self.assertIn('일반 모드 켜기', page)

    def test_headline_cleaners_remove_short_links_on_every_page(self):
        self.assertEqual(page_build._clean_title('시장 소식 reut.rs/abc - 매체'), '시장 소식')
        for page in (landing.render_landing(), landing_thai.render_thai_landing()):
            self.assertIn('cleanTitle(a.title)', page)
            self.assertIn('reut', page)
        self.assertIn('reut', page_build.SCRIPT)


if __name__ == '__main__':
    unittest.main()
