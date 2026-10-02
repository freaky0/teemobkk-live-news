import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_news_dashboard as core
import page_build
from deploy import collect_public
import translate_ko


class TranslateOne(unittest.TestCase):
    def test_codex_subscription_is_tried_before_api_fallback(self):
        expected = {"title": "번역 제목", "summary": "번역 요약"}
        with patch.object(translate_ko, "_complete_with_codex", return_value='{"title":"번역 제목","summary":"번역 요약"}') as codex, \
             patch.object(translate_ko, "_complete_with_api") as api:
            self.assertEqual(translate_ko.translate_one("Original", "Summary"), expected)
        codex.assert_called_once()
        api.assert_not_called()

    def test_codex_failure_uses_api_fallback(self):
        expected = {"title": "번역 제목", "summary": "번역 요약"}
        with patch.object(translate_ko, "_complete_with_codex", side_effect=RuntimeError("rate limited")), \
             patch.object(translate_ko, "_complete_with_api", return_value='{"title":"번역 제목","summary":"번역 요약"}') as api:
            self.assertEqual(translate_ko.translate_one("Original", "Summary"), expected)
        api.assert_called_once()

    def test_korean_card_uses_translation_and_has_an_original_toggle(self):
        html = page_build._seed_cards([{
            "title": "Market rises 2%", "title_ko": "시장이 2% 상승",
            "summary": "Funds bought BTC.", "summary_ko": "펀드가 비트코인을 매수했다.",
            "link": "https://example.test/story", "published_at": "2026-10-02T01:00:00Z",
            "source": "Example", "source_type": "news", "category": "시장·가격",
        }], False, "ko")
        self.assertIn("시장이 2% 상승", html)
        self.assertIn("원문 보기", html)
        self.assertIn("Market rises 2%", html)
        self.assertIn("Funds bought BTC.", html)

    def test_korean_publisher_stamp_changes_when_translations_are_backfilled(self):
        original = [{"link": "https://example.test/story", "title_ko": None, "summary_ko": None}]
        translated = [{"link": "https://example.test/story", "title_ko": "번역 제목", "summary_ko": "번역 요약"}]
        self.assertNotEqual(collect_public.digest_of(original), collect_public.digest_of(translated))

    def test_empty_translation_of_a_nonempty_summary_uses_fallback(self):
        expected = {"title": "번역 제목", "summary": "번역 요약"}
        with patch.object(translate_ko, "_complete_with_codex", return_value='{"title":"번역 제목","summary":""}'):
            with patch.object(translate_ko, "_complete_with_api", return_value='{"title":"번역 제목","summary":"번역 요약"}') as api:
                self.assertEqual(translate_ko.translate_one("Original", "A nonempty summary"), expected)
        api.assert_called_once()

    def test_invalid_and_failed_translations_fail_open(self):
        with patch.object(translate_ko, "_complete_with_codex", side_effect=RuntimeError("offline")), \
             patch.object(translate_ko, "_complete_with_api", side_effect=RuntimeError("offline")):
            self.assertIsNone(translate_ko.translate_one("Original", "Summary"))
        with patch.object(translate_ko, "_complete_with_codex", return_value='not json'), \
             patch.object(translate_ko, "_complete_with_api", return_value='not json'):
            self.assertIsNone(translate_ko.translate_one("Original", "Summary"))


