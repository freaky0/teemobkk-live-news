"""The channel's frozen shape, and the check that keeps it frozen.

The channel is fed by the one-minute timer and an optional outbox bridge, but both paths now render through `render()`. What this file locks down is the exact approved shape: one bracket tag, factual body, `Teemo's Note`, related hashtags, an `@url:` source line with ICT time, and the Korean footer. Legacy markdown links, raw source lines, and English footer variants must keep failing.

    python tests/test_tg_push_format.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "deploy"))

os.environ.setdefault("TG_TIMEZONE", "ICT")
# The channel's format is fixed in tg_push.py; a stale TG_NOTE_LABEL must not select a second shape.
os.environ["TG_NOTE_LABEL"] = "TeemoBKK's Note"

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
    "Teemo's Note\n"
    "조달 자금이 오픈AI 후속 투자에 쓰일 수 있다.\n"
    "\n"
    "관련 : #소프트뱅크 #오픈AI #정크본드\n"
    "출처: <a href=\"https://example.com/story\">출처</a> | 2026-09-21 09:00:00 ICT\n"
    "<a href=\"https://teemobkk.io/news/\">TeemoBKK 라이브 뉴스</a>"
)

# Shapes the channel carried before the single renderer was enforced. They must stay rejected.
MARKDOWN_POST = (
    "[속보] 비트코인, ETF 자금 유입 전환에 84.8K 돌파\n"
    "\n"
    "비트코인이 미국 현물 ETF 자금 흐름이 순유입으로 전환된 뒤 84.8K를 넘어섰다.\n"
    "\n"
    "TeemoBKK's Note : ETF 수급이 실제 순유입으로 이어지는지가 핵심 변수다.\n"
    "\n"
    "#비트코인 #ETF #기관수급\n"
    "2026-09-22 06:16 ICT\n"
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

    def test_body_paragraph_breaks_are_preserved(self):
        text = tg_push.render(ITEM, TITLE, "첫 문단.\n\n둘째 문단.", NOTE, TAGS)
        self.assertIn("첫 문단.\n\n둘째 문단.", text)

    def test_the_shape_carries_embedded_anchor_links_only(self):
        text = frozen()
        self.assertNotIn("@url:", text)
        self.assertNotIn("](", text)
        self.assertIn('<a href="https://example.com/story">출처</a>', text)
        self.assertIn('<a href="https://teemobkk.io/news/">TeemoBKK 라이브 뉴스</a>', text)

    def test_dynamic_ampersands_are_html_escaped(self):
        item = dict(ITEM)
        item["link"] = "https://example.com/story?a=1&b=2"
        text = tg_push.render(item, "A < B", "본문 & 확인", NOTE, TAGS)
        self.assertIn("A &lt; B", text)
        self.assertIn("본문 &amp; 확인", text)
        self.assertIn("story?a=1&amp;b=2", text)

    def test_the_note_label_is_fixed_even_when_env_requests_another_one(self):
        self.assertIn("Teemo's Note\n조달", frozen())
        self.assertNotIn("TeemoBKK's Note", frozen())

    def test_the_footer_keeps_its_link_when_the_env_is_empty(self):
        original = tg_push.CHANNEL_LINK
        try:
            tg_push.CHANNEL_LINK = "https://teemobkk.io/news/"
            self.assertIn('<a href="https://teemobkk.io/news/">TeemoBKK 라이브 뉴스</a>', frozen())
        finally:
            tg_push.CHANNEL_LINK = original


class ShapeCheck(unittest.TestCase):
    def test_it_reports_one_problem_per_broken_line(self):
        broken = "\n".join(["[기사] 제목", "", "본문", "", "출처: https://example.com/x",
                            "TeemoBKK Live News (https://teemobkk.io/news/)"])
        joined = " | ".join(tg_push.validate_post(broken))
        self.assertIn("Note", joined)
        self.assertIn("관련", joined)
        self.assertIn("ICT source", joined)

    def test_the_old_renderers_shapes_are_still_rejected(self):
        for text, expected in ((MARKDOWN_POST, "markdown link"),
                               (OLD_DEPLOYED_POST, "hash-tag first line"),
                               (OLD_DEPLOYED_POST, "visible URL wrapper"),
                               (OLD_DEPLOYED_POST, "old English footer"),
                               (OLD_DEPLOYED_POST, "ICT source")):
            with self.subTest(expected=expected):
                self.assertIn(expected, " | ".join(tg_push.validate_post(text)))

    def test_a_missing_related_line_is_rejected(self):
        text = GOLDEN.replace("관련 : #소프트뱅크 #오픈AI #정크본드\n", "")
        self.assertIn("관련", " | ".join(tg_push.validate_post(text)))

    def test_more_than_four_tags_is_rejected(self):
        text = GOLDEN.replace("#소프트뱅크 #오픈AI #정크본드", "#가 #나 #다 #라 #마")
        self.assertIn("관련", " | ".join(tg_push.validate_post(text)))

    def test_the_note_block_is_required_for_every_publisher(self):
        text = "\n".join(line for line in GOLDEN.split("\n")
                         if line not in (tg_push.NOTE_LABEL, NOTE))
        problems = " | ".join(tg_push.validate_post(text))
        self.assertIn("Note", problems)

    def test_note_body_is_required_after_the_note_header(self):
        text = GOLDEN.replace("Teemo's Note\n조달", "Teemo's Note\n\n조달")
        self.assertIn("note body", " | ".join(tg_push.validate_post(text)))

    def test_lines_out_of_order_are_rejected(self):
        lines = GOLDEN.split("\n")
        notes = lines.index(tg_push.NOTE_LABEL)
        related = [i for i, line in enumerate(lines) if line.startswith("관련 :")][0]
        lines[notes], lines[related] = lines[related], lines[notes]
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

    def test_a_post_without_a_note_is_refused(self):
        ok, why = tg_push.post_parts(self.connection, self.parts(note=""))
        self.assertFalse(ok)
        self.assertIn("no note", why)

    def test_a_second_post_of_the_same_link_is_refused(self):
        self.connection.execute(
            "INSERT INTO tg_posted (link, posted_at, mode) VALUES (?,?,?)",
            (LINK, "2026-09-21T02:00:00+00:00", "agent"))
        self.connection.commit()
        ok, why = tg_push.post_parts(self.connection, self.parts())
        self.assertFalse(ok)
        self.assertIn("already posted", why)


class SameTickEvent(unittest.TestCase):
    """A same-event rewrite skipped first must block the next wording in that tick."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._original_db = core.DB_FILE
        self._original_dry = tg_push.DRY_RUN
        core.DB_FILE = Path(self.dir) / "news.db"
        core.init_db()
        self.connection = tg_push.connect()
        tg_push.DRY_RUN = True
        now = datetime.now(timezone.utc)
        rows = [
            ("https://example.com/a", "미국 법무부, 바이낸스 이란 제재 위반 조사"),
            ("https://example.com/b", "연방 검찰, 바이낸스 이란 제재 위반 조사"),
        ]
        for index, (link, title) in enumerate(rows):
            stamp = (now - timedelta(minutes=index + 1)).isoformat()
            self.connection.execute(
                "INSERT INTO articles (link, title, summary, source, source_type, region,"
                " category, asset, priority, published_at, collected_at, categories)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (link, title, title, "Google News · 지정학", "news", "글로벌", "지정학",
                 "", 4, stamp, stamp, "지정학,규제정책"),
            )
        self.connection.commit()

    def tearDown(self):
        tg_push.DRY_RUN = self._original_dry
        self.connection.close()
        core.DB_FILE = self._original_db

    def test_only_one_rewrite_of_the_event_is_selected(self):
        rows = tg_push.tick(self.connection, now=datetime.now(timezone.utc), limit=10, quiet=True)
        self.assertEqual(1, len(rows))
        self.assertIn("바이낸스", rows[0]["title"])


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


