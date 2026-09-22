"""The channel's frozen shape, and the check that keeps it frozen.

The channel is fed by two pipelines - the one-minute timer in `deploy/tg_push.py` and the VPS
agent that picks stories with a model - and both of them now render through `render()`. What this
file locks down is the part that made the channel look inconsistent before: the exact lines of the
post, in order, with one link style and one footer, and a `validate_post()` that refuses anything
else. The regression samples at the bottom are the shapes the channel actually carried (a markdown
link post and the older `#태그` + `(@url:)` post); they must keep failing.

    python tests/test_tg_push_format.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))

os.environ.setdefault("TG_TIMEZONE", "ICT")
# The channel's label, confirmed 2026-09-22. Pinned here so the test does not silently follow a
# changed default: the frozen shape is a decision and this file is what records it.
os.environ["TG_NOTE_LABEL"] = "Teemo's Note"

import live_news_dashboard as core  # noqa: E402
import tg_push  # noqa: E402

LINK = "https://example.com/story"

ITEM = {
    "link": LINK,
    "title": "소프트뱅크, 110억 달러 정크본드 발행 추진",
    "summary": "소프트뱅크그룹이 110억 달러 이상 규모의 채권 발행을 추진하고 있다.",
    "source": "CoinNess",
    "asset": "BTC",
    "priority": 4,
    "published_at": "2026-09-21T02:00:00+00:00",
    "categories": "시장·가격,비트코인",
}

TITLE = "소프트뱅크, 110억 달러 정크본드 발행 추진"
BODY = "소프트뱅크그룹이 110억 달러 규모의 달러·유로 채권 발행을 추진하고 있다."
NOTE = "조달 자금이 오픈AI 후속 투자에 쓰일 수 있다."
TAGS = ["소프트뱅크", "오픈AI", "정크본드"]

# The golden sample. Written out by hand on purpose: this is the shape the channel posts, and a
# test that builds the expectation by calling the same renderer proves nothing.
GOLDEN = (
    "[기사] 소프트뱅크, 110억 달러 정크본드 발행 추진\n"
    "\n"
    "소프트뱅크그룹이 110억 달러 규모의 달러·유로 채권 발행을 추진하고 있다.\n"
    "\n"
    "Teemo's Note : 조달 자금이 오픈AI 후속 투자에 쓰일 수 있다.\n"
    "\n"
    "관련 : $BTC\n"
    "#소프트뱅크 #오픈AI #정크본드\n"
    "2026-09-21 09:00:00 ICT\n"
    "\n"
    "출처: https://example.com/story\n"
    "TeemoBKK 라이브 뉴스 (https://teemobkk.io/news/)"
)

# Shapes this channel really carried. Each one has to stay broken.
MARKDOWN_POST = (
    "[속보] 비트코인, ETF 자금 유입 전환에 84.8K 돌파\n"
    "\n"
    "비트코인이 미국 현물 ETF 자금 흐름이 순유입으로 전환된 뒤 84.8K를 넘어섰다.\n"
    "\n"
    "TeemoBKK's Note : ETF 수급이 실제 순유입으로 이어지는지가 핵심 변수다.\n"
    "\n"
    "관련 : $BTC\n"
    "#비트코인 #ETF #기관수급\n"
    "2026-09-22 06:16 ICT\n"
    "\n"
    "[출처](https://www.bloomberg.com/news/articles/x)\n"
    "[TeemoBKK 라이브 뉴스](https://teemobkk.io/news)"
)

OLD_DEPLOYED_POST = (
    "#기사 소프트뱅크, 110억 달러 정크본드 발행 추진\n"
    "\n"
    "소프트뱅크그룹이 110억 달러 규모의 채권 발행을 추진하고 있다.\n"
    "\n"
    "Teemo's Note : 조달 자금이 후속 투자에 쓰일 수 있다.\n"
    "\n"
    "#소프트뱅크, #오픈AI, #정크본드\n"
    "출처 CoinNess · (@url:`https://coinness.com/stock-news/127661/quote`) | 2026-09-21 09:05:20\n"
    "TeemoBKK Live News (@url:`https://teemobkk.io/news`)"
)


def frozen(item=None, priority=None):
    item = dict(item or ITEM)
    if priority is not None:
        item["priority"] = priority
    return tg_push.render(item, TITLE, BODY, NOTE, TAGS)


class GoldenShape(unittest.TestCase):
    def test_render_matches_the_golden_sample(self):
        self.assertEqual(GOLDEN, frozen())

    def test_golden_sample_passes_the_shape_check(self):
        self.assertEqual([], tg_push.validate_post(GOLDEN))

    def test_a_pick_gets_its_own_tag(self):
        item = dict(ITEM)
        item["channel_pick"] = True
        text = tg_push.render(item, TITLE, BODY, NOTE, TAGS)
        self.assertTrue(text.startswith("[티모의 선택] 소프트뱅크"), text.splitlines()[0])
        self.assertEqual([], tg_push.validate_post(text))

    def test_a_breaking_story_gets_the_breaking_tag(self):
        self.assertTrue(frozen(priority=5).startswith("[속보] "))

    def test_the_shape_carries_one_link_style_only(self):
        text = frozen()
        self.assertNotIn("](", text)
        self.assertNotIn("@url:", text)
        self.assertIn("출처: https://example.com/story", text)

    def test_the_footer_keeps_its_link_when_the_env_is_empty(self):
        original = tg_push.CHANNEL_LINK
        try:
            tg_push.CHANNEL_LINK = "https://teemobkk.io/news/"
            self.assertIn("TeemoBKK 라이브 뉴스 (https://teemobkk.io/news/)", frozen())
        finally:
            tg_push.CHANNEL_LINK = original


class ShapeCheck(unittest.TestCase):
    def test_it_reports_one_problem_per_broken_line(self):
        broken = "\n".join(["[기사] 제목", "", "본문", "", "출처: https://example.com/x",
                            "TeemoBKK 라이브 뉴스 (https://teemobkk.io/news/)"])
        joined = " | ".join(tg_push.validate_post(broken, require_note=True))
        self.assertIn("Note", joined)
        self.assertIn("hashtag", joined)
        self.assertIn("ZONE", joined)

    def test_the_old_renderers_shapes_are_still_rejected(self):
        for text, expected in ((MARKDOWN_POST, "markdown link"),
                               (OLD_DEPLOYED_POST, "hash-tag first line"),
                               (OLD_DEPLOYED_POST, "(@url:) wrapper")):
            with self.subTest(expected=expected):
                self.assertIn(expected, " | ".join(tg_push.validate_post(text)))

    def test_a_two_tag_title_line_is_rejected(self):
        text = GOLDEN.replace("[기사] 소프트뱅크", "[속보, 기사] 소프트뱅크")
        self.assertIn("two tags", " | ".join(tg_push.validate_post(text)))

    def test_a_missing_tag_line_is_rejected(self):
        text = GOLDEN.replace("#소프트뱅크 #오픈AI #정크본드", "")
        self.assertIn("hashtag", " | ".join(tg_push.validate_post(text)))

    def test_more_than_four_tags_is_rejected(self):
        text = GOLDEN.replace("#소프트뱅크 #오픈AI #정크본드", "#가 #나 #다 #라 #마")
        self.assertIn("hashtag", " | ".join(tg_push.validate_post(text)))

    def test_the_note_line_is_optional_for_the_timer_and_required_for_the_agent(self):
        text = "\n".join(line for line in GOLDEN.split("\n")
                         if not line.startswith(tg_push.NOTE_LABEL))\
            .replace("\n\n\n", "\n\n")
        self.assertEqual([], tg_push.validate_post(text))
        self.assertIn("Note", " | ".join(tg_push.validate_post(text, require_note=True)))

    def test_lines_out_of_order_are_rejected(self):
        lines = GOLDEN.split("\n")
        notes = [i for i, line in enumerate(lines) if line.startswith(tg_push.NOTE_LABEL)][0]
        tags = [i for i, line in enumerate(lines) if line.startswith("#소프트뱅크")][0]
        lines[notes], lines[tags] = lines[tags], lines[notes]
        self.assertIn("order", " | ".join(tg_push.validate_post("\n".join(lines))))


class TagsLine(unittest.TestCase):
    def test_a_full_editor_answer_is_left_alone(self):
        self.assertEqual(["비트코인", "ETF", "정크본드"],
                         tg_push.merge_tags(["비트코인", "ETF", "정크본드"], ["시장·가격", "비트코인"]))

    def test_stored_categories_top_up_only_to_the_minimum(self):
        self.assertEqual(["비트코인", "시장가격"],
                         tg_push.merge_tags(["비트코인"], ["시장·가격", "비트코인", "ETF"]))
        self.assertEqual(["시장가격", "비트코인"],
                         tg_push.merge_tags([], ["시장·가격", "비트코인", "ETF"]))

    def test_it_never_repeats_a_tag_and_stops_at_four(self):
        self.assertEqual(["비트코인", "ETF"],
                         tg_push.merge_tags(["비트코인", "#비트코인", "ETF"], []))
        self.assertEqual(4, len(tg_push.merge_tags(["가", "나", "다", "라", "마"], [])))


class AgentFixture(unittest.TestCase):
    """A database with one stored article, and dry-run on, for the agent paths."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._original_db = core.DB_FILE
        core.DB_FILE = Path(self.dir) / "news.db"
        core.init_db()
        self.connection = tg_push.connect()
        self._original_dry = tg_push.DRY_RUN
        tg_push.DRY_RUN = True
        self.connection.execute(
            "INSERT OR REPLACE INTO articles (link, title, summary, source, source_type, region,"
            " category, asset, priority, published_at, collected_at, categories)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (LINK, ITEM["title"], ITEM["summary"], ITEM["source"], "news", "글로벌",
             "시장·가격", "BTC", 4, ITEM["published_at"], ITEM["published_at"],
             ITEM["categories"]))
        self.connection.commit()

    def tearDown(self):
        tg_push.DRY_RUN = self._original_dry
        self.connection.close()
        core.DB_FILE = self._original_db

    def parts(self, **overrides):
        data = {"link": LINK, "title": TITLE, "body": BODY, "note": NOTE, "tags": TAGS}
        data.update(overrides)
        return data


