"""The source name a reader sees once the aggregator link is resolved.

A Google News row is filed under the query that collected it ("Google News · 스테이블코인") because
that is the identity the source filter and the source pills address. Its `<source>` element, however,
carries the publisher's own name, and that is what the reader should see on the card once the link
has been resolved. This file checks the whole path of that name - feed metadata, storage, the API,
and the two readers (the dashboard card and the landing strip) - plus the thing that must NOT change:
the source identity every filter is built on.

    python tests/test_original_source.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))

import collect_public  # noqa: E402
import google_news  # noqa: E402
import landing  # noqa: E402
import live_news_dashboard as core  # noqa: E402
import page_build  # noqa: E402

AGG = ("https://news.google.com/rss/articles/CBMiWEFVX3lxTE93OFlPeFdrWVBvS1FQOGJlTnladzUw"
       "NERweEpUdGZEUUsy?oc=5")
PUB = "https://bitcoinmagazine.com/news/new-york-sues-polymarket"
QUERY = "Google News · 스테이블코인"

# The shape Google News search RSS has: the publisher sits in <source>, with its home page in the
# url attribute, beside the aggregator <link>.
RSS_WITH_SOURCE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>bitcoin</title>
<item>
  <title>New York Sues Polymarket - Bitcoin Magazine</title>
  <link>%s</link>
  <description>&lt;a href="x"&gt;New York Sues Polymarket&lt;/a&gt;</description>
  <pubDate>Thu, 24 Sep 2026 22:11:00 GMT</pubDate>
  <source url="https://bitcoinmagazine.com">Bitcoin Magazine</source>
</item>
<item>
  <title>A story the feed did not name a publisher for</title>
  <link>https://news.google.com/rss/articles/CBMiOTHERID?oc=5</link>
  <pubDate>Thu, 24 Sep 2026 22:05:00 GMT</pubDate>
</item>
</channel></rss>""" % AGG.encode()


def stored_row(**overrides):
    row = {"link": AGG, "title": "New York Sues Polymarket", "summary": "본문", "source": QUERY,
           "source_type": "aggregated", "region": "글로벌", "category": "일반",
           "categories": "일반", "asset": "시장", "priority": 3,
           "published_at": datetime.now(timezone.utc).isoformat(), "collected_at": "",
           "original_source": "Bitcoin Magazine"}
    row.update(overrides)
    return row


class FeedMetadata(unittest.TestCase):
    def test_the_publisher_name_is_read_from_the_source_element(self):
        items = core.parse_rss(RSS_WITH_SOURCE, QUERY, "aggregated")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["original_source"], "Bitcoin Magazine")
        # The collecting query is untouched: it is the source filter's identity.
        self.assertEqual(items[0]["source"], QUERY)

    def test_a_feed_without_a_source_element_leaves_the_name_empty(self):
        items = core.parse_rss(RSS_WITH_SOURCE, QUERY, "aggregated")
        self.assertEqual(items[1]["original_source"], "")
        self.assertEqual(items[1]["source"], QUERY)

    def test_a_plain_rss_feed_is_unaffected(self):
        plain = (b'<?xml version="1.0"?><rss version="2.0"><channel><item>'
                 b'<title>t</title><link>https://example.co.kr/a</link>'
                 b'<pubDate>Thu, 24 Sep 2026 22:11:00 GMT</pubDate></item></channel></rss>')
        items = core.parse_rss(plain, "Example", "breaking")
        self.assertEqual(items[0]["original_source"], "")
        self.assertEqual(items[0]["source"], "Example")


class DisplayLabel(unittest.TestCase):
    def test_a_resolved_row_with_a_publisher_name_shows_that_name(self):
        self.assertEqual(google_news.display_source(
            {"source": QUERY, "original_source": "Bitcoin Magazine", "original_link": PUB}),
            "Bitcoin Magazine")

    def test_a_resolved_row_without_a_name_falls_back_to_the_hostname(self):
        self.assertEqual(google_news.display_source(
            {"source": QUERY, "original_source": "", "original_link": "https://www.example.co.kr/a"}),
            "example.co.kr")

    def test_an_unresolved_row_keeps_the_query_label(self):
        self.assertEqual(google_news.display_source(
            {"source": QUERY, "original_source": "Bitcoin Magazine"}), QUERY)
        self.assertEqual(google_news.display_source({"source": QUERY, "original_link": ""}), QUERY)

    def test_a_hostname_fallback_never_lands_on_google(self):
        # belt and braces: the resolution layer refuses a Google answer, and so does the label
        self.assertEqual(google_news.hostname("https://news.google.com/rss/articles/x"),
                         "news.google.com")
        self.assertEqual(google_news.display_source(
            {"source": QUERY, "original_source": "", "original_link": ""}), QUERY)