class PendingTranslations(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.previous_db = core.DB_FILE
        core.DB_FILE = self.path
        core.init_db()
        core.insert_articles([{
            "link": "https://example.test/story", "title": "Market rises 2%", "summary": "Funds bought BTC.",
            "source": "Example", "source_type": "news", "region": core.GLOBAL_REGION,
            "category": "시장·가격", "published_at": core.datetime.now(core.timezone.utc).isoformat(),
        }])

    def tearDown(self):
        core.DB_FILE = self.previous_db
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.path + suffix)
            except OSError:
                pass

    def test_pending_translation_persists_success_and_leaves_original(self):
        with patch.object(translate_ko, "translate_one", return_value={"title": "시장이 2% 상승", "summary": "펀드가 비트코인을 매수했다."}):
            self.assertEqual(translate_ko.translate_pending(limit=5), 1)
        connection = sqlite3.connect(self.path)
        try:
            row = connection.execute("SELECT title, summary, title_ko, summary_ko FROM articles").fetchone()
        finally:
            connection.close()
        self.assertEqual(row, ("Market rises 2%", "Funds bought BTC.", "시장이 2% 상승", "펀드가 비트코인을 매수했다."))

    def test_pending_translation_failure_does_not_raise_or_change_original(self):
        with patch.object(translate_ko, "translate_one", side_effect=RuntimeError("provider down")):
            self.assertEqual(translate_ko.translate_pending(limit=5), 0)
        connection = sqlite3.connect(self.path)
        try:
            row = connection.execute("SELECT title, title_ko FROM articles").fetchone()
        finally:
            connection.close()
        self.assertEqual(row, ("Market rises 2%", None))
    def test_init_db_adds_translation_columns_to_a_legacy_database(self):
        handle, legacy_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        previous_db = core.DB_FILE
        try:
            connection = sqlite3.connect(legacy_path)
            connection.execute(
                "CREATE TABLE articles (link TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, "
                "source TEXT, source_type TEXT, region TEXT, category TEXT, categories TEXT, asset TEXT, "
                "priority INTEGER, published_at TEXT NOT NULL, collected_at TEXT, original_source TEXT)"
            )
            connection.execute(
                "INSERT INTO articles (link,title,summary,published_at) VALUES (?,?,?,?)",
                ("https://example.test/legacy", "Legacy title", "Legacy summary",
                 core.datetime.now(core.timezone.utc).isoformat()))
            connection.commit()
            connection.close()
            core.DB_FILE = legacy_path
            core.init_db()
            connection = sqlite3.connect(legacy_path)
            try:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
                row = connection.execute("SELECT title,title_ko,summary_ko FROM articles").fetchone()
            finally:
                connection.close()
            self.assertTrue({"title_ko", "summary_ko"}.issubset(columns))
            self.assertEqual(row, ("Legacy title", None, None))
        finally:
            core.DB_FILE = previous_db
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(legacy_path + suffix)
                except OSError:
                    pass

    def test_collect_cycle_continues_when_translation_postprocessing_raises(self):
        from unittest.mock import patch

        with patch.object(core, "poll_plan", return_value=([], [])), \
             patch.object(core, "fetch_google_news", return_value=[]), \
             patch.object(core, "fetch_coinness", return_value=([], {"ok": True})), \
             patch.object(core, "fetch_coinness_stock", return_value=([], {"ok": True})), \
             patch.object(core.sbh_source, "fetch_into", return_value=[]), \
             patch.object(core.sbh_open_news, "fetch_into", return_value=[]), \
             patch.object(core.bluesky_source, "fetch_into", return_value=[]), \
             patch.object(core.whitehouse_source, "fetch_into", return_value=[]), \
             patch.object(core.telegram_source, "fetch_into", return_value=[]), \
             patch.object(translate_ko, "translate_pending", side_effect=RuntimeError("provider outage")):
            result = core.collect_news()
        self.assertIn("inserted_article_count", result)
        self.assertEqual(result["inserted_article_count"], 0)

    def test_korean_query_returns_translation_and_original_fallback(self):
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE articles SET title_ko = ?, summary_ko = ?",
                               ("시장이 2% 상승", "펀드가 비트코인을 매수했다."))
            connection.execute(
                "INSERT INTO articles (link,title,summary,source,source_type,region,category,priority,published_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                ("https://example.test/fallback", "Original fallback", "English summary", "Example", "news",
                 core.GLOBAL_REGION, "시장·가격", 3, core.datetime.now(core.timezone.utc).isoformat()))
        rows, total, _ = core.query_articles(hours=24, region=core.GLOBAL_REGION, lang="ko", limit=10)
        by_link = {row["link"]: row for row in rows}
        self.assertEqual(total, 2)
        self.assertEqual(by_link["https://example.test/story"]["title"], "시장이 2% 상승")
        self.assertEqual(by_link["https://example.test/story"]["original_title"], "Market rises 2%")
        self.assertEqual(by_link["https://example.test/fallback"]["title"], "Original fallback")


if __name__ == "__main__":
    unittest.main()
