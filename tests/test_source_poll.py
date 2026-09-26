"""Every RSS source gets asked - the slower-poll rule must not park a source forever.

The bug this covers (2026-09-20 to 09-26): the cycle picked its jobs with
`turn % SLOW_SOURCES.get(name, 1) == 1`. For a source with no slower poll that is `turn % 1 == 1`,
which never matches, because the remainder of a division by 1 is always 0. The result was that
every RSS source except FinancialJuice - all six crypto/macro wires, both Bangkok Post feeds,
Khaosod English, Thai Enquirer, Prachatai English, Thairath, Matichon - was left out of *every*
cycle while the operator panel carried them as `ok: true, count: 0` under the note "slower poll:
not asked this cycle". The Thailand tab was 100% Google News for six days and nothing looked
broken, because a source that is never asked and a source that answers nothing render the same.

Three facts are locked here: the sources without a slower poll are asked every cycle, the one on a
slower poll is asked on its cadence and not more often, and no source ever falls out of the plan.

    python tests/test_source_poll.py
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import live_news_dashboard as core  # noqa: E402


def asked_names(turn):
    asked, _sat_out = core.poll_plan(turn)
    return [job[0] for job in asked]


class PollPlanTest(unittest.TestCase):
    def setUp(self):
        self.every_cycle = [name for name, _kind, _url in core.RSS_SOURCES + core.THAI_RSS_SOURCES
                            if name not in core.SLOW_SOURCES]
        self.slowed = [name for name in core.SLOW_SOURCES]

    def test_no_source_is_parked(self):
        """Every source - Thai feeds included - is asked inside the first ten cycles."""
        seen = set()
        for turn in range(1, 11):
            seen.update(asked_names(turn))
        expected = {name for name, _kind, _url in core.RSS_SOURCES + core.THAI_RSS_SOURCES}
        self.assertEqual(set(), expected - seen, "한 번도 묻지 않는 소스: %s" % (expected - seen))

    def test_plain_sources_are_asked_every_cycle(self):
        """A source with no slower poll cannot miss a cycle; this is the case that broke."""
        self.assertTrue(self.every_cycle, "SLOW_SOURCES 밖 소스가 하나도 없다")
        for turn in range(1, 31):
            missing = [name for name in self.every_cycle if name not in asked_names(turn)]
            self.assertEqual([], missing, "turn %d 에 빠진 소스: %s" % (turn, missing))

    def test_thai_feeds_are_in_the_plan(self):
        """Every Thai feed rides the same plan as the crypto wires.

        The roster grows as feeds are adopted (21 entries as of the 2026-09-26 adoption), so the
        count is not pinned - what is pinned is that whatever is listed is actually asked, and that
        no two entries share a name, because the name is the status row, the pill and the push
        history's identity.
        """
        thai = [name for name, _kind, _url in core.THAI_RSS_SOURCES]
        names = [name for name, _kind, _url in core.RSS_SOURCES + core.THAI_RSS_SOURCES]
        self.assertEqual(len(names), len(set(names)), "이름이 겹치는 소스가 있다")
        self.assertGreaterEqual(len(thai), 7, "태국 피드가 7곳 아래로 줄었다")
        for name in thai:
            self.assertIn(name, asked_names(1), "%s 가 첫 사이클에 없다" % name)

    def test_slower_poll_keeps_its_interval(self):
        """A slower-poll source is asked every Nth cycle - on its cadence, not never, not always."""
        for name, interval in core.SLOW_SOURCES.items():
            turns = [turn for turn in range(1, 41) if name in asked_names(turn)]
            self.assertEqual([t for t in range(1, 41) if t % interval == 0], turns,
                             "%s 의 주기 %d 회" % (name, interval))

    def test_plan_is_a_partition(self):
        """Asked + sat out covers every source exactly once, so no job is dropped or doubled."""
        for turn in range(1, 21):
            asked, sat_out = core.poll_plan(turn)
            self.assertEqual(len(asked) + len(sat_out),
                             len(core.RSS_SOURCES) + len(core.THAI_RSS_SOURCES), "turn %d" % turn)
            self.assertEqual(set(), set(asked) & set(sat_out), "turn %d 에 겹친 job" % turn)

    def test_regions_are_kept(self):
        """Thai feeds are filed under the Thailand region and the wires stay global.

        Turn 5 is a cycle every source is present in: the slower poll is a multiple of 5.
        """
        asked, _sat_out = core.poll_plan(5)
        regions = {job[0]: job[3] for job in asked}
        self.assertEqual(len(core.RSS_SOURCES) + len(core.THAI_RSS_SOURCES), len(regions))
        for name, _kind, _url in core.THAI_RSS_SOURCES:
            self.assertEqual(core.THAI_REGION, regions[name], name)
        for name, _kind, _url in core.RSS_SOURCES:
            self.assertEqual(core.GLOBAL_REGION, regions[name], name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