class Storage(unittest.TestCase):
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

    def test_a_database_without_the_column_gains_it(self):
        connection = sqlite3.connect(core.DB_FILE)
        connection.execute(
            "CREATE TABLE articles (link TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, "
            "source TEXT, source_type TEXT, region TEXT, category TEXT, categories TEXT, "
            "asset TEXT, priority INTEGER, published_at TEXT NOT NULL, collected_at TEXT)")
        connection.execute("INSERT INTO articles (link, title, published_at) VALUES (?,?,?)",
                           ("https://example.co.kr/old", "옛 기사", "2026-09-01T00:00:00+00:00"))
        connection.commit()
        connection.close()
        core.init_db()
        connection = sqlite3.connect(core.DB_FILE)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
        self.assertIn("original_source", columns)
        # The old row keeps a NULL, which the label treats as "no name known" rather than as text.
        self.assertIsNone(connection.execute(
            "SELECT original_source FROM articles WHERE link = ?",
            ("https://example.co.kr/old",)).fetchone()[0])
        connection.close()

    def test_the_name_round_trips_through_the_articles_table(self):
        core.init_db()
        self.assertEqual(core.insert_articles([stored_row()]), 1)
        row = core.query_articles(hours=24, limit=5)[0][0]
        self.assertEqual(row["original_source"], "Bitcoin Magazine")
        self.assertEqual(row["source"], QUERY)

    def test_a_row_stored_without_a_name_reads_back_as_empty(self):
        core.init_db()
        core.insert_articles([stored_row(link="https://example.co.kr/b", original_source="")])
        row = core.query_articles(hours=24, limit=5)[0][0]
        self.assertIn(row["original_source"], (None, ""))


class ApiSerialization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp.close()
        self.previous = core.DB_FILE
        core.DB_FILE = self.temp.name
        core._ORIGINALS.update({"loaded_at": 0.0, "map": {}})
        core.init_db()
        core.insert_articles([stored_row()])
        connection = core.db_connect()
        try:
            google_news.remember(connection, {AGG: PUB})
        finally:
            connection.close()

    def tearDown(self):
        core.DB_FILE = self.previous
        core._ORIGINALS.update({"loaded_at": 0.0, "map": {}})
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.temp.name + suffix)
            except OSError:
                pass

    def test_the_api_row_carries_both_names_and_the_resolved_link(self):
        rows, _total, _counts = core.query_articles(hours=24, limit=10)
        row = rows[0]
        cache = core.original_links()
        original = google_news.original_for(str(row["link"]), cache)
        self.assertEqual(original, PUB)
        # This is the shape the handler puts on the wire: `source` kept, `original_source` kept,
        # `original_link` added, and the label derived from them.
        row["original_link"] = original
        payload = json.dumps({"articles": [row]}, ensure_ascii=False)
        self.assertIn('"source": "%s"' % QUERY, payload)
        self.assertIn('"original_source": "Bitcoin Magazine"', payload)
        self.assertIn(PUB, payload)
        self.assertEqual(google_news.display_source(row), "Bitcoin Magazine")

    def test_source_filter_identity_is_unchanged(self):
        """The operator's source axis must keep answering the stored query, not the publisher."""
        rows, _t, _c = core.query_articles(hours=24, limit=10, source=[QUERY])
        self.assertEqual(len(rows), 1)
        rows, _t, _c = core.query_articles(hours=24, limit=10, source=["Bitcoin Magazine"])
        self.assertEqual(rows, [])

    def test_the_published_row_carries_the_publisher_name(self):
        published = collect_public.public_row(
            stored_row(), {AGG: PUB})
        self.assertEqual(published["source"], QUERY)
        self.assertEqual(published["original_source"], "Bitcoin Magazine")
        self.assertEqual(published["original_link"], PUB)
        self.assertEqual(google_news.display_source(published), "Bitcoin Magazine")


