"""Six-hour bilingual event dedup on the feed and the published briefing source."""
import os
import sys
import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))
import live_news_dashboard as core
import semantic_event
import page_build
from collect_public import merge

NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def row(title, hours=0, region="글로벌", priority=4):
    return {"title": title, "link": "https://example.com/" + str(abs(hash(title))),
            "published_at": (NOW - timedelta(hours=hours)).isoformat(),
            "region": region, "priority": priority, "source": title}


class SemanticEvent(unittest.TestCase):
    def test_browser_and_server_share_bilingual_event_rules(self):
        pairs = [
            ("Trump imposes tariffs on China", "트럼프, 중국에 관세 부과", True),
            ("Trump imposes tariffs on China", "Trump delays tariffs on China", False),
            ("Trump delays tariffs on China", "트럼프 중국 관세 연기", True),
            ("Trump imposes tariffs on China", "트럼프 한국 관세 부과", False),
            ("Fed cuts interest rates", "연준 기준금리 인하", True),
            ("Fed cuts interest rates", "연준 기준금리 인상", False),
            ("Trump imposes tariffs on China 25%", "트럼프 중국 관세 10% 부과", False),
            ("Rain expected in Bangkok", "방콕에 비 예보", False),
        ]
        cases = [(row(a), row(b, 2), expected) for a, b, expected in pairs]
        cases.append((row(pairs[0][0]), row(pairs[0][1], 7), False))
        cases.append((row(pairs[0][0]), row(pairs[0][1], 2) |
                      {"published_at": "2026-09-30T12:00:00"}, False))
        source = page_build.render(public=True, datadir='', want_thai=False,
                                   icon_prefix='', admin=False)
        self.assertIn('function sameBriefingEvent(', source)
        # The generated browser rules, not a second handwritten regex table.
        script = semantic_event.browser_source() + '\nconsole.log(JSON.stringify(' + \
            'JSON.parse(process.argv[1]).map(([a,b])=>sameBriefingEvent(a,b))));'
        result = subprocess.run(['node', '-e', script,
                                 json.dumps([(a, b) for a, b, _ in cases], ensure_ascii=False)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [expected for _, _, expected in cases])
        self.assertEqual([semantic_event.same_event(a, b) for a, b, _ in cases],
                         [expected for _, _, expected in cases])

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
