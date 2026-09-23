"""Switching a whole source on and off: what it takes out, what it keeps, and who may do it.

The distinction this file holds: a source switch is a filter, not a delete, and it is stored in the
settings table so the deployed server keeps the operator's choice across restarts. A switched-off
source leaves every read path - the feed, the counts, the landings and the pills all read through
`query_articles` - which is why the way back is the source list itself rather than a filter.

    python tests/test_source_switch.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import admin_auth  # noqa: E402
import live_news_dashboard as core  # noqa: E402

SECRET = "correct-horse-battery-staple"
KEPT = "https://example.com/kept"
DROPPED = "https://example.com/dropped"
# The read paths this file checks are windowed (hours=24), so the fixture has to be recent: a pinned
# date ages out of the window and the feeds answer empty while the code is unchanged.
WHEN = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()


def article(link, title, source):
    return {"link": link, "title": title, "summary": "본문", "source": source,
            "source_type": "news", "region": "글로벌", "category": "시장·가격",
            "categories": ["시장·가격"], "priority": 3, "published_at": WHEN,
            "collected_at": WHEN}


class Switch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Path(self.dir) / "news.db"
        self._original = core.DB_FILE
        core.DB_FILE = self.db
        core.init_db()
        core.insert_articles([article(KEPT, "남는 기사", "Reuters"),
                              article(DROPPED, "사라질 기사", "CoinNess")])

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

    def test_it_starts_with_nothing_switched_off(self):
        self.assertEqual(core.hidden_sources(), [])

    def test_switching_a_source_off_takes_its_stories_out_of_the_read_paths(self):
        self.assertEqual(len(self.links()), 2)
        self.assertEqual(core.set_source_hidden("CoinNess", True), ["CoinNess"])
        self.assertEqual(self.links(), [KEPT], "the reader's list loses that source")

    def test_the_rows_stay_in_the_database(self):
        core.set_source_hidden("CoinNess", True)
        self.assertEqual(self.stored(), 2, "a switch is a filter, not a delete")

    def test_switching_it_back_returns_the_stories(self):
        core.set_source_hidden("CoinNess", True)
        self.assertEqual(core.set_source_hidden("CoinNess", False), [])
        self.assertEqual(len(self.links()), 2)

    def test_it_holds_against_the_other_filters(self):
        core.set_source_hidden("CoinNess", True)
        self.assertEqual(self.links(source="CoinNess"), [], "not even asking for it brings it back")
        self.assertEqual(self.links(text="기사"), [KEPT])

    def test_a_blank_source_changes_nothing(self):
        core.set_source_hidden("CoinNess", True)
        self.assertEqual(core.set_source_hidden("   ", True), ["CoinNess"])
        self.assertEqual(core.set_source_hidden("", False), ["CoinNess"])

    def test_the_choice_is_written_where_a_restart_finds_it(self):
        core.set_source_hidden("CoinNess", True)
        connection = sqlite3.connect(str(self.db))
        try:
            row = connection.execute("SELECT value FROM settings WHERE name = ?",
                                     (core.HIDDEN_SOURCES,)).fetchone()
        finally:
            connection.close()
        self.assertIsNotNone(row, "the settings table is what survives a service restart")
        self.assertEqual(json.loads(row[0]), ["CoinNess"])

    def test_two_sources_are_independent(self):
        core.set_source_hidden("CoinNess", True)
        core.set_source_hidden("SBHNews", True)
        self.assertEqual(core.set_source_hidden("CoinNess", False), ["SBHNews"])
        self.assertEqual(len(self.links()), 2, "bringing one back does not bring the other back")


class Endpoint(unittest.TestCase):
    """The write path on a deployment: closed to strangers, and the list is the operator's."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.password = Path(cls.dir) / ".admin_password"
        cls.password.write_bytes(SECRET.encode("utf-8"))
        cls._password_file = admin_auth.PASSWORD_FILE
        admin_auth.PASSWORD_FILE = cls.password

        cls._db = core.DB_FILE
        core.DB_FILE = Path(cls.dir) / "news.db"
        core.init_db()
        core.insert_articles([article(KEPT, "남는 기사", "Reuters"),
                              article(DROPPED, "사라질 기사", "CoinNess")])

        cls._public = core.PUBLIC_MODE
        core.PUBLIC_MODE = True          # the deployment's mode
        core.Handler.state = core.NewsState(interval=600)

        from http.server import ThreadingHTTPServer
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), core.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        admin_auth.PASSWORD_FILE = cls._password_file
        core.DB_FILE = cls._db
        core.PUBLIC_MODE = cls._public
        core.setting_set(core.HIDDEN_SOURCES, "[]")

    def setUp(self):
        admin_auth._failures.clear()
        core.setting_set(core.HIDDEN_SOURCES, "[]")

    def call(self, path, method="GET", body=None, cookie="", header=False):
        request = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Content-Type": "application/json"})
        if cookie:
            request.add_header("Cookie", cookie)
        if header:
            request.add_header(admin_auth.REQUIRED_HEADER, "teemo-admin")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read() or b"{}")
            except ValueError:
                payload = {}
            return error.code, payload

    def session(self):
        request = urllib.request.Request(
            self.base + "/api/login", method="POST",
            data=json.dumps({"password": SECRET}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200, "the test needs a working login")
            return dict(response.headers).get("Set-Cookie", "").split(";", 1)[0]

    def test_a_stranger_cannot_switch_a_source(self):
        status, _ = self.call("/api/source", "POST", {"source": "CoinNess", "hidden": True})
        self.assertEqual(status, 401, "the deployed server must not take an anonymous switch")
        self.assertEqual(core.hidden_sources(), [])

    def test_a_stranger_does_not_see_which_sources_are_off(self):
        core.set_source_hidden("CoinNess", True)
        status, payload = self.call("/api/status")
        self.assertEqual(status, 200)
        self.assertNotIn("hidden_sources", payload,
                         "the anonymous response deliberately carries no source detail")

    def test_the_operator_sees_the_list_and_can_switch(self):
        cookie = self.session()
        status, payload = self.call("/api/source", "POST", {"source": "CoinNess", "hidden": True},
                                    cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("hidden_sources"), ["CoinNess"])

        _, status_payload = self.call("/api/status", cookie=cookie, header=True)
        self.assertEqual(status_payload.get("hidden_sources"), ["CoinNess"])

        _, feed = self.call("/api/news?region=%s&hours=24" % urllib.parse.quote("글로벌"))
        self.assertEqual([row["link"] for row in feed.get("articles", [])], [KEPT],
                         "a reader's feed loses the switched-off source")

        status, payload = self.call("/api/source", "POST", {"source": "CoinNess", "hidden": False},
                                    cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("hidden_sources"), [])
        _, feed = self.call("/api/news?region=%s&hours=24" % urllib.parse.quote("글로벌"))
        self.assertEqual(len(feed.get("articles", [])), 2)

    def test_a_switch_without_a_source_is_refused(self):
        cookie = self.session()
        status, _ = self.call("/api/source", "POST", {"hidden": True}, cookie=cookie, header=True)
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
