"""Teemo's Pick: the operator's judgement, and what a reader sees of it.

A pick is the one piece of operator input a reader is meant to see, so this file checks both ends:
that the annotation reaches the rows on their way out (including the seeded first screen, which is
in the HTML before any script runs), and that it stays a judgement rather than a rank - the order of
the feed must be the same with and without picks.

    python tests/test_picks.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import live_news_dashboard as core  # noqa: E402
import page_build  # noqa: E402

OLD = "https://example.com/older-picked"
NEW = "https://example.com/newer-plain"
FILLER = "https://example.com/filler"


def article(link, title, published):
    return {"link": link, "title": title, "summary": "본문", "source": "Example",
            "source_type": "news", "region": "글로벌", "category": "시장·가격",
            "categories": ["시장·가격"], "priority": 3, "published_at": published,
            "collected_at": published}


class Picks(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "news.db"
        self._original = core.DB_FILE
        core.DB_FILE = self.db
        core.init_db()
        core.insert_articles([
            article(NEW, "새 기사", "2026-09-20T12:00:00+00:00"),
            article(OLD, "오래된 기사", "2026-09-20T09:00:00+00:00"),
            article(FILLER, "보통 기사", "2026-09-20T06:00:00+00:00"),
        ])

    def tearDown(self):
        core.DB_FILE = self._original

    def rows(self, **kwargs):
        items, total, _ = core.query_articles(hours=24, region="글로벌", **kwargs)
        return items, total

    def test_the_table_is_created_by_init_db(self):
        import sqlite3
        connection = sqlite3.connect(str(self.db))
        try:
            found = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='picked_links'").fetchone()
        finally:
            connection.close()
        self.assertTrue(found)

    def test_a_row_carries_the_pick_and_the_phrase(self):
        items, _ = self.rows()
        self.assertFalse(any(item["picked"] for item in items), "nothing is picked to start with")
        core.pick_link(OLD, "직접 확인한 내용")
        items, _ = self.rows()
        by_link = {item["link"]: item for item in items}
        self.assertTrue(by_link[OLD]["picked"])
        self.assertEqual(by_link[OLD]["pick_note"], "직접 확인한 내용")
        self.assertFalse(by_link[NEW]["picked"], "a pick is about one story, not the whole feed")
        self.assertEqual(by_link[NEW]["pick_note"], "")

    def test_a_pick_never_changes_the_order(self):
        before = [item["link"] for item in self.rows()[0]]
        core.pick_link(FILLER, "")
        core.pick_link(OLD, "")
        after = [item["link"] for item in self.rows()[0]]
        self.assertEqual(before, after, "newest first, picked or not")
        self.assertEqual(before[0], NEW, "the newest story stays on top")

    def test_picked_only_narrows_the_list(self):
        core.pick_link(OLD, "")
        items, total = self.rows(picked_only=True)
        self.assertEqual(total, 1)
        self.assertEqual([item["link"] for item in items], [OLD])

    def test_a_pick_composes_with_the_other_conditions(self):
        core.pick_link(OLD, "")
        self.assertEqual(self.rows(picked_only=True, category="시장·가격")[1], 1)
        self.assertEqual(self.rows(picked_only=True, category="트럼프")[1], 0,
                         "a pick is one more condition, not an override")

    def test_unpicking_removes_it(self):
        core.pick_link(OLD, "")
        self.assertEqual(core.unpick_link(OLD), 0)
        self.assertEqual(self.rows(picked_only=True)[1], 0)
        self.assertNotIn(OLD, [item["link"] for item in self.rows(picked_only=True)[0]])

    def test_picking_twice_updates_the_phrase(self):
        core.pick_link(OLD, "first")
        core.pick_link(OLD, "second")
        picks = core.picked_links()
        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0]["note"], "second")
        self.assertEqual(picks[0]["title"], "오래된 기사", "the headline comes from the archive")

    def test_the_list_is_newest_pick_first(self):
        core.pick_link(OLD, "older pick")
        core.pick_link(NEW, "newer pick")
        self.assertEqual([row["link"] for row in core.picked_links()], [NEW, OLD])

    def test_the_seeded_page_carries_the_badge(self):
        core.pick_link(OLD, "확인함")
        seed = page_build.seed_from_db(str(self.db), "글로벌", False, "ko", limit=25)
        self.assertIn("pickbadge", seed, "the badge is part of the first screen, not of the fetch")
        self.assertIn("확인함", seed)
        self.assertEqual(seed.count("pickbadge"), 1, "only the picked story carries it")

    def test_the_seed_is_unchanged_when_nothing_is_picked(self):
        seed = page_build.seed_from_db(str(self.db), "글로벌", False, "ko", limit=25)
        self.assertNotIn("pickbadge", seed)

    def test_a_pick_does_not_move_the_stars_or_the_priority(self):
        before = {item["link"]: (item["priority"], item.get("asset")) for item in self.rows()[0]}
        core.pick_link(OLD, "note")
        after = {item["link"]: (item["priority"], item.get("asset")) for item in self.rows()[0]}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
