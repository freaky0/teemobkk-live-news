"""Regression contracts for the public not-found page and headline/date UI."""
import json
import re
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import landing
import landing_thai
import page_build
import category_rules


class AuditUI(unittest.TestCase):
    def test_trend_alias_matches_are_explicit_and_do_not_change_plain_search(self):
        for headline in ('Trump visits Bangkok', '트럼프 방문', 'ทรัมป์ เยือนกรุงเทพ'):
            self.assertTrue(category_rules.text_matches(headline, 'trend:trump'))
        for headline in ('Trumpet concert', '트럼펫 공연', 'Trumpism debated'):
            self.assertFalse(category_rules.text_matches(headline, 'trend:trump'))
        self.assertFalse(category_rules.text_matches('트럼프 방문', 'trump'))
        for headline in ('Bitcoin rallies', '비트코인 상승', 'บิตคอยน์พุ่ง'):
            self.assertTrue(category_rules.text_matches(headline, 'trend:bitcoin'))
        self.assertFalse(category_rules.text_matches('Bitcoiners gather', 'trend:bitcoin'))

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

    def test_korean_dates_agree_on_all_page_variants(self):
        for page in (landing.render_landing(), landing_thai.render_thai_landing()):
            self.assertIn('function displayStamp(value)', page)
        for lang in ('ko', 'en'):
            for thai in (False, True):
                page = page_build.render(public=True, datadir='', want_thai=thai,
                                         icon_prefix='', admin=False, lang=lang)
                self.assertIn('function sameBriefingEvent(', page)
                self.assertIn('aria-pressed="false"', page)
        self.assertEqual(page_build._ict_stamp('2026-10-01T03:04:00Z', 'ko'), '10월 1일 10:04')
        self.assertEqual(page_build._ict_stamp('2026-10-01T03:04:00Z', 'en'), 'Oct 1, 10:04')

    def test_headline_cleaners_remove_short_links_on_every_page(self):
        self.assertEqual(page_build._clean_title('시장 소식 reut.rs/abc - 매체'), '시장 소식')
        for page in (landing.render_landing(), landing_thai.render_thai_landing()):
            self.assertIn('cleanTitle(a.title)', page)
            self.assertIn('reut', page)
        self.assertIn('reut', page_build.SCRIPT)

    def test_headlines_keep_complete_words_and_full_accessible_text(self):
        title = 'Market participants discuss liquidity and the latest policy decision in Washington'
        item = {'title': title, 'link': 'https://example.com/story', 'source': 'Example',
                'published_at': '2026-09-30T12:00:00Z'}
        seed = page_build._seed_cards([item], False, 'en')
        self.assertIn(title, seed)
        self.assertIn('word-break:normal', page_build.CSS)
        self.assertIn('-webkit-line-clamp:3', page_build.CSS)
        self.assertIn('text-overflow:ellipsis', page_build.CSS)

    def test_no_speaker_or_star_rating_on_reader_cards_and_calendar(self):
        self.assertNotIn('speakChip(a)', page_build.SCRIPT)
        self.assertNotIn('stars(a)', page_build.SCRIPT)
        self.assertNotIn("join('*')", page_build.SCRIPT)
        self.assertNotIn('★4', page_build.SCRIPT)
        self.assertNotIn('★4', page_build.render(public=True, datadir='', want_thai=False,
                                                icon_prefix='', admin=False, lang='en'))

    def test_english_page_does_not_expose_korean_interface_literals(self):
        page = page_build.render(public=True, datadir='', want_thai=False,
                                 icon_prefix='', admin=False, lang='en')
        for text in ('그 이전', '최근 1시간', '선택한 조건을 모두', '요약 펼치기', '중요도 ★4'):
            self.assertNotIn(text, page)

    def test_seed_card_actions_use_the_requested_interface_language(self):
        item = {'title': 'Market update', 'summary': 'Summary ' * 40,
                'link': 'https://example.com/story', 'published_at': '2026-09-30T12:00:00Z'}
        english = page_build._seed_cards([item], False, 'en')
        korean = page_build._seed_cards([item], False, 'ko')
        self.assertIn('>Open original ↗</a>', english)
        self.assertIn('>Show more</button>', english)
        self.assertNotIn('원문 열기', english)
        self.assertNotIn('요약 펼치기', english)
        self.assertIn('>원문 열기 ↗</a>', korean)

    def test_trend_terms_are_identical_across_interface_languages_and_regions(self):
        for thai in (False, True):
            pages = [page_build.render(public=True, datadir='', want_thai=thai,
                                       icon_prefix='', admin=False, lang=lang)
                     for lang in ('en', 'ko')]
            for key in ('T_STOP', 'T_SKIP'):
                lines = [next(line for line in page.splitlines() if line.startswith('const ' + key + '='))
                         for page in pages]
                self.assertEqual(*lines)
            match = re.search(r'const T_STOP=new Set\((\[.*?\])\)', pages[0])
            self.assertIsNotNone(match)
            words = json.loads(match.group(1)) if match else []
            self.assertIn('오늘', words)
            self.assertIn('the', words)


if __name__ == '__main__':
    unittest.main()
