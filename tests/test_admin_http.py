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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import admin_auth  # noqa: E402
import live_news_dashboard as core  # noqa: E402

SECRET = "correct horse battery staple"


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