class Rendering(unittest.TestCase):
    def test_the_seeded_card_names_the_publisher(self):
        resolved = collect_public.public_row(stored_row(), {AGG: PUB})
        html = page_build._seed_cards([resolved], False, "ko")
        self.assertIn('<span class="chip src">Bitcoin Magazine</span>', html)
        self.assertNotIn('<span class="chip src">' + QUERY + '</span>', html)

    def test_the_seeded_card_keeps_the_query_label_while_unresolved(self):
        unresolved = collect_public.public_row(stored_row(), {})
        html = page_build._seed_cards([unresolved], False, "ko")
        self.assertIn('<span class="chip src">' + QUERY + '</span>', html)

    def test_the_seeded_card_uses_the_hostname_when_the_feed_gave_no_name(self):
        without_name = collect_public.public_row(stored_row(original_source=""), {AGG: PUB})
        html = page_build._seed_cards([without_name], False, "ko")
        self.assertIn('<span class="chip src">bitcoinmagazine.com</span>', html)

    def test_the_page_script_derives_the_label_and_keeps_the_filter_value(self):
        self.assertIn("function srcLabel(a)", page_build.SCRIPT)
        self.assertIn("esc(srcLabel(a))", page_build.SCRIPT)
        # The chip still filters on the stored source.
        self.assertIn("data-v=\"'+esc(a.source)+'\"", page_build.SCRIPT)
        self.assertIn("srcOn=tag.k==='src'&&tag.v===a.source", page_build.SCRIPT)

    def test_the_source_pills_still_list_the_query_identity(self):
        """The pill row is built from the stored source, so adding a publisher name changes no pill."""
        self.assertIn("function pillCount", page_build.SCRIPT)
        self.assertIn("catList(a)", page_build.SCRIPT)

    def test_the_landing_strip_names_the_publisher(self):
        self.assertIn("function srcLabel(a)", landing.PAGE)
        self.assertIn("source.textContent=srcLabel(a)||'원문'", landing.PAGE)

    def test_the_landing_strip_links_to_the_publisher(self):
        self.assertIn("safeLink(a.original_link||a.link)", landing.PAGE)


class OperatorFilter(unittest.TestCase):
    def test_switching_a_source_off_still_addresses_the_query(self):
        with open(os.path.join(ROOT, "deploy", "collect_public.py"), encoding="utf-8") as handle:
            published = handle.read()
        self.assertIn('"original_source"', published)
        # The push/selection path keeps reading the stored source for its own identity checks.
        with open(os.path.join(ROOT, "live_news_dashboard.py"), encoding="utf-8") as handle:
            collector = handle.read()
        self.assertIn('"original_source": clean_text(original_source)', collector)
        self.assertIn('"source": source,', collector)


