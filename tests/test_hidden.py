"""Hiding a story: what it filters out, what it keeps, and how it comes back.

The distinction this file exists to hold: hiding is a filter on every read path, not a delete. The
row stays in the archive, so the same story cannot reappear through a different filter or after a
re-fetch, and a wrong click is undoable. Both halves are checked here - the row is gone from what a
reader sees, and still there in what the database holds.

    python tests/test_hidden.py
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import live_news_dashboard as core  # noqa: E402
import page_build  # noqa: E402

KEEP = "https://example.com/keep-me"
HIDE = "https://example.com/hide-me"


def article(link, title, region="글로벌", source="Example", published="2026-09-20T10:00:00+00:00"):
    return {"link": link, "title": title, "summary": "본문", "source": source,
            "source_type": "news", "region": region, "category": "시장·가격",
            "categories": ["시장·가격"], "priority": 3, "published_at": published,
            "collected_at": published}


class Hidden(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "news.db"
        self._original = core.DB_FILE
        core.DB_FILE = self.db
        core.init_db()
        core.insert_articles([article(KEEP, "남아 있는 기사"), article(HIDE, "가려질 기사")])

    def tearDown(self):
        core.DB_FILE = self._original

    def stored_links(self):
        connection = sqlite3.connect(str(self.db))
        try:
            return {row[0] for row in connection.execute("SELECT link FROM articles")}
        finally:
            connection.close()

    def total(self, **kwargs):
        _, total, _ = core.query_articles(hours=24, region="글로벌", **kwargs)
        return total

    def test_the_table_is_created_by_init_db(self):
        connection = sqlite3.connect(str(self.db))
        try:
            found = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='hidden_links'").fetchone()
        finally:
            connection.close()
        self.assertTrue(found, "the migration has to create it, not the first hide")

    def test_hiding_takes_the_story_out_of_the_read_paths(self):
        self.assertEqual(self.total(), 2)
        core.hide_link(HIDE, "가려질 기사")
        self.assertEqual(self.total(), 1, "the reader's list loses it")
        rows, _, _ = core.query_articles(hours=24, region="글로벌")
        self.assertNotIn(HIDE, [row["link"] for row in rows])
        # And it is not merely filtered from the default view: any filter combination must miss it,
        # or hiding would only work on the screen it was done from.
        self.assertEqual(self.total(text="가려질"), 0, "not even asking for it by name brings it back")
        self.assertEqual(self.total(category="시장·가격"), 1, "the other row is untouched")

    def test_the_row_is_still_in_the_archive(self):
        core.hide_link(HIDE, "가려질 기사")
        self.assertEqual(self.stored_links(), {KEEP, HIDE}, "hiding must not delete the row")
        self.assertEqual(core.archive_stats()["archived_total"], 2)
        self.assertEqual(core.archive_stats()["hidden_total"], 1,
                         "stored and hidden are two different numbers")

    def test_the_restore_list_carries_the_headline(self):
        core.hide_link(HIDE, "")
        rows = core.hidden_links()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link"], HIDE)
        self.assertEqual(rows[0]["title"], "가려질 기사",
                         "the title is read back from the archived row when none was given")
        self.assertTrue(rows[0]["hidden_at"])

    def test_restoring_puts_it_back(self):
        core.hide_link(HIDE, "")
        self.assertEqual(core.unhide_link(HIDE), 0)
        self.assertEqual(self.total(), 2)
        self.assertEqual(core.hidden_links(), [])

    def test_hiding_twice_is_one_entry_and_updates_the_clock(self):
        core.hide_link(HIDE, "first")
        core.hide_link(HIDE, "second")
        rows = core.hidden_links()
        self.assertEqual(len(rows), 1, "the link is the key, so a repeat is not a second entry")
        self.assertEqual(rows[0]["title"], "second")

    def test_a_hidden_link_stays_hidden_after_the_row_is_replaced(self):
        core.hide_link(HIDE, "가려질 기사")
        # Retention deletes a row and the collector fetches it again: the story is back in the
        # archive under the same link, and the reader must still not see it.
        connection = sqlite3.connect(str(self.db))
        try:
            connection.execute("DELETE FROM articles WHERE link = ?", (HIDE,))
            connection.commit()
        finally:
            connection.close()
        core.insert_articles([article(HIDE, "가려질 기사")])
        self.assertEqual(self.total(), 1)
        self.assertIn(HIDE, self.stored_links())

    def test_the_seed_of_a_page_skips_hidden_rows(self):
        core.hide_link(HIDE, "가려질 기사")
        seed = page_build.seed_from_db(str(self.db), "글로벌", False, "ko", limit=25)
        self.assertIn("남아 있는 기사", seed)
        self.assertNotIn("가려질 기사", seed,
                         "the page ships its first screen in the HTML, so the seed has to skip too")

    def test_the_link_guard_rejects_what_cannot_be_a_story(self):
        for bad in ("", "   ", "ftp://example.com/x", "example.com/x", "https://", "h" * 3000,
                    None):
            self.assertFalse(core._looks_like_link(bad or ""), repr(bad))
        self.assertTrue(core._looks_like_link("https://example.com/a-story"))
        self.assertTrue(core._looks_like_link("http://localhost:8080/x"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
