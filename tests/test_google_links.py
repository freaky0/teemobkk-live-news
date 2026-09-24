"""Google News links: the reader goes to the publisher, the row keeps its identity.

A Google News row is stored under the aggregator URL and that URL is the primary key every
operator action and the push history address. So the fix is not to rewrite the row: the
publisher URL is resolved (from Google's own answer, never assembled) into a cache, published
beside the stored link, and used wherever a reader clicks. This file checks each of those
steps without touching the network - the RPC answer is canned.

    python tests/test_google_links.py
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

import collect_public  # noqa: E402
import google_news  # noqa: E402
import landing  # noqa: E402
import live_news_dashboard as core  # noqa: E402
import page_build  # noqa: E402

AGG = ("https://news.google.com/rss/articles/CBMihgFBVV95cUxNRDlVOS1zS05fUkhyWk5ac3NKUG9XN2JD"
       "WE41ODRXZkxGaEFzU1ozYk5jcTlSeTBUTHNyd0d3?oc=5")
PUBLISHER = "https://www.xportsnews.com/article/2200096"
# The shape a real batchexecute answer has, quote for quote (measured 2026-09-24).
RPC_ANSWER = (r''')]}'  [[\"wrb.fr\",\"Fbv4je\",\"[\\\"garturlres\\\",\\\"https://www.xportsnews.com/article'''
              r'''/2200096\\\",1]\",null,null,null,\"generic\"],[\"di\",20],[\"af.httprm\",19,\"713\"]]''')
PAGE = '<html><body><c-wiz><div data-n-a-id="CBMihgFB" data-n-a-ts="1790285542" ' \
       'data-n-a-sg="AbIaSL_2OWUG4EsLKTeNT3GPLl-C"></div></c-wiz></body></html>'


def article(link, title="제목", published=None):
    return {"link": link, "title": title, "summary": "본문", "source": "Google News · Bitcoin",
            "source_type": "aggregated", "region": "글로벌", "category": "일반",
            "categories": "일반", "priority": 3,
            "published_at": published or datetime.now(timezone.utc).isoformat()}


class AggregatorDetection(unittest.TestCase):
    def test_google_news_link_is_an_aggregator(self):
        self.assertTrue(google_news.is_aggregator(AGG))

    def test_publisher_link_is_not_an_aggregator(self):
        self.assertFalse(google_news.is_aggregator(PUBLISHER))
        self.assertFalse(google_news.is_aggregator("https://www.matichon.co.th/sport/news_5896999"))

    def test_article_id_is_taken_from_the_path(self):
        self.assertTrue(google_news.article_id(AGG).startswith("CBMihgFB"))
        self.assertNotIn("oc=5", google_news.article_id(AGG))

    def test_a_google_answer_is_never_accepted_as_an_original(self):
        for url in ("https://news.google.com/rss/articles/x", "https://google.com/x",
                    "https://www.google.com/url?q=y", "ftp://example.com/a", "example.com/a", ""):
            self.assertFalse(google_news.valid_original(url), url)

    def test_a_publisher_url_is_accepted(self):
        self.assertTrue(google_news.valid_original(PUBLISHER))
        self.assertTrue(google_news.valid_original("http://example.co.kr/a?b=c"))


class RpcAnswer(unittest.TestCase):
    def test_the_publisher_url_is_read_out_of_the_answer(self):
        self.assertEqual(google_news.parse_rpc(RPC_ANSWER), PUBLISHER)

    def test_unicode_escapes_are_decoded(self):
        escaped = (r''')]}'  [[\"wrb.fr\",\"Fbv4je\",\"[\\\"garturlres\\\",\\\"https://pub.example/x'''
                   r'''?a=1\\u0026b=2\\\",1]\"]]''')
        self.assertEqual(google_news.parse_rpc(escaped), "https://pub.example/x?a=1&b=2")

    def test_escaped_slashes_are_decoded(self):
        escaped = (r''')]}'  [[\"wrb.fr\",\"Fbv4je\",\"[\\\"garturlres\\\",\\\"https:\\/\\/pub.example'''
                   r'''\\/y\\\",1]\"]]''')
        self.assertEqual(google_news.parse_rpc(escaped), "https://pub.example/y")

    def test_an_answer_without_the_marker_is_no_answer(self):
        self.assertIsNone(google_news.parse_rpc(')]}\'  [["wrb.fr","Fbv4je",null]]'))
        self.assertIsNone(google_news.parse_rpc(""))
        self.assertIsNone(google_news.parse_rpc(None))

    def test_an_answer_pointing_back_at_google_is_refused(self):
        bounce = (r''')]}'  [[\"wrb.fr\",\"Fbv4je\",\"[\\\"garturlres\\\",\\\"https://news.google.com'''
                  r'''/rss/articles/abc\\\",1]\"]]''')
        self.assertIsNone(google_news.parse_rpc(bounce))

    def test_signature_reads_the_page_attributes(self):
        self.assertEqual(google_news.signature(PAGE), ("1790285542", "AbIaSL_2OWUG4EsLKTeNT3GPLl-C"))
        self.assertIsNone(google_news.signature("<html><body>no attributes here</body></html>"))


class Resolve(unittest.TestCase):
    def test_a_google_link_resolves_through_the_rpc(self):
        seen = {}

        def rpc(url, body):
            seen["url"] = url
            seen["body"] = body
            return RPC_ANSWER

        self.assertEqual(google_news.resolve(AGG, opener=lambda link: PAGE, rpc=rpc), PUBLISHER)
        self.assertEqual(seen["url"], google_news.RPC_URL)
        self.assertIn("Fbv4je", seen["body"])
        self.assertIn(google_news.article_id(AGG), seen["body"])

    def test_a_publisher_link_is_left_alone(self):
        self.assertIsNone(google_news.resolve(PUBLISHER, opener=lambda link: PAGE,
                                              rpc=lambda url, body: RPC_ANSWER))

    def test_a_page_without_a_signature_resolves_nothing(self):
        self.assertIsNone(google_news.resolve(AGG, opener=lambda link: "<html></html>",
                                              rpc=lambda url, body: RPC_ANSWER))

    def test_a_failing_fetch_is_not_an_error(self):
        def boom(link):
            raise OSError("network down")

        self.assertIsNone(google_news.resolve(AGG, opener=boom, rpc=lambda url, body: RPC_ANSWER))
        self.assertEqual(google_news.resolve_many([AGG], opener=boom, rpc=lambda url, body: "x"), {})

    def test_several_links_resolve_in_one_pass(self):
        other = AGG.replace("?oc=5", "?oc=6")
        found = google_news.resolve_many([AGG, other], opener=lambda link: PAGE,
                                         rpc=lambda url, body: RPC_ANSWER)
        self.assertEqual(len(found), 2)
        self.assertEqual(set(found.values()), {PUBLISHER})


class Cache(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        google_news.ensure_table(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_a_resolution_survives_a_round_trip(self):
        self.assertEqual(google_news.remember(self.connection, {AGG: PUBLISHER}), 1)
        self.assertEqual(google_news.load(self.connection), {AGG: PUBLISHER})

    def test_a_bogus_original_is_not_stored(self):
        self.assertEqual(google_news.remember(self.connection, {AGG: "https://news.google.com/x"}), 0)
        self.assertEqual(google_news.remember(self.connection, {PUBLISHER: PUBLISHER}), 0)
        self.assertEqual(google_news.load(self.connection), {})

    def test_a_resolution_is_written_once(self):
        google_news.remember(self.connection, {AGG: PUBLISHER})
        google_news.remember(self.connection, {AGG: "https://other.example/a"})
        self.assertEqual(google_news.load(self.connection), {AGG: PUBLISHER})

    def test_the_reader_gets_the_stored_link_until_a_resolution_exists(self):
        self.assertEqual(google_news.original_for(AGG, {}), AGG)
        self.assertEqual(google_news.original_for(AGG, {AGG: PUBLISHER}), PUBLISHER)
        self.assertEqual(google_news.original_for("", {}), "")


class PublishedRow(unittest.TestCase):
    def test_a_resolved_link_is_published_beside_the_stored_one(self):
        row = collect_public.public_row(article(AGG), {AGG: PUBLISHER})
        self.assertEqual(row["link"], AGG)
        self.assertEqual(row["original_link"], PUBLISHER)

    def test_an_unresolved_row_publishes_no_extra_field(self):
        row = collect_public.public_row(article(AGG), {})
        self.assertEqual(row["link"], AGG)
        self.assertNotIn("original_link", row)

    def test_a_publisher_row_is_untouched(self):
        row = collect_public.public_row(article(PUBLISHER), {AGG: PUBLISHER})
        self.assertNotIn("original_link", row)

    def test_a_republished_row_keeps_one_entry_per_story(self):
        """The previous file holds the resolved row, the database holds the aggregator row."""
        fresh = [collect_public.public_row(article(AGG, title="같은 기사"), {AGG: PUBLISHER})]
        previous = [dict(fresh[0])]
        merged = [collect_public.public_row(row, {AGG: PUBLISHER})
                  for row in collect_public.merge(previous, fresh)]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["original_link"], PUBLISHER)
        self.assertEqual(collect_public.digest_of(merged), collect_public.digest_of(fresh))


class PageDisplay(unittest.TestCase):
    def test_the_seeded_card_links_to_the_publisher(self):
        html = page_build._seed_cards([collect_public.public_row(article(AGG), {AGG: PUBLISHER})],
                                     False, "ko")
        self.assertIn('href="' + PUBLISHER + '"', html)
        self.assertNotIn('href="' + AGG.replace("&", "&amp;") + '"', html)

    def test_the_seeded_card_falls_back_to_the_stored_link(self):
        html = page_build._seed_cards([collect_public.public_row(article(AGG), {})], False, "ko")
        self.assertIn("news.google.com", html)

    def test_the_page_script_prefers_the_resolved_link(self):
        self.assertIn("a.original_link||a.link", page_build.SCRIPT)

    def test_the_landing_strip_prefers_the_resolved_link(self):
        self.assertIn("a.original_link||a.link", landing.PAGE)

    def test_operator_actions_still_address_the_stored_link(self):
        """Hide and Pick key on the row's own link, so the resolution cannot break them."""
        self.assertIn("data-hide=\"'+esc(a.link)+'\"", page_build.SCRIPT)
        self.assertIn("data-picklink=\"'+esc(a.link)+'\"", page_build.SCRIPT)