class RecollectBackfill(unittest.TestCase):
    """A story seen again with a publisher name fills the blank on the stored row - and nothing else."""

    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp.close()
        self.previous = core.DB_FILE
        core.DB_FILE = self.temp.name
        core.init_db()

    def tearDown(self):
        core.DB_FILE = self.previous
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.temp.name + suffix)
            except OSError:
                pass

    def one_row(self, link=AGG):
        rows, _total, _counts = core.query_articles(hours=24, limit=10)
        return {row["link"]: row for row in rows}[link]

    def test_a_blank_name_is_filled_when_the_story_comes_back(self):
        core.insert_articles([stored_row(original_source="")])
        first = self.one_row()
        self.assertIn(first["original_source"], (None, ""))
        # The same story is collected again, this time with the publisher the feed now names.
        self.assertEqual(core.insert_articles([stored_row(original_source="Bitcoin Magazine")]), 0)
        again = self.one_row()
        self.assertEqual(again["original_source"], "Bitcoin Magazine")
        # Only the name moved: the link, the query identity, the title, the clock and the rest are
        # exactly what they were.
        for field in ("link", "source", "source_type", "title", "summary", "published_at",
                      "collected_at", "category", "categories", "region", "asset", "priority"):
            self.assertEqual(again[field], first[field], field)

    def test_an_existing_name_is_never_overwritten(self):
        core.insert_articles([stored_row(original_source="Bitcoin Magazine")])
        core.insert_articles([stored_row(original_source="Someone Else")])
        self.assertEqual(self.one_row()["original_source"], "Bitcoin Magazine")

    def test_a_blank_incoming_name_does_not_clear_the_stored_one(self):
        core.insert_articles([stored_row(original_source="Bitcoin Magazine")])
        core.insert_articles([stored_row(original_source="")])
        self.assertEqual(self.one_row()["original_source"], "Bitcoin Magazine")

    def test_the_query_identity_survives_the_backfill(self):
        core.insert_articles([stored_row(original_source="")])
        core.insert_articles([stored_row(original_source="Bitcoin Magazine")])
        # The operator's source axis still answers the collecting query, not the publisher.
        rows, _t, _c = core.query_articles(hours=24, limit=10, source=[QUERY])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], QUERY)
        rows, _t, _c = core.query_articles(hours=24, limit=10, source=["Bitcoin Magazine"])
        self.assertEqual(rows, [])

    def test_a_backfill_is_not_counted_as_a_new_row(self):
        core.insert_articles([stored_row(original_source="")])
        self.assertEqual(core.insert_articles([stored_row(original_source="CoinDesk")]), 0)
        self.assertEqual(len(core.query_articles(hours=24, limit=10)[0]), 1)

    def test_only_the_matching_link_is_touched(self):
        core.insert_articles([stored_row(original_source="")])
        core.insert_articles([stored_row(link="https://example.co.kr/other",
                                         original_source="Other Site")])
        self.assertIn(self.one_row()["original_source"], (None, ""))
        self.assertEqual(self.one_row("https://example.co.kr/other")["original_source"], "Other Site")


class SeedPath(unittest.TestCase):
    """The first screen - the HTML before any script runs - names the same publisher."""

    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp.close()
        self.db = self.temp.name
        connection = sqlite3.connect(self.db)
        connection.execute(
            "CREATE TABLE articles (link TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, "
            "source TEXT, source_type TEXT, region TEXT, category TEXT, categories TEXT, "
            "asset TEXT, priority INTEGER, published_at TEXT NOT NULL, collected_at TEXT, "
            "original_source TEXT)")
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "INSERT INTO articles (link, title, summary, source, source_type, region, category, "
            "categories, priority, published_at, original_source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (AGG, "New York Sues Polymarket", "본문", QUERY, "aggregated", "글로벌", "일반", "일반",
             3, now, "Bitcoin Magazine"))
        connection.execute(
            "INSERT INTO articles (link, title, summary, source, source_type, region, category, "
            "categories, priority, published_at, original_source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("https://news.google.com/rss/articles/CBMiOTHER?oc=5", "다른 기사", "본문", QUERY,
             "aggregated", "글로벌", "일반", "일반", 3, now, ""))
        connection.commit()
        connection.close()

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def _resolve_one(self):
        connection = sqlite3.connect(self.db)
        google_news.ensure_table(connection)
        google_news.remember(connection, {AGG: PUB})
        connection.close()

    def test_the_seeded_first_screen_names_the_publisher(self):
        self._resolve_one()
        html = page_build.seed_from_db(self.db, "글로벌", False, "ko", limit=5)
        self.assertIn('<span class="chip src">Bitcoin Magazine</span>', html)
        self.assertIn('href="' + PUB + '"', html)

    def test_an_unresolved_seeded_row_keeps_the_query_label(self):
        self._resolve_one()
        html = page_build.seed_from_db(self.db, "글로벌", False, "ko", limit=5)
        self.assertIn('<span class="chip src">' + QUERY + '</span>', html)

    def test_a_database_without_the_cache_table_still_seeds(self):
        """The page is rebuilt before the collector has created the cache table."""
        html = page_build.seed_from_db(self.db, "글로벌", False, "ko", limit=5)
        self.assertIn('<span class="chip src">' + QUERY + '</span>', html)
        self.assertNotIn("original_link", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
