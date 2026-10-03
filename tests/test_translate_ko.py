import json
import os
import sqlite3
import sys
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_news_dashboard as core
import page_build
import econ_calendar
from deploy import collect_public
from tools import backfill_translations
import translate_ko


class TranslateOne(unittest.TestCase):
    def test_codex_adapter_imports_from_repository_root(self):
        from deploy import tg_push

        self.assertTrue(callable(tg_push.codex_complete_translation))

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

    def test_explicit_codex_provider_never_uses_api_fallback(self):
        with patch.dict(os.environ, {"TG_TRANSLATE_PROVIDER": "openai-codex"}):
            with patch.object(translate_ko, "_complete_with_codex", side_effect=RuntimeError("rate limited")) as codex:
                with patch.object(translate_ko, "_complete_with_api") as api:
                    with self.assertRaisesRegex(RuntimeError, "rate limited"):
                        translate_ko.translate_one("Original", "Summary")
        codex.assert_called_once()
        api.assert_not_called()

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


class CalendarNameTranslation(unittest.TestCase):
    def setUp(self):
        self.old_cache = econ_calendar._NAME_TRANSLATION_CACHE.copy()
        econ_calendar._NAME_TRANSLATION_CACHE.clear()

    def tearDown(self):
        econ_calendar._NAME_TRANSLATION_CACHE.clear()
        econ_calendar._NAME_TRANSLATION_CACHE.update(self.old_cache)

    def _completed(self, output, returncode=0):
        return subprocess.CompletedProcess([], returncode, stdout=output, stderr="")

    def test_codex_runs_in_isolated_read_only_subscription_subprocess(self):
        name = "Federal Reserve Interest Rate Decision"
        output = json.dumps({"translations": [{"id": "event-0", "name_ko": "연준 금리 결정"}]}, ensure_ascii=False)
        with patch.object(econ_calendar.subprocess, "run", return_value=self._completed(output)) as run:
            self.assertEqual(econ_calendar.translate_event_names([name]), {name: "연준 금리 결정"})

        command = run.call_args.args[0]
        options = run.call_args.kwargs
        self.assertEqual(command[0], "/usr/local/bin/codex")
        self.assertEqual(command[1], "exec")
        self.assertIn("gpt-6-luna", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--sandbox", command)
        self.assertIn("read-only", command)
        self.assertIn("--ask-for-approval", command)
        self.assertIn("never", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertEqual(command[-1], "-")
        self.assertFalse(options["shell"])
        self.assertTrue(options["capture_output"])
        self.assertEqual(options["timeout"], econ_calendar.CODEX_TIMEOUT_SECONDS)
        self.assertTrue(os.path.basename(options["cwd"]).startswith("teemo-econ-calendar-codex-"))
        self.assertNotEqual(os.path.realpath(options["cwd"]), os.path.realpath(Path(__file__).resolve().parents[1]))
        self.assertIn('"name": "Federal Reserve Interest Rate Decision"', options["input"])

    def test_timeout_leaves_translation_empty(self):
        name = "Consumer Price Index"
        with patch.object(econ_calendar.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 45)):
            self.assertEqual(econ_calendar.translate_event_names([name]), {name: ""})

    def test_unavailable_codex_executable_leaves_translation_empty(self):
        name = "Consumer Price Index"
        with patch.object(econ_calendar.subprocess, "run", side_effect=FileNotFoundError("codex")):
            self.assertEqual(econ_calendar.translate_event_names([name]), {name: ""})

    def test_nonzero_exit_and_malformed_json_leave_translation_empty(self):
        name = "Consumer Price Index"
        valid = json.dumps({"translations": [{"id": "event-0", "name_ko": "소비자물가지수"}]}, ensure_ascii=False)
        with patch.object(econ_calendar.subprocess, "run", return_value=self._completed(valid, returncode=1)):
            self.assertEqual(econ_calendar.translate_event_names([name]), {name: ""})
        econ_calendar._NAME_TRANSLATION_CACHE.clear()
        with patch.object(econ_calendar.subprocess, "run", return_value=self._completed("not JSON")):
            self.assertEqual(econ_calendar.translate_event_names([name]), {name: ""})

    def test_missing_or_empty_translated_title_stays_blank(self):
        names = ["Consumer Price Index", "Federal Reserve Decision"]
        output = json.dumps({"translations": [
            {"id": "event-0", "name_ko": "  "},
            {"id": "event-99", "name_ko": "무시할 번역"},
        ]}, ensure_ascii=False)
        with patch.object(econ_calendar.subprocess, "run", return_value=self._completed(output)):
            self.assertEqual(econ_calendar.translate_event_names(names), {name: "" for name in names})

    def _source_patches(self, rows=None):
        if rows is None:
            rows = [{
                "gmt": "08:30", "eventName": "Nonfarm Payrolls", "country": "United States",
                "actual": "", "consensus": "", "previous": "",
            }]
        return (
            patch.object(econ_calendar, "fetch_day", return_value=rows),
            patch.object(econ_calendar, "fetch_earnings", return_value=[]),
            patch.object(econ_calendar.potus_schedule, "fetch", return_value=[]),
            patch.object(econ_calendar, "fed_funds_range", return_value=""),
        )

    def test_scheduled_write_persists_name_ko(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = os.path.join(directory, "calendar.json")
            patches = self._source_patches()
            with patches[0], patches[1], patches[2], patches[3], \
                 patch.object(econ_calendar, "translate_event_names", return_value={"Nonfarm Payrolls": "고용 보고서"}):
                self.assertGreater(econ_calendar.write(output_path), 0)
            with open(output_path, encoding="utf-8") as handle:
                payload = json.load(handle)
        events = [event for day in payload["days"] for event in day["events"]]
        self.assertTrue(events)
        self.assertTrue(all(event["name_ko"] == "고용 보고서" for event in events))

    def test_translation_exception_does_not_break_collect_and_saves_empty_names(self):
        patches = self._source_patches()
        with patches[0], patches[1], patches[2], patches[3], \
             patch.object(econ_calendar, "translate_event_names", side_effect=RuntimeError("offline")):
            payload = econ_calendar.collect(
                econ_calendar.datetime(2026, 10, 3, 12, tzinfo=econ_calendar.timezone.utc))
        events = [event for day in payload["days"] for event in day["events"]]
        self.assertTrue(events)
        self.assertTrue(all(event["name_ko"] == "" for event in events))

    def test_collect_collapses_case_and_ampersand_release_label_variants(self):
        rows = [
            {"gmt": "08:30", "eventName": "CPI Tokyo Ex Food & Energy", "country": "Japan",
             "actual": "", "consensus": "", "previous": ""},
            {"gmt": "08:30", "eventName": "cpi tokyo ex food and energy", "country": "Japan",
             "actual": "", "consensus": "", "previous": ""},
        ]
        patches = self._source_patches(rows)
        with patches[0], patches[1], patches[2], patches[3], \
             patch.object(econ_calendar, "translate_event_names", return_value={}):
            payload = econ_calendar.collect(
                econ_calendar.datetime(2026, 10, 3, 12, tzinfo=econ_calendar.timezone.utc))
        events = [event for day in payload["days"] for event in day["events"]
                  if event["country"] == "Japan" and "tokyo" in event["name"].casefold()]
        keys = [(event["date"], event["kst"], event["country"]) for event in events]
        self.assertEqual(len(events), 3)
        self.assertEqual(len(keys), len(set(keys)))


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


class BackfillSafety(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tempdir.name, "news.db")
        self.original_db_file = core.DB_FILE
        core.DB_FILE = self.path
        self.links = [
            "https://example.test/oldest",
            "https://example.test/middle",
            "https://example.test/newest",
        ]
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE TABLE articles (link TEXT PRIMARY KEY, title TEXT, summary TEXT, "
                "title_ko TEXT, summary_ko TEXT, published_at TEXT, collected_at TEXT)"
            )
            connection.executemany(
                "INSERT INTO articles (link, title, summary, published_at, collected_at) VALUES (?, ?, ?, ?, ?)",
                [
                    (link, f"Title {index}", f"Summary {index}", published_at, published_at)
                    for link, index, published_at in zip(
                        self.links,
                        range(3),
                        ["2026-09-30T00:00:00+00:00", "2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00"],
                    )
                ],
            )
            connection.commit()

    def tearDown(self):
        core.DB_FILE = self.original_db_file
        self.tempdir.cleanup()

    def test_codex_failure_aborts_backfill_batch_without_api_fallback(self):
        with patch.dict(os.environ, {"TG_TRANSLATE_PROVIDER": "openai-codex"}):
            with patch.object(translate_ko, "_complete_with_codex", side_effect=RuntimeError("codex down")) as codex:
                with patch.object(translate_ko, "_complete_with_api") as api:
                    with self.assertRaisesRegex(RuntimeError, "codex down"):
                        translate_ko.translate_pending(limit=5, throttle_seconds=0)
        codex.assert_called_once()
        api.assert_not_called()

    def test_cli_uses_explicit_database_and_forces_codex_provider(self):
        batches = []

        def translate_selected(links, limit, throttle_seconds):
            self.assertEqual(os.environ.get("TG_TRANSLATE_PROVIDER"), "openai-codex")
            self.assertEqual(core.DB_FILE, self.path)
            self.assertEqual(limit, len(links))
            self.assertEqual(throttle_seconds, 0)
            batches.append(links)
            with closing(sqlite3.connect(self.path)) as connection:
                connection.executemany(
                    "UPDATE articles SET title_ko = ?, summary_ko = ? WHERE link = ?",
                    [("제목", "요약", link) for link in links],
                )
                connection.commit()
            return len(links)

        with patch.dict(os.environ, {"TG_TRANSLATE_PROVIDER": "openai"}):
            with patch.object(sys, "argv", [
                "backfill_translations.py", "--db", self.path, "--batch-size", "2",
                "--max-rows", "2", "--throttle", "0",
            ]):
                with patch.object(translate_ko, "translate_pending", side_effect=translate_selected):
                    result = backfill_translations.main()

        self.assertEqual(result, 0)
        self.assertEqual(batches, [list(reversed(self.links))[:2]])
        self.assertEqual([link for _, link in backfill_translations.pending_batch(3)], self.links[:1])

    def test_backfill_ignores_articles_without_source_text(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "INSERT INTO articles (link, title, summary, published_at, collected_at) VALUES (?, ?, ?, ?, ?)",
                ("https://example.test/empty", "", "", "2026-09-01T00:00:00+00:00", "2026-09-01T00:00:00+00:00"),
            )
            connection.commit()
        self.assertEqual(backfill_translations.pending_count(), 3)
        self.assertEqual(len(backfill_translations.pending_batch(10)), 3)

    def test_ingest_default_translates_newest_article_first(self):
        with patch.dict(os.environ, {"TG_TRANSLATE_PROVIDER": "openai-codex"}):
            with patch.object(translate_ko, "_complete_with_codex", return_value='{"title":"최신 제목","summary":"최신 요약"}') as codex:
                count = translate_ko.translate_pending(limit=1, throttle_seconds=0)
        self.assertEqual(count, 1)
        codex.assert_called_once()
        with closing(sqlite3.connect(self.path)) as connection:
            translated = connection.execute("SELECT link FROM articles WHERE title_ko IS NOT NULL").fetchall()
        self.assertEqual([row[0] for row in translated], [self.links[-1]])

    def test_backfill_batches_newest_incomplete_articles_first(self):
        first = backfill_translations.pending_batch(2)
        newest_first = list(reversed(self.links))
        self.assertEqual([link for _, link in first], newest_first[:2])
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executemany(
                "UPDATE articles SET title_ko = ?, summary_ko = ? WHERE link = ?",
                [("제목", "요약", link) for link in newest_first[:2]],
            )
            connection.commit()
        second = backfill_translations.pending_batch(2)
        self.assertEqual([link for _, link in second], self.links[:1])

    def test_backfill_translates_selected_links_newest_first(self):
        translated_titles = []

        def translate(title, summary):
            translated_titles.append(title)
            return '{"title":"한국어 제목","summary":"한국어 요약"}'

        with patch.dict(os.environ, {"TG_TRANSLATE_PROVIDER": "openai-codex"}):
            with patch.object(translate_ko, "_complete_with_codex", side_effect=translate):
                count = translate_ko.translate_pending(
                    limit=3, links=self.links, throttle_seconds=0
                )

        self.assertEqual(count, 3)
        self.assertEqual(translated_titles, ["Title 2", "Title 1", "Title 0"])

    def test_backfill_repairs_rows_with_either_translation_field_missing(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("UPDATE articles SET title_ko = ? WHERE link = ?", ("기존 제목", self.links[0]))
            connection.commit()
        with patch.dict(os.environ, {"TG_TRANSLATE_PROVIDER": "openai-codex"}):
            with patch.object(translate_ko, "_complete_with_codex", return_value='{"title":"새 제목","summary":"새 요약"}'):
                count = translate_ko.translate_pending(links=[self.links[0]], throttle_seconds=0)
        self.assertEqual(count, 1)
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT title_ko, summary_ko FROM articles WHERE link = ?", (self.links[0],)).fetchone()
        self.assertEqual(row, ("새 제목", "새 요약"))


if __name__ == "__main__":
    unittest.main()
