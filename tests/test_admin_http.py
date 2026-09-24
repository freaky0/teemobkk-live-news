"""The admin gate, driven over HTTP against a server in this process.

The unit tests next door check the rules; this checks that the running server applies them - that a
stranger cannot write, that a session works and that a session sees what a stranger does not. The
server is started here rather than touched on a live host, so the checks are about the code that
ships, and the collector is never started, so nothing goes to the network.

    python tests/test_admin_http.py
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import admin_auth  # noqa: E402
import live_news_dashboard as core  # noqa: E402

SECRET = "correct horse battery staple"
LINK = "https://example.com/http-test-story"
PICK_LINK = "https://example.com/http-test-pick"


def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class Gate(unittest.TestCase):
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

    def setUp(self):
        admin_auth._failures.clear()

    def call(self, path, method="GET", body=None, cookie="", header=False, proto=""):
        request = urllib.request.Request(self.base + path, method=method,
                                         data=json.dumps(body).encode("utf-8") if body is not None else None,
                                         headers={"Content-Type": "application/json"})
        if cookie:
            request.add_header("Cookie", cookie)
        if header:
            request.add_header(admin_auth.REQUIRED_HEADER, "teemo-admin")
        if proto:
            request.add_header("X-Forwarded-Proto", proto)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
                return response.status, dict(response.headers), (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read() or b"{}")
            except ValueError:
                payload = {}
            return error.code, dict(error.headers), payload

    def login(self, password=SECRET):
        status, headers, _ = self.call("/api/login", "POST", {"password": password})
        return status, headers.get("Set-Cookie", "")

    def session(self, password=SECRET):
        status, cookie = self.login(password)
        self.assertEqual(status, 200, "the test needs a working login")
        return cookie.split(";", 1)[0]

    # --- strangers ---
    def test_a_stranger_cannot_write(self):
        status, _, _ = self.call("/api/settings", "POST", {"interval": 300})
        self.assertEqual(status, 401, "the deployed server must not accept an anonymous write")

    def test_a_stranger_does_not_see_the_collection_state(self):
        status, _, payload = self.call("/api/status")
        self.assertEqual(status, 200)
        for key in ("sources", "archive", "interval_seconds"):
            self.assertNotIn(key, payload, "the operator's view must not go out anonymously")
        self.assertIn("updated_at_ict", payload, "the page still needs the clock")
        status, _, payload = self.call("/api/news?hours=24&limit=1")
        self.assertEqual(status, 200)
        self.assertNotIn("sources", payload)

    def test_the_operator_endpoints_are_closed(self):
        self.assertEqual(self.call("/api/stats")[0], 404)

    def test_a_forged_cookie_is_refused(self):
        status, _, _ = self.call("/api/settings", "POST", {"interval": 300},
                                 cookie="teemo_admin=9999999999.deadbeef", header=True)
        self.assertEqual(status, 401)

    def test_the_wrong_password_is_refused_and_no_cookie_is_handed_out(self):
        status, cookie = self.login("not the password")
        self.assertEqual(status, 401)
        self.assertEqual(cookie, "")

    def test_repeated_failures_are_throttled(self):
        for _ in range(admin_auth.FAIL_LIMIT):
            self.login("not the password")
        status, _ = self.login("not the password")
        self.assertEqual(status, 429, "the sixth attempt from one address waits")
        self.assertEqual(self.login(SECRET)[0], 429, "and the right password waits too")

    # --- a session ---
    def test_login_hands_out_a_usable_session(self):
        status, cookie = self.login()
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn("; Secure", cookie, "plain http on the test server")
        status, _, payload = self.call("/api/settings", "POST", {"interval": 300},
                                       cookie=cookie.split(";", 1)[0], header=True)
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(core.Handler.state.interval, 300)

    def test_a_session_sees_what_a_stranger_does_not(self):
        cookie = self.session()
        status, _, payload = self.call("/api/status", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("sources", payload)
        self.assertIn("archive", payload)
        self.assertIn("interval_seconds", payload)
        self.assertEqual(self.call("/api/stats", cookie=cookie)[0], 200)

    def test_a_session_still_needs_the_custom_header_to_write(self):
        cookie = self.session()
        status, _, _ = self.call("/api/settings", "POST", {"interval": 120}, cookie=cookie)
        self.assertEqual(status, 401, "the header is what a cross-site form post cannot set")

    def test_a_tls_request_needs_a_session_even_without_public_mode(self):
        core.PUBLIC_MODE = False
        try:
            status, _, _ = self.call("/api/settings", "POST", {"interval": 240}, proto="https")
            self.assertEqual(status, 401, "the proxy says this arrived over TLS, so writes need a session")
            status, _, _ = self.call("/api/settings", "POST", {"interval": 240})
            self.assertEqual(status, 200, "a loopback server on the operator's machine keeps working")
        finally:
            core.PUBLIC_MODE = True

    # --- the operator page ---
    def test_a_stranger_asking_for_admin_gets_only_a_password_box(self):
        with urllib.request.urlopen(self.base + "/admin", timeout=10) as response:
            page = response.read().decode("utf-8")
            headers = dict(response.headers)
        self.assertEqual(response.status, 200)
        self.assertIn('id="pw"', page, "the login box")
        for marker in ('id="interval"', 'id="logout"', 'id="feed"', "window.__ADMIN__"):
            self.assertNotIn(marker, page, "a stranger must not receive dashboard markup: " + marker)
        self.assertIn("no-store", headers.get("Cache-Control", ""),
                      "a page that depends on a session must never be cached")

    def test_a_session_gets_the_operator_page(self):
        cookie = self.session()
        with urllib.request.urlopen(urllib.request.Request(
                self.base + "/admin/", headers={"Cookie": cookie}), timeout=10) as response:
            page = response.read().decode("utf-8")
        self.assertIn("window.__ADMIN__=true", page, "the script has to know before it writes")
        self.assertIn('id="interval"', page)
        self.assertIn('id="logout"', page)
        self.assertIn("X-Requested-With", page, "writes carry the header the server wants")
        self.assertIn('id="feed"', page)

    def test_the_operator_document_is_not_a_file(self):
        self.assertFalse((Path(ROOT) / "_admin.html").exists(),
                         "the page must not sit where the reverse proxy serves from disk")
        # Nothing answers it either: it is not a route and not in the static whitelist.
        self.assertEqual(self.call("/_admin.html")[0], 404)

    def test_signing_out_ends_the_session_and_not_only_the_cookie(self):
        cookie = self.session()
        self.assertIn("window.__ADMIN__=true", self.admin_body(cookie))
        status, headers, _ = self.call("/api/logout", "POST", {}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))
        # A copy of the cookie kept elsewhere must stop working too: otherwise logging out would
        # only clear the browser it happened in.
        self.assertEqual(self.call("/api/settings", "POST", {"interval": 300},
                                   cookie=cookie, header=True)[0], 401)
        self.assertNotIn("window.__ADMIN__=true", self.admin_body(cookie))

    def test_an_expired_session_gets_the_login_box_again(self):
        # Signed with the right key, but its expiry is long past: the signature is not the whole
        # check, the clock is part of it.
        cookie = "teemo_admin=" + admin_auth.issue_token(now=10 ** 6)
        self.assertNotIn("window.__ADMIN__=true", self.admin_body(cookie))

    def admin_body(self, cookie):
        with urllib.request.urlopen(urllib.request.Request(
                self.base + "/admin", headers={"Cookie": cookie}), timeout=10) as response:
            return response.read().decode("utf-8")

    def test_the_login_page_points_at_the_login_endpoint(self):
        page = self.admin_body("")
        self.assertIn("/api/login", page)
        self.assertIn('type="password"', page)
        self.assertIn("noindex", page)

    # --- hiding a story ---
    def test_a_stranger_cannot_hide_or_see_what_is_hidden(self):
        self.assertEqual(self.call("/api/hide", "POST", {"link": LINK})[0], 401)
        self.assertEqual(self.call("/api/unhide", "POST", {"link": LINK})[0], 401)
        self.assertEqual(self.call("/api/hidden")[0], 404, "the restore list is the operator's")

    def test_a_stranger_cannot_touch_the_rules(self):
        self.assertEqual(self.call("/api/filter", "POST", {"action": "add", "pattern": "x"})[0], 401)
        self.assertEqual(self.call("/api/filters")[0], 404, "the rule list is the operator's")

    def test_hiding_needs_the_header_as_well_as_a_session(self):
        cookie = self.session()
        self.assertEqual(self.call("/api/hide", "POST", {"link": LINK}, cookie=cookie)[0], 401)

    def test_an_impossible_link_is_refused(self):
        cookie = self.session()
        for bad in ("", "nonsense", "ftp://example.com/x", "https://"):
            self.assertEqual(self.call("/api/hide", "POST", {"link": bad},
                                       cookie=cookie, header=True)[0], 400, repr(bad))

    def test_hiding_through_the_api_removes_it_and_puts_it_back(self):
        core.init_db()
        core.insert_articles([{"link": LINK, "title": "가려질 기사", "summary": "본문",
                               "source": "Example", "source_type": "news", "region": "글로벌",
                               "category": "시장·가격", "categories": ["시장·가격"], "priority": 3,
                               "published_at": now_iso(), "collected_at": now_iso()}])
        self.assertIn(LINK, self.links(), "the row has to be visible before it is hidden")
        cookie = self.session()

        status, _, payload = self.call("/api/hide", "POST", {"link": LINK, "title": "가려질 기사"},
                                       cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("hidden_total"), 1)
        self.assertNotIn(LINK, self.links(), "the feed must not answer with it any more")

        status, _, payload = self.call("/api/hidden", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual([row["link"] for row in payload["hidden"]], [LINK])
        self.assertEqual(payload["hidden"][0]["title"], "가려질 기사")

        status, _, payload = self.call("/api/unhide", "POST", {"link": LINK}, cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("hidden_total"), 0)
        self.assertIn(LINK, self.links(), "restoring has to bring it back")

    # --- Teemo's Pick ---
    def test_a_stranger_cannot_pick(self):
        self.assertEqual(self.call("/api/pick", "POST", {"link": PICK_LINK})[0], 401)
        self.assertEqual(self.call("/api/unpick", "POST", {"link": PICK_LINK})[0], 401)

    def test_the_pick_list_is_public_because_the_badge_is_the_point(self):
        status, _, payload = self.call("/api/picks")
        self.assertEqual(status, 200, "a reader has to be able to see what was picked")
        self.assertIn("picked", payload)

    def test_picking_marks_the_row_for_readers(self):
        cookie = self.session()
        core.init_db()
        core.insert_articles([{"link": PICK_LINK, "title": "골라낸 기사", "summary": "본문",
                               "source": "Example", "source_type": "news", "region": "글로벌",
                               "category": "시장·가격", "categories": ["시장·가격"], "priority": 3,
                               "published_at": now_iso(), "collected_at": now_iso()}])
        status, _, payload = self.call("/api/pick", "POST", {"link": PICK_LINK, "note": "확인함"},
                                       cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("picked_total"), 1)

        # A reader's request, with no session, sees the pick on the row.
        row = [a for a in self.call("/api/news?hours=24&limit=50")[2]["articles"] if a["link"] == PICK_LINK][0]
        self.assertTrue(row["picked"])
        self.assertEqual(row["pick_note"], "확인함")

        # And the filter the pill uses.
        status, _, payload = self.call("/api/news?hours=24&limit=50&picked=1")
        self.assertEqual([a["link"] for a in payload["articles"]], [PICK_LINK])
        self.assertEqual(payload["total"], 1)
        status, _, payload = self.call("/api/news?hours=24&limit=50&picked=1&category=%ED%8A%B8%EB%9F%BC%ED%94%84")
        self.assertEqual(payload["total"], 0, "a pick composes with the other conditions")

        status, _, payload = self.call("/api/unpick", "POST", {"link": PICK_LINK}, cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("picked_total"), 0)
        row = [a for a in self.call("/api/news?hours=24&limit=50")[2]["articles"] if a["link"] == PICK_LINK][0]
        self.assertFalse(row["picked"])

    def test_a_pick_needs_the_header_as_well_as_a_session(self):
        cookie = self.session()
        self.assertEqual(self.call("/api/pick", "POST", {"link": PICK_LINK}, cookie=cookie)[0], 401)

    # --- the refresh interval ---
    def test_the_interval_is_the_operators_business(self):
        self.assertNotIn("interval_seconds", self.call("/api/news?hours=24&limit=1")[2],
                         "an anonymous reader does not need to know how often we collect")
        cookie = self.session()
        payload = self.call("/api/news?hours=24&limit=1", cookie=cookie)[2]
        self.assertIn("interval_seconds", payload)

    def test_a_chosen_interval_survives_a_restart(self):
        cookie = self.session()
        status, _, payload = self.call("/api/settings", "POST", {"interval": 120},
                                       cookie=cookie, header=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("interval_seconds"), 120)
        self.assertEqual(core.setting_get("interval_seconds"), "120")
        # What a restart does: the service starts again with the command-line default, and the stored
        # value is what wins.
        restarted = core.NewsState(interval=60)
        self.assertEqual(restarted.interval, 120)
        self.assertEqual(core.Handler.state.interval, 120, "and the running one still has it")

    def links(self, path="/api/news?hours=24&limit=50"):
        payload = self.call(path)[2]
        return [row.get("link") for row in payload.get("articles", [])]

    def test_logout_clears_the_cookie(self):
        cookie = self.session()
        status, headers, _ = self.call("/api/logout", "POST", {}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))

    def test_an_absurd_body_is_refused_not_read(self):
        status, _, _ = self.call("/api/login", "POST",
                                 {"password": "x" * (admin_auth.MAX_BODY * 2)})
        self.assertEqual(status, 400)

    def test_without_a_password_file_nobody_can_log_in(self):
        self.password.unlink()
        try:
            self.assertEqual(self.login()[0], 401)
            self.assertEqual(self.call("/api/settings", "POST", {"interval": 300})[0], 401)
        finally:
            self.password.write_bytes(SECRET.encode("utf-8"))

    def test_robots_and_sitemap_are_public_and_only_list_indexable_pages(self):
        with urllib.request.urlopen(self.base + "/robots.txt", timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/plain", response.headers.get("Content-Type", ""))
            robots = response.read().decode("utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertIn("Allow: /", robots)
        self.assertIn("Sitemap: https://teemobkk.io/sitemap.xml", robots)

        with urllib.request.urlopen(self.base + "/sitemap.xml", timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("xml", response.headers.get("Content-Type", ""))
            sitemap = ET.fromstring(response.read())
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text or "" for node in sitemap.findall("sm:url/sm:loc", namespace)]
        self.assertEqual(urls, ["https://teemobkk.io/", "https://teemobkk.io/thai/",
                                "https://teemobkk.io/privacy/", "https://teemobkk.io/privacy/en/"])
        self.assertFalse(any("/news/" in url for url in urls),
                         "the news dashboards are noindex and don't belong in the sitemap")

    def test_privacy_pages_are_public_translated_and_canonical(self):
        pages = (
            ("/privacy/", "ko", "개인정보 처리방침", "https://teemobkk.io/privacy/", "en",
             "https://teemobkk.io/privacy/en/", "활성화되어 있지"),
            ("/privacy/en/", "en", "Privacy Policy", "https://teemobkk.io/privacy/en/", "ko",
             "https://teemobkk.io/privacy/", "not active"),
        )
        for path, lang, title, canonical, alternate_lang, alternate, inactive_note in pages:
            with urllib.request.urlopen(self.base + path, timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("text/html", response.headers.get("Content-Type", ""))
                page = response.read().decode("utf-8")
            self.assertIn('<html lang="%s">' % lang, page)
            self.assertIn('<link rel="canonical" href="%s">' % canonical, page)
            self.assertIn('<link rel="alternate" hreflang="%s" href="%s">' %
                          (alternate_lang, alternate), page)
            self.assertIn("Keith S. Jun", page)
            self.assertIn("freaky0@gmail.com", page)
            self.assertIn(title, page)
            self.assertNotIn('name="robots" content="noindex"', page)
            self.assertIn("AdSense", page)
            self.assertIn("TCF v2.3", page)
            self.assertIn(inactive_note, page)

    def test_the_page_tells_the_script_it_is_public(self):
        # The page is not JSON, so it is fetched directly rather than through the JSON helper.
        with urllib.request.urlopen(self.base + "/", timeout=10) as response:
            page = response.read().decode("utf-8")
        self.assertIn("window.__PUBLIC__=true", page)
        cookie = self.session()
        with urllib.request.urlopen(urllib.request.Request(
                self.base + "/", headers={"Cookie": cookie}), timeout=10) as response:
            page = response.read().decode("utf-8")
        self.assertNotIn("window.__PUBLIC__=true", page, "an operator gets the full page")


if __name__ == "__main__":
    unittest.main(verbosity=2)
