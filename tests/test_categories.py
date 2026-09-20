"""Data-layer checks for multi-label categories.

The stored value is a comma-joined list, so three things can go wrong quietly and each one has a
check here: a headline that matches two axes must carry both, the filter must answer for a
secondary axis, and the delimiter must do the work so a partial name cannot match.

Category names are read out of the rules table by one of their terms instead of being typed into
this file: a hand-typed name is the thing most likely to be wrong, and it would then "prove" the
implementation correct against a string this test invented.

    python tests/test_categories.py
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import category_rules as taxonomy  # noqa: E402
import live_news_dashboard as core  # noqa: E402


def axis(*terms):
    """The category whose rule owns all of `terms`."""
    for name, own in taxonomy.GLOBAL_RULES:
        if all(term in own for term in terms):
            return name
    raise AssertionError("no axis owns %s" % (terms,))


POLICY = axis("tariff")
TRUMP = axis("trump")
RATES = axis("interest rate")


class MultiLabel(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._original_db = core.DB_FILE
        core.DB_FILE = os.path.join(self.dir, "t.db")
        core.init_db()

    def tearDown(self):
        core.DB_FILE = self._original_db

    def fresh(self, minutes_ago=5):
        return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()

    def test_a_headline_matching_two_axes_carries_both(self):
        article = core.make_article("Trump signs tariff bill on China", "https://e.test/1", "",
                                    self.fresh(), "Src", "media")
        self.assertIn(POLICY, article["categories"])
        self.assertIn(TRUMP, article["categories"])
        self.assertEqual(article["category"], article["categories"][0],
                         "the stored single value must stay the first of the list")

    def test_the_filter_answers_for_a_secondary_axis(self):
        article = core.make_article("Trump signs tariff bill on China", "https://e.test/2", "",
                                    self.fresh(), "Src", "media")
        core.insert_articles([article])
        rows, total, _ = core.query_articles(hours=24, category=TRUMP, limit=10)
        self.assertEqual(total, 1, "a story filed under another axis must still answer this one")
        self.assertEqual(rows[0]["link"], "https://e.test/2")
        self.assertIsInstance(rows[0]["categories"], list)

    def test_a_partial_name_does_not_match(self):
        article = core.make_article("Trump signs tariff bill on China", "https://e.test/3", "",
                                    self.fresh(), "Src", "media")
        core.insert_articles([article])
        _, total, _ = core.query_articles(hours=24, category=POLICY[:-1], limit=10)
        self.assertEqual(total, 0, "the comma delimiters must be what makes a name match")

    def test_a_row_written_before_the_column_still_filters(self):
        connection = sqlite3.connect(core.DB_FILE)
        connection.execute(
            "INSERT INTO articles (link, title, summary, source, source_type, region, category, "
            "categories, asset, priority, published_at, collected_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("https://e.test/4", "old row", "", "Src", "media", core.GLOBAL_REGION, POLICY, None,
             "BTC", 3, self.fresh(), self.fresh()))
        connection.commit()
        connection.close()
        _, total, _ = core.query_articles(hours=24, category=POLICY, limit=10)
        self.assertEqual(total, 1, "a NULL list must fall back to the single stored value")

    def test_the_pill_table_matches_the_taxonomy(self):
        """The screen's stored values must be exactly the rule names.

        A mismatch is a pill that filters nothing, and this is also where a non-ASCII name that
        lost characters on write would show up: the pill table and the rules are separate files.
        """
        import ui_text
        self.assertEqual({value for value, _ in ui_text.CATS["global"]},
                         {taxonomy.GENERIC_CATEGORY} | {name for name, _ in taxonomy.GLOBAL_RULES})
        self.assertEqual({value for value, _ in ui_text.CATS["thai"]},
                         {taxonomy.GENERIC_CATEGORY} | {name for name, _ in taxonomy.THAI_RULES})

    def test_every_pill_has_a_label_in_both_languages(self):
        import ui_text
        for lang in ("ko", "en"):
            labels = ui_text.cat_labels(lang)
            for value, name in ui_text.CATS["global"] + ui_text.CATS["thai"]:
                self.assertIn(value, labels, "%s is missing a %s label" % (name, lang))

    def test_the_published_files_carry_only_real_category_names(self):
        """The generated JSON is data on the public site: a name that is not in the table is a chip
        that filters nothing. Skips when the files have not been generated in this checkout.
        """
        import json
        valid = taxonomy.valid_names()
        checked = 0
        for name in ("global.json", "thai.json", "global-recent.json", "thai-recent.json"):
            path = os.path.join(ROOT, "docs", name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            for row in payload.get("articles") or []:
                labels = row.get("categories")
                self.assertIsInstance(labels, list, "%s: %s is not a list" % (name, row.get("link")))
                self.assertTrue(labels, "%s: %s has an empty list" % (name, row.get("link")))
                for label in labels:
                    self.assertIn(label, valid, "%s: %r is not a category" % (name, label))
                self.assertEqual(row.get("category"), labels[0],
                                 "%s: the single value must be the first label" % name)
                checked += 1
        self.assertGreater(checked, 0, "no published file was found to check")

    def test_no_category_name_contains_a_comma(self):
        for name, _ in list(taxonomy.GLOBAL_RULES) + list(taxonomy.THAI_RULES):
            self.assertNotIn(",", name)

    def test_the_reader_accepts_a_list_as_well_as_the_stored_string(self):
        """The DB layer hands out a list; a row read from the table is a string.

        Accepting only the string turned a list into its own repr, which reached the screen as a
        chip reading "['일반']" - so both shapes are pinned here.
        """
        self.assertEqual(taxonomy.split_categories([POLICY, TRUMP]), [POLICY, TRUMP])
        self.assertEqual(taxonomy.split_categories(taxonomy.join_categories([POLICY, TRUMP])),
                         [POLICY, TRUMP])
        self.assertEqual(taxonomy.split_categories([POLICY, POLICY]), [POLICY], "no duplicates")
        for shape in ([POLICY, TRUMP], taxonomy.join_categories([POLICY, TRUMP])):
            for name in taxonomy.split_categories(shape):
                self.assertIn(name, taxonomy.valid_names())

    def test_every_name_this_module_returns_is_a_real_category(self):
        for shape in ("", None, [POLICY], "unknown·" + RATES, [POLICY, POLICY]):
            for name in taxonomy.split_categories(shape):
                self.assertIn(name, taxonomy.valid_names(),
                              "%r produced the unknown name %r" % (shape, name))

    def test_stored_string_round_trips(self):
        names = [POLICY, TRUMP]
        self.assertEqual(taxonomy.split_categories(taxonomy.join_categories(names)), names)

    def test_a_renamed_category_is_normalised_wherever_it_is_read(self):
        """A name the table no longer offers maps onto the axis that replaced it.

        The input is built from a current name plus a word the table does not know, which is the
        shape a rename leaves behind - no historical name is typed into this test, so it cannot
        pass by comparing two copies of the same mistake.
        """
        self.assertEqual(taxonomy.retire(RATES), RATES, "a current name must pass through")
        for retired in ("unknown·" + RATES, RATES + "·unknown", "unknown·" + RATES + "·unknown2"):
            self.assertEqual(taxonomy.retire(retired), RATES)
        self.assertEqual(taxonomy.retire("완전히 다른 이름"), "완전히 다른 이름",
                         "an unknown name is left alone rather than guessed at")
        self.assertEqual(taxonomy.split_categories("unknown·" + RATES, None), [RATES])
        self.assertEqual(taxonomy.split_categories("", None), [taxonomy.GENERIC_CATEGORY])

    def test_empty_list_falls_back_to_the_generic_category(self):
        article = core.make_article("zzz nothing matches zzz", "https://e.test/5", "",
                                    self.fresh(), "Src", "media")
        self.assertEqual(article["categories"], [taxonomy.GENERIC_CATEGORY])
        self.assertEqual(article["category"], taxonomy.GENERIC_CATEGORY)

    def test_thai_rows_keep_their_own_table(self):
        article = core.make_article("pm2.5 dust warning in Bangkok", "https://e.test/6", "",
                                    self.fresh(), "Src", "media", region=core.THAI_REGION)
        thai_names = {name for name, _ in taxonomy.THAI_RULES}
        self.assertTrue(set(article["categories"]) <= thai_names | {taxonomy.GENERIC_CATEGORY},
                        "a Thai row must not pick up a global axis: %s" % (article["categories"],))


if __name__ == "__main__":
    unittest.main(verbosity=2)
