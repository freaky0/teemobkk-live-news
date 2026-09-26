"""One story, one row on the screen.

The repetition a reader reported (2026-09-26): "Thailand issues warning of heavy rain" appeared four
times in the Thailand tab - Global Times, english.news.cn twice, Xinhua - and the two english.news.cn
rows were two different Google links for the same article. The link is the table's primary key, so an
identical link was never the problem; three separate paths let a story through twice:

  * Google hands one article out under several aggregator links, so the key it is filed under differs
    while the article behind it does not;
  * a wire story is carried by several outlets, and their headlines differ only in the outlet name
    Google appends ("… - Global Times", "… - english.news.cn", "… -Xinhua - 新华网"), which kept the
    old similarity check from recognising them as one story;
  * the in-cycle check only ever saw one cycle, so a story arriving again an hour later was new again.

This file locks the fix on all three, and - just as important - locks the cases that must NOT merge:
different flood stories that share a topic.

    python tests/test_dedupe.py
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))

import google_news  # noqa: E402
import live_news_dashboard as core  # noqa: E402

# Measured on the live Thailand window: the same wire story, from four outlets, under four links.
# The two english.news.cn rows are two different Google links for the same article.
STORY = [
    {"title": "Thailand issues warning of heavy rain - Global Times",
     "link": "https://news.google.com/rss/articles/CBMiYkFVX3lxTE1TcEtxTmRYMll6?oc=5",
     "source": "Google News · 방콕", "source_type": "aggregated", "region": "태국",
     "original_source": "Global Times", "published_at": "2026-09-25T23:46:00+00:00", "priority": 2},
    {"title": "Thailand issues warning of heavy rain - english.news.cn",
     "link": "https://news.google.com/rss/articles/CBMifEFVX3lxTE9FRkFjTWRiUTRH?oc=5",
     "source": "Google News · 태국", "source_type": "aggregated", "region": "태국",
     "original_source": "english.news.cn", "published_at": "2026-09-25T23:24:00+00:00", "priority": 2},
    {"title": "Thailand issues warning of heavy rain - english.news.cn",
     "link": "https://news.google.com/rss/articles/CBMijAFBVV95cUxQcFRsVS12YkM2?oc=5",
     "source": "Google News · 태국", "source_type": "aggregated", "region": "태국",
     "original_source": "english.news.cn", "published_at": "2026-09-25T23:24:00+00:00", "priority": 2},
    {"title": "Thailand issues warning of heavy rain-Xinhua - 新华网",
     "link": "https://news.google.com/rss/articles/CBMimAFBVV95cUxPaTlRb0NRTnht?oc=5",
     "source": "Google News · 방콕", "source_type": "aggregated", "region": "태국",
     "original_source": "新华网", "published_at": "2026-09-25T23:24:00+00:00", "priority": 2},
]

# Different events that share a topic. They must stay separate rows.
OTHER_EVENTS = [
    {"title": "Eastern Bangkok on flood alert as water in canals reaches critical - Bangkok Post",
     "link": "https://news.google.com/rss/articles/CBMi0gFBVV95cUxNVmpZc3VaR3Yw?oc=5",
     "source": "Google News · 방콕", "source_type": "aggregated", "region": "태국",
     "original_source": "Bangkok Post", "published_at": "2026-09-25T12:07:00+00:00", "priority": 2},
    {"title": "Flooding hits Bangkok as prolonged rain disrupts major routes - Phuket News",
     "link": "https://news.google.com/rss/articles/CBMiYkFVX3lxTFBDNVlJb3hmR0du?oc=5",
     "source": "Google News · 방콕", "source_type": "aggregated", "region": "태국",
     "original_source": "Phuket News", "published_at": "2026-09-25T11:49:00+00:00", "priority": 2},
    {"title": "Heavy flooding submerges vehicles, halts traffic in eastern Thailand",
     "link": "https://news.google.com/rss/articles/CBMisgFBVV95cUxPSGdpUExCTmRX?oc=5",
     "source": "Google News · 태국", "source_type": "aggregated", "region": "태국",
     "original_source": "Thai PBS", "published_at": "2026-09-25T20:06:00+00:00", "priority": 2},
]


def copy_of(article, **changes):
    row = dict(article)
    row.update(changes)
    return row


class TitleKey(unittest.TestCase):
    def test_the_four_outlets_carrying_one_wire_story_share_a_key(self):
        keys = {core.dedupe_key(a["title"], a["original_source"]) for a in STORY}
        self.assertEqual(len(keys), 1, keys)
        self.assertEqual(keys, {"thailandissueswarningofheavyrain"})

    def test_the_publisher_name_is_stripped_before_comparing(self):
        # "-Xinhua - 新华网": the agency's own tag, then the name Google appended.
        self.assertEqual(core.dedupe_key("Thailand issues warning of heavy rain-Xinhua - 新华网", "新华网"),
                         "thailandissueswarningofheavyrain")

    def test_a_korean_headline_with_an_outlet_tail_is_the_same_story(self):
        left = core.dedupe_key("“월 1000만원 벌 수 있다”에 태국 간 고3…123억원 보이스피싱 가담 - 주간조선", "주간조선")
        right = core.dedupe_key("“월 1000만원 벌 수 있다”에 태국 간 고3…123억원 보이스피싱 가담")
        self.assertEqual(left, right)

    def test_a_non_publisher_tail_is_preserved(self):
        self.assertNotEqual(core.dedupe_key("Rates rise - after talks continue"),
                            core.dedupe_key("Rates rise"))

    def test_different_events_keep_different_keys(self):
        keys = {core.dedupe_key(a["title"], a["original_source"]) for a in OTHER_EVENTS}
        self.assertEqual(len(keys), len(OTHER_EVENTS), keys)

    def test_the_similarity_margin_between_those_events_is_wide(self):
        """They are guarded by an exact key and a high in-cycle threshold, not by a guess."""
        a = core.dedupe_key(OTHER_EVENTS[0]["title"])
        b = core.dedupe_key(OTHER_EVENTS[1]["title"])
        self.assertFalse(core._similar_title(a, b))


class InCycleDedupe(unittest.TestCase):
    def test_the_four_outlet_copies_collapse_to_the_newest(self):
        kept = core.dedupe([copy_of(a) for a in STORY])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["title"], "Thailand issues warning of heavy rain - Global Times")

    def test_different_events_are_all_kept(self):
        kept = core.dedupe([copy_of(a) for a in OTHER_EVENTS])
        self.assertEqual(len(kept), len(OTHER_EVENTS))

    def test_an_identical_link_is_kept_once(self):
        kept = core.dedupe([copy_of(STORY[1]), copy_of(STORY[1], title="다른 제목")])
        self.assertEqual(len(kept), 1)

    def test_the_same_publisher_link_under_two_aggregator_links_is_one_story(self):
        kept = core.dedupe([
            copy_of(STORY[0], link="https://www.bangkokpost.com/thailand/general/3325484/a"),
            copy_of(STORY[0], link="https://www.bangkokpost.com/thailand/general/3325484/a?utm=2"),
        ])
        self.assertEqual(len(kept), 1)


class ScreenDedupe(unittest.TestCase):
    def test_the_screen_drops_the_second_copy_of_the_wire_story(self):
        rows = [copy_of(a) for a in STORY] + [copy_of(a) for a in OTHER_EVENTS]
        kept = core.dedupe_rows(rows)
        titles = [row["title"] for row in kept]
        self.assertEqual(len(kept), 1 + len(OTHER_EVENTS), titles)

    def test_the_screen_drops_the_same_link_even_when_titles_differ(self):
        rows = [copy_of(STORY[1]), copy_of(STORY[1], title="A rewritten title")]
        self.assertEqual(len(core.dedupe_rows(rows)), 1)

    def test_two_google_links_for_one_article_collapse_once_resolved(self):
        """The exact shape a reader saw: two english.news.cn rows, one article behind them."""
        rows = [copy_of(STORY[1], original_link="https://english.news.cn/20260926/abc/c.html"),
                copy_of(STORY[2], original_link="https://english.news.cn/20260926/abc/c.html")]
        self.assertEqual(len(core.dedupe_rows(rows)), 1)

    def test_a_region_keeps_its_own_copy(self):
        """The global tab and the Thailand tab are two views, not duplicates of each other."""
        rows = [copy_of(STORY[1]), copy_of(STORY[2], region="글로벌")]
        self.assertEqual(len(core.dedupe_rows(rows)), 2)

    def test_a_row_without_a_title_is_not_dropped_by_a_key(self):
        rows = [copy_of(STORY[1], title=""), copy_of(STORY[2], title="")]
        self.assertEqual(len(core.dedupe_rows(rows)), 2)


class StoredDedupe(unittest.TestCase):
    """A story seen again in a later cycle: compare against the window, not just this cycle."""

    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp.close()
        self.previous = core.DB_FILE
        core.DB_FILE = self.temp.name

    def tearDown(self):
        core.DB_FILE = self.previous
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.temp.name + suffix)
            except OSError:
                pass

    def stored(self):
        core.init_db()
        core.insert_articles([copy_of(STORY[0])])

    def test_the_same_story_under_a_second_outlet_is_not_stored_again(self):
        self.stored()
        fresh = [copy_of(STORY[1])]          # english.news.cn, different link, same wire copy
        self.assertEqual(core.drop_already_stored(fresh), [])
        self.assertEqual(core.insert_articles(core.drop_already_stored(fresh)), 0)

    def test_a_different_story_is_stored(self):
        self.stored()
        fresh = [copy_of(a) for a in OTHER_EVENTS]
        self.assertEqual(len(core.drop_already_stored(fresh)), len(OTHER_EVENTS))

    def test_a_second_region_keeps_its_copy(self):
        self.stored()
        fresh = [copy_of(STORY[1], region="글로벌")]
        self.assertEqual(len(core.drop_already_stored(fresh)), 1)

    def test_the_stored_publisher_url_blocks_the_same_article_from_another_feed(self):
        """A row whose Google link is resolved can still be matched by its publisher URL."""
        self.stored()
        connection = core.db_connect()
        try:
            google_news.remember(connection, {STORY[0]["link"]:
                                              "https://www.globaltimes.cn/page/202609/1234.shtml"})
        finally:
            connection.close()
        direct = [copy_of(STORY[1], title="Heavy rain warning issued for Thailand",
                          link="https://www.globaltimes.cn/page/202609/1234.shtml?ref=rss")]
        self.assertEqual(core.drop_already_stored(direct), [])


class Wiring(unittest.TestCase):
    """The three call sites, and the one path that must keep its own selection."""

    def source(self, name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
            return handle.read()

    def test_the_collector_dedupes_against_the_window_before_inserting(self):
        self.assertIn("deduped = drop_already_stored(dedupe_by_region(fresh_articles))",
                      self.source("live_news_dashboard.py"))

    def test_the_api_dedupes_the_rows_it_hands_a_page(self):
        self.assertIn("articles = dedupe_rows(articles)", self.source("live_news_dashboard.py"))

    def test_the_published_json_gets_the_same_treatment(self):
        self.assertIn("core.dedupe_rows(fetch_window())", self.source("deploy/collect_public.py"))

    def test_the_push_selection_keeps_its_own_gate(self):
        """deploy/tg_push.py selects its own candidates and has its own duplicate gate: untouched."""
        push = self.source("deploy/tg_push.py")
        self.assertIn("core._similar_title", push)
        self.assertNotIn("dedupe_rows", push)


if __name__ == "__main__":
    unittest.main(verbosity=2)