class OriginalPublisherLink(unittest.TestCase):
    AGGREGATOR = "https://news.google.com/rss/articles/CBMihgFBVV95cUxNRDlVOS1zS05fUkhyWk5ac3NKUG9XN2JD?oc=5"
    PUBLISHER = "https://www.xportsnews.com/article/2200096"

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")

    def tearDown(self):
        self.connection.close()

    def test_cached_publisher_url_is_used_without_changing_story_identity(self):
        tg_push.google_news.remember(self.connection, {self.AGGREGATOR: self.PUBLISHER})
        item = {"link": self.AGGREGATOR}
        self.assertEqual(tg_push.attach_original_link(self.connection, item), self.PUBLISHER)
        self.assertEqual(item["link"], self.AGGREGATOR)
        text = tg_push.render({**ITEM, **item}, TITLE, BODY, NOTE, TAGS)
        self.assertIn('href="%s"' % self.PUBLISHER, text)
        self.assertNotIn(self.AGGREGATOR, text)

    def test_missing_cache_resolves_and_remembers_verified_publisher(self):
        item = {"link": self.AGGREGATOR}
        with patch.object(tg_push.google_news, "resolve", return_value=self.PUBLISHER) as resolve:
            self.assertEqual(tg_push.attach_original_link(self.connection, item), self.PUBLISHER)
        resolve.assert_called_once_with(self.AGGREGATOR)
        self.assertEqual(tg_push.google_news.load(self.connection)[self.AGGREGATOR], self.PUBLISHER)

    def test_failed_resolution_falls_back_to_stored_aggregator_url(self):
        item = {"link": self.AGGREGATOR}
        with patch.object(tg_push.google_news, "resolve", return_value=None):
            self.assertEqual(tg_push.attach_original_link(self.connection, item), self.AGGREGATOR)
        self.assertNotIn("original_link", item)
        text = tg_push.render({**ITEM, **item}, TITLE, BODY, NOTE, TAGS)
        self.assertIn("구글 뉴스(원문 미확인)", text)
        self.assertEqual([], tg_push.validate_post(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)
