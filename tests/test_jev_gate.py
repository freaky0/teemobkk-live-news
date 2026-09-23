import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "deploy"))

import jev_gate  # type: ignore[import-not-found]  # noqa: E402


ITEMS = [
    {
        "link": "https://example.com/a",
        "title": "미국 법무부, 바이낸스 이란 제재 위반 조사",
        "summary": "미국 법무부가 바이낸스의 이란 제재 위반 여부를 조사한다.",
        "source": "Google News · 지정학",
        "published_at": "2026-09-22T02:00:00+00:00",
        "_age_minutes": 20.0,
    },
    {
        "link": "https://example.com/b",
        "title": "연방 검찰, 바이낸스 이란 제재 위반 조사",
        "summary": "연방 검찰이 같은 제재 위반 의혹을 조사한다.",
        "source": "Google News · 지정학",
        "published_at": "2026-09-22T02:02:00+00:00",
        "_age_minutes": 18.0,
    },
]


class JEVGate(unittest.TestCase):
    def setUp(self):
        self.original_mode = jev_gate.MODE
        self.original_key = os.environ.get("JEV_API_KEY")
        jev_gate.MODE = "live"
        os.environ["JEV_API_KEY"] = "test-only-not-sent"

    def tearDown(self):
        jev_gate.MODE = self.original_mode
        if self.original_key is None:
            os.environ.pop("JEV_API_KEY", None)
        else:
            os.environ["JEV_API_KEY"] = self.original_key

    def raw_answers(self):
        return {
            "answers": {
                "item_1_importance": {"choice": "high"},
                "item_1_duplicate": {"noul": 0.12},
                "item_1_freshness": {"choice": "fresh"},
                "item_2_importance": {"choice": "medium"},
                "item_2_duplicate": {"noul": 0.95},
                "item_2_freshness": {"choice": "aging"},
            },
            "model": "jev-test",
        }

    def test_build_payload_has_three_typed_questions_per_candidate(self):
        payload = jev_gate.build_payload(
            ITEMS,
            ["Earlier channel headline"],
            datetime(2026, 9, 22, 2, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(6, len(payload["questions"]))
        self.assertEqual("choice", payload["questions"]["item_1_importance"]["type"])
        self.assertEqual("noul", payload["questions"]["item_2_duplicate"]["type"])

    @patch.object(jev_gate, "_call")
    def test_evaluate_parses_importance_duplicate_and_freshness(self, call):
        call.return_value = self.raw_answers()
        result = jev_gate.evaluate(ITEMS, ["Earlier channel headline"], datetime.now(timezone.utc))
        self.assertFalse(result.fallback)
        self.assertEqual("high", result.decisions[ITEMS[0]["link"]].importance)
        self.assertAlmostEqual(0.95, result.decisions[ITEMS[1]["link"]].duplicate_confidence)
        self.assertEqual("aging", result.decisions[ITEMS[1]["link"]].freshness)
        call.assert_called_once()

    @patch.object(jev_gate, "_call")
    def test_failure_returns_deterministic_fallback(self, call):
        call.side_effect = jev_gate.JEVError("timeout")
        result = jev_gate.evaluate(ITEMS, [], datetime.now(timezone.utc))
        self.assertTrue(result.fallback)
        self.assertEqual({}, result.decisions)
        self.assertIn("timeout", result.error)

    def test_only_high_confidence_duplicate_blocks_priority4(self):
        decision = jev_gate.Decision("x", "medium", 0.85, "aging", {})
        self.assertTrue(jev_gate.should_block_duplicate(decision, 4, False))
        self.assertFalse(jev_gate.should_block_duplicate(decision, 5, False))
        self.assertFalse(jev_gate.should_block_duplicate(decision, 4, True))


class AltNoiseFilter(unittest.TestCase):
    def item(self, title, asset="시장", category="일반", priority=4):
        return {
            "title": title,
            "summary": "",
            "asset": asset,
            "priority": priority,
            "category": category,
            "categories": [category],
            "channel_pick": False,
        }

    def test_plain_near_is_not_an_altcoin_ticker(self):
        item = self.item("Bitcoin ETF inflows near $1B", asset="BTC", category="ETF·수급")
        self.assertFalse(jev_gate.is_single_alt_notice(item))

    def test_plain_optimism_is_not_an_altcoin_ticker(self):
        item = self.item("Geopolitical Optimism Supports Market Sentiment")
        self.assertFalse(jev_gate.is_single_alt_notice(item))

    def test_major_asset_mention_exempts_mixed_altcoin_headline(self):
        item = self.item("Bitcoin and XRP exchange listing update", asset="BTC")
        self.assertFalse(jev_gate.is_single_alt_notice(item))

    def test_unambiguous_dollar_ticker_still_matches(self):
        item = self.item("$NEAR ecosystem update")
        self.assertTrue(jev_gate.is_single_alt_notice(item))

    def test_explicit_asset_field_ticker_still_matches(self):
        item = self.item("Token ecosystem update", asset="NEAR")
        self.assertTrue(jev_gate.is_single_alt_notice(item))

    def test_unambiguous_altcoin_symbol_still_matches(self):
        item = self.item("Solana ecosystem update")
        self.assertTrue(jev_gate.is_single_alt_notice(item))


if __name__ == "__main__":
    unittest.main(verbosity=2)