class AgentPath(AgentFixture):
    """The agent supplies words; this script supplies the shape."""

    def test_the_agent_post_comes_out_in_the_frozen_shape(self):
        ok, text = tg_push.post_parts(self.connection, self.parts())
        self.assertTrue(ok, text)
        self.assertEqual(GOLDEN, text)
        self.assertEqual([], tg_push.validate_post(text))

    def test_a_link_that_is_not_in_the_database_is_refused(self):
        ok, why = tg_push.post_parts(self.connection, self.parts(link="https://example.com/nope"))
        self.assertFalse(ok)
        self.assertIn("news.db", why)

    def test_a_post_without_a_note_is_refused_by_the_shape_check(self):
        ok, why = tg_push.post_parts(self.connection, self.parts(note=""))
        self.assertFalse(ok)
        self.assertIn("shape check failed", why)

    def test_a_second_post_of_the_same_link_is_refused(self):
        self.connection.execute(
            "INSERT INTO tg_posted (link, posted_at, mode) VALUES (?,?,?)",
            (LINK, "2026-09-21T02:00:00+00:00", "agent"))
        self.connection.commit()
        ok, why = tg_push.post_parts(self.connection, self.parts())
        self.assertFalse(ok)
        self.assertIn("already posted", why)


class OutboxDrain(AgentFixture):
    """The container cannot call the pusher: it queues JSON parts, the host drains them."""

    def outbox(self):
        directory = Path(self.dir) / "tg_outbox"
        directory.mkdir(exist_ok=True)
        return directory

    def test_a_queued_file_is_rendered_and_reported(self):
        outbox = self.outbox()
        (outbox / "one.json").write_text(json.dumps(self.parts(), ensure_ascii=False),
                                         encoding="utf-8")
        posted, held = tg_push.drain_outbox(self.connection, outbox)
        self.assertEqual((1, 0), (posted, held))
        # The queue is only archived when the post was really sent: in a dry run the file stays,
        # which is what keeps --dry-run a read-only check.
        self.assertTrue((outbox / "one.json").exists())

    def test_a_file_that_cannot_be_posted_moves_out_of_the_watch_directory(self):
        outbox = self.outbox()
        (outbox / "bad.json").write_text(
            json.dumps(self.parts(link="https://example.com/absent"), ensure_ascii=False),
            encoding="utf-8")
        # Safe without dry run: a link that is not in the archive is refused before any send.
        tg_push.DRY_RUN = False
        posted, held = tg_push.drain_outbox(self.connection, outbox)
        self.assertEqual((0, 1), (posted, held))
        # Out of the queue, kept for a human: a file left in place keeps the path unit
        # triggering until systemd's start limit fails both units.
        self.assertFalse((outbox / "bad.json").exists())
        self.assertTrue((outbox / "failed" / "bad.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
