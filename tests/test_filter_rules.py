"""Rules that keep a shape of story off the pages: what they take out, and what they give back.

The distinction this file holds: a rule is a filter, not a delete. A story a rule catches is
registered exactly as before and then skipped on every read path, its catch is recorded against the
rule, and the rule can be switched off - which returns every story it caught. A rule that is on by
default is one that is never read, so proposals from the operator's own hiding arrive switched off.

    python tests/test_filter_rules.py
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import live_news_dashboard as core  # noqa: E402

# The read paths this file checks are windowed (hours=24), so the fixture has to be recent: a pinned
# date ages out of the window and every rule looks like it caught nothing while the code is unchanged.
WHEN = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
DIGEST = "https://example.com/digest"
DIGEST2 = "https://example.com/digest-2"
OTHER = "https://example.com/other"
DIGEST_TITLE = "Bloomberg News Now is a comprehensive audio report of today's top stories"


def article(link, title, source="Bluesky · bloomberg.com", summary="본문"):
    return {"link": link, "title": title, "summary": summary, "source": source,
            "source_type": "news", "region": "글로벌", "category": "시장·가격",
            "categories": ["시장·가격"], "priority": 3, "published_at": WHEN,
            "collected_at": WHEN}


class Rules(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "news.db"
        self._original = core.DB_FILE
        core.DB_FILE = self.db
        core.init_db()
        core.insert_articles([article(DIGEST, DIGEST_TITLE),
                              article(DIGEST2, DIGEST_TITLE + " and more"),
                              article(OTHER, "Fed holds rates steady", source="Reuters",
                                      summary="The central bank left rates unchanged.")])

    def tearDown(self):
        core.DB_FILE = self._original

    def links(self, **kwargs):
        rows, _, _ = core.query_articles(hours=24, region="글로벌", **kwargs)
        return sorted(row["link"] for row in rows)

    def stored(self):
        connection = sqlite3.connect(str(self.db))
        try:
            return connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        finally:
            connection.close()

    def caught(self):
        return sorted(row["link"] for row in core.caught_links())

    # ── what a rule does to the pages ──────────────────────────────────
    def test_it_starts_with_no_rules(self):
        self.assertEqual(core.filter_rules(), [])

    def test_a_rule_that_is_off_changes_nothing(self):
        core.add_filter_rule("bloomberg news now")
        self.assertEqual(len(self.links()), 3)
        self.assertEqual(self.caught(), [])

    def test_a_rule_that_is_on_takes_its_stories_out_of_the_read_paths(self):
        core.add_filter_rule("bloomberg news now", enabled=True)
        self.assertEqual(self.links(), [OTHER], "both digests leave, the wire stays")

    def test_the_stories_are_still_registered(self):
        core.add_filter_rule("bloomberg news now", enabled=True)
        self.assertEqual(self.stored(), 3, "a rule is a filter, not a delete")

    def test_the_catch_is_recorded_against_the_rule(self):
        core.add_filter_rule("bloomberg news now", enabled=True)
        self.assertEqual(self.caught(), [DIGEST, DIGEST2])
        rule = core.filter_rules()[0]
        self.assertEqual(rule["hits"], 2, "the panel can say what a rule is doing")
        self.assertTrue(rule["last_hit_at"])

    def test_switching_the_rule_off_gives_the_stories_back(self):
        rule = core.add_filter_rule("bloomberg news now", enabled=True)["id"]
        self.assertEqual(len(self.links()), 1)
        core.set_filter_rule(rule, enabled=False)
        self.assertEqual(len(self.links()), 3)
        self.assertEqual(self.caught(), [], "the catches are cleared, not left to drift")

    def test_deleting_the_rule_gives_the_stories_back(self):
        rule = core.add_filter_rule("bloomberg news now", enabled=True)["id"]
        self.assertEqual(core.delete_filter_rule(rule), 0)
        self.assertEqual(len(self.links()), 3)

    def test_it_holds_against_the_other_filters(self):
        core.add_filter_rule("bloomberg news now", enabled=True)
        self.assertEqual(self.links(source="Bluesky · bloomberg.com"), [],
                         "not even asking for the source brings it back")
        self.assertEqual(self.links(text="bloomberg"), [])

    # ── the operator stays the judge ───────────────────────────────────
    def test_keeping_one_story_does_not_give_up_the_rule(self):
        core.add_filter_rule("bloomberg news now", enabled=True)
        core.keep_caught(DIGEST)
        self.assertEqual(self.links(), [DIGEST, OTHER], "the kept story is readable again")
        self.assertEqual(self.caught(), [DIGEST2], "the rule goes on doing its job")
        core.keep_caught(DIGEST, keep=False)
        self.assertEqual(len(self.links()), 1)

    def test_a_story_the_collector_sees_again_is_counted_once(self):
        core.add_filter_rule("bloomberg news now", enabled=True)
        core.insert_articles([article(DIGEST, DIGEST_TITLE)])
        self.assertEqual(core.filter_rules()[0]["hits"], 2, "not three")

    # ── matching ───────────────────────────────────────────────────────
    def test_a_latin_word_has_to_start_a_word(self):
        core.insert_articles([article("https://example.com/x", "A fascinating story", summary="no ads")])
        core.add_filter_rule("casino", enabled=True)
        self.assertEqual(len(self.links()), 4, "fascinating is not a casino")
        core.insert_articles([article("https://example.com/y", "Top Crypto Casinos for Bonuses",
                                      summary="trusted sites")])
        self.assertNotIn("https://example.com/y", self.links(), "casinos starts with casino")

    def test_korean_matches_through_a_particle(self):
        core.insert_articles([article("https://example.com/k", "코인니스 주간 에어드롭 안내",
                                      source="CoinNess", summary="이벤트")])
        core.add_filter_rule("에어드롭", enabled=True)
        self.assertNotIn("https://example.com/k", self.links(), "조사가 붙어도 같은 낱말이다")

    def test_switching_a_rule_on_acts_on_what_is_already_there(self):
        rule = core.add_filter_rule("bloomberg news now")["id"]      # arrives off
        self.assertEqual(len(self.links()), 3)
        core.set_filter_rule(rule, enabled=True)
        self.assertEqual(self.links(), [OTHER], "turning it on cannot wait for tomorrow's stories")

    def test_rewording_a_rule_keeps_it_honest(self):
        rule = core.add_filter_rule("bloomberg news now", enabled=True)["id"]
        core.set_filter_rule(rule, pattern="fed holds rates")
        self.assertEqual(self.links(), [DIGEST, DIGEST2], "the old pattern's catches come back")
        self.assertEqual(self.caught(), [OTHER])

    def test_an_empty_pattern_is_refused(self):
        with self.assertRaises(ValueError):
            core.add_filter_rule("   ")

    def test_the_same_pattern_twice_does_not_flip_it(self):
        first = core.add_filter_rule("bloomberg news now", enabled=True)
        again = core.add_filter_rule("bloomberg news now")
        self.assertEqual(again["enabled"], True, "adding it again leaves it switched on")
        self.assertEqual(len(core.filter_rules()), 1)


class Learning(unittest.TestCase):
    """What the operator's own hiding teaches: the recurring shapes, and only those."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "news.db"
        self._original = core.DB_FILE
        core.DB_FILE = self.db
        core.init_db()
        core.insert_articles([article(DIGEST, DIGEST_TITLE),
                              article(DIGEST2, DIGEST_TITLE + " and more"),
                              article(OTHER, "US retail sales rose in August by more than expected",
                                      source="Reuters", summary="Retail sales beat forecasts.")])
        core.hide_link(DIGEST, DIGEST_TITLE)
        core.hide_link(DIGEST2, DIGEST_TITLE + " and more")

    def tearDown(self):
        core.DB_FILE = self._original

    def test_the_recurring_shape_is_proposed(self):
        core.learn_filter_rules()
        patterns = [rule["pattern"] for rule in core.filter_rules()]
        self.assertTrue(any("bloomberg news now" in p for p in patterns),
                        "the title of both hidden stories: %s" % patterns)

    def test_proposals_arrive_switched_off(self):
        core.learn_filter_rules()
        rules = core.filter_rules()
        self.assertTrue(rules)
        self.assertTrue(all(not rule["enabled"] for rule in rules),
                        "a rule that is never read is one the operator cannot judge")
        self.assertTrue(all(rule["origin"] == "learned" for rule in rules))
        rows, _, _ = core.query_articles(hours=24, region="글로벌")
        self.assertEqual(len(rows), 1, "nothing is filtered until it is switched on")

    def test_it_does_not_propose_a_word_the_whole_feed_uses(self):
        core.learn_filter_rules()
        patterns = [rule["pattern"] for rule in core.filter_rules()]
        self.assertNotIn("august", patterns)
        self.assertNotIn("retail sales", patterns)

    def test_it_does_not_propose_the_same_pattern_twice(self):
        core.learn_filter_rules()
        before = len(core.filter_rules())
        core.learn_filter_rules()
        self.assertEqual(len(core.filter_rules()), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
