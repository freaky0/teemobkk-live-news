"""Six-hour bilingual event dedup on the feed and the published briefing source."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))
import live_news_dashboard as core
import semantic_event
from collect_public import merge

NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def row(title, hours=0, region="글로벌", priority=4):
    return {"title": title, "link": "https://example.com/" + str(abs(hash(title))),
            "published_at": (NOW - timedelta(hours=hours)).isoformat(),
            "region": region, "priority": priority, "source": title}


class SemanticEvent(unittest.TestCase):
    def test_translations_and_sources_unify_in_both_feed_paths(self):
        english = row("Trump imposes tariffs on China")
        korean = row("트럼프, 중국에 관세 부과", 2)
        self.assertTrue(semantic_event.same_event(english, korean))
        self.assertEqual(core.dedupe_rows([english, korean]), [english])
        self.assertEqual(core.dedupe([dict(english), dict(korean)]), [english])

    def test_boundary_and_distinct_events(self):
        first = row("Trump imposes tariffs on China")
        self.assertTrue(semantic_event.same_event(first, row("트럼프 중국 관세 부과", 6)))
        self.assertFalse(semantic_event.same_event(first, row("트럼프 중국 관세 부과", 7)))
        for title in ("Trump delays tariffs on China", "Trump imposes tariffs on Korea",
                      "Fed cuts interest rates", "China announces tariffs"):
            with self.subTest(title=title):
                self.assertFalse(semantic_event.same_event(first, row(title, 1)))
        self.assertEqual(len(core.dedupe_rows([first, row("트럼프 중국 관세 부과", 7)])), 2)

    def test_rate_direction_and_material_values(self):
        self.assertTrue(semantic_event.same_event(row("Fed cuts interest rates"),
                                                  row("연준 기준금리 인하", 1)))
        self.assertFalse(semantic_event.same_event(row("Fed cuts interest rates"),
                                                   row("연준 기준금리 인상", 1)))
        self.assertFalse(semantic_event.same_event(row("Fed cuts interest rates 0.25%"),
                                                   row("연준 기준금리 0.5% 인하", 1)))

    def test_region_scope_unknown_events_and_bad_timestamps(self):
        first = row("Trump imposes tariffs on China")
        korean = row("트럼프 중국 관세 부과", 1, "태국")
        self.assertEqual(len(core.dedupe_rows([first, korean])), 2)
        self.assertFalse(semantic_event.same_event(first, row("트럼프 중국 관세 부과", 1) | {"published_at": "unknown"}))
        self.assertIsNone(semantic_event.signature("Rain expected in Bangkok"))

    def test_published_merge_removes_previous_duplicates(self):
        # The merged JSON is the input for static page news feed and briefing.
        from unittest.mock import patch
        with patch("collect_public.datetime") as clock:
            clock.now.return_value = NOW
            clock.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            rows = merge([row("트럼프 중국 관세 부과", 2)], [row("Trump imposes tariffs on China")])
        self.assertEqual([entry["title"] for entry in rows], ["Trump imposes tariffs on China"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
