"""Iran and Middle East conflict stories survive Telegram topic filters."""
import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))

import jev_gate
import live_news_dashboard as core
import tg_push


class IranTelegramCoverage(unittest.TestCase):
    def setUp(self):
        self.old_filter = jev_gate.ALT_NOTICE_FILTER
        jev_gate.ALT_NOTICE_FILTER = True

    def tearDown(self):
        jev_gate.ALT_NOTICE_FILTER = self.old_filter

    def test_priority_four_iran_conflict_story_survives_altcoin_gate(self):
        item = {
            "title": "Iran conflict escalates as missile strikes hit the region",
            "summary": "Iranian officials report new strikes near Tehran",
            "asset": "SOL", "priority": 4, "category": "알트코인",
            "categories": ["알트코인"], "channel_pick": False,
        }
        self.assertFalse(jev_gate.is_single_alt_notice(item))

    def test_persian_gulf_and_houthi_story_survives_altcoin_gate(self):
        item = {
            "title": "후티 공격으로 홍해 긴장 고조, 페르시아만 원유 운송 우려",
            "summary": "중동 해상 안보 관련 소식", "asset": "XRP", "priority": 4,
            "category": "알트코인", "categories": ["알트코인"], "channel_pick": False,
        }
        self.assertFalse(jev_gate.is_single_alt_notice(item))

    def test_unrelated_routine_single_alt_notice_remains_blocked(self):
        item = {
            "title": "Solana exchange trading caution notice",
            "summary": "Routine individual asset notice", "asset": "SOL", "priority": 4,
            "category": "알트코인", "categories": ["알트코인"], "channel_pick": False,
        }
        self.assertTrue(jev_gate.is_single_alt_notice(item))

    def test_conflict_candidate_passes_deterministic_posting_gate(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        item = {
            "title": "Iranian missile strikes raise Middle East escalation risk",
            "summary": "",
            "link": "https://example.test/iran-story",
            "published_at": now.isoformat(),
            "asset": "SOL", "priority": 4, "category": "알트코인",
            "categories": ["알트코인"], "channel_pick": False,
        }
        self.assertEqual((True, ""), tg_push.worth_posting(item, now))


class AlJazeeraFeed(unittest.TestCase):
    def test_al_jazeera_is_registered_with_topic_gate(self):
        self.assertIn(("Al Jazeera · Middle East", "news",
                       "https://www.aljazeera.com/xml/rss/all.xml"), core.RSS_SOURCES)

    def test_topic_gate_keeps_mideast_and_drops_unrelated_stories(self):
        self.assertTrue(core.matches_middle_east_topic(
            "Iran warns after Israeli strikes near Tehran", "Regional escalation"))
        self.assertTrue(core.matches_middle_east_topic(
            "حرب إيران وإسرائيل تتصاعد", "Middle East conflict"))
        self.assertFalse(core.matches_middle_east_topic(
            "Global technology stocks rally", "Markets update"))

    def test_live_feed_parses_and_topic_subset_has_recent_items(self):
        payload = core.fetch_bytes("https://www.aljazeera.com/xml/rss/all.xml", timeout=15)
        rows = core.parse_rss(payload, "Al Jazeera · Middle East", "news", core.GLOBAL_REGION)
        relevant = [row for row in rows
                    if core.matches_middle_east_topic(row["title"], row["summary"])]
        self.assertTrue(rows, "공개 RSS에 항목이 없음")
        self.assertTrue(relevant, "최신 RSS 항목에서 주제 관련 기사를 찾지 못함")
        newest = max(row["published_at"] for row in relevant if row["published_at"])
        published = datetime.datetime.fromisoformat(newest.replace("Z", "+00:00"))
        age_hours = (datetime.datetime.now(datetime.timezone.utc) - published).total_seconds() / 3600
        self.assertGreaterEqual(age_hours, -1, "발행 시각이 비정상적으로 미래임")
        self.assertLess(age_hours, 48, "주제 관련 최신 기사가 48시간보다 오래됨")
        print("Al Jazeera RSS: %d parsed, %d topic-matched, newest relevant %.2fh ago" %
              (len(rows), len(relevant), age_hours))


if __name__ == "__main__":
    unittest.main(verbosity=2)