class CollectorRead(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp.close()
        self.previous = core.DB_FILE
        core.DB_FILE = self.temp.name
        core._ORIGINALS.update({"loaded_at": 0.0, "map": {}})

    def tearDown(self):
        core.DB_FILE = self.previous
        core._ORIGINALS.update({"loaded_at": 0.0, "map": {}})
        # WAL leaves sidecars behind and Windows keeps the handle for a moment, so a failed
        # cleanup must not turn a passing check into an error.
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.temp.name + suffix)
            except OSError:
                pass

    def test_the_read_path_serves_the_cache_and_keeps_it_warm(self):
        connection = core.db_connect()
        try:
            google_news.remember(connection, {AGG: PUBLISHER})
        finally:
            connection.close()
        self.assertEqual(core.original_links(), {AGG: PUBLISHER})
        # A second call inside the TTL must not go back to the database, and a read failure
        # must keep the previous map rather than dropping every link to the aggregator.
        connection = sqlite3.connect(core.DB_FILE)
        connection.execute("DELETE FROM " + google_news.TABLE)
        connection.commit()
        connection.close()
        self.assertEqual(core.original_links(), {AGG: PUBLISHER})
        core._ORIGINALS["loaded_at"] = 0.0
        self.assertEqual(core.original_links(), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
