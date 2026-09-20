"""Admin session rules, checked without a server.

The cookie is the whole session: it is a signed expiry, so these tests are about the parts that can
go wrong quietly - a token that stays valid after the password changed, a tampered expiry that still
verifies, a cookie nobody can find because the parser reads the wrong name.

    python tests/test_admin_auth.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import admin_auth  # noqa: E402

SECRET = "correct horse battery staple"


class Sessions(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._original = admin_auth.PASSWORD_FILE
        admin_auth.PASSWORD_FILE = Path(self.dir) / ".admin_password"
        admin_auth._failures.clear()

    def tearDown(self):
        admin_auth.PASSWORD_FILE = self._original
        admin_auth._failures.clear()

    def set_password(self, value=SECRET):
        admin_auth.PASSWORD_FILE.write_bytes(value.encode("utf-8"))

    # --- configuration ---
    def test_no_password_file_means_no_sessions_and_no_login(self):
        self.assertFalse(admin_auth.is_configured())
        self.assertFalse(admin_auth.check_password(SECRET))
        self.assertEqual(admin_auth.issue_token(), "")
        self.assertFalse(admin_auth.verify_token("123.abc"))

    def test_an_empty_file_is_not_a_password(self):
        admin_auth.PASSWORD_FILE.write_bytes(b"\n")
        self.assertFalse(admin_auth.is_configured(), "whitespace must not become a blank password")

    def test_only_the_stored_password_is_accepted(self):
        self.set_password()
        self.assertTrue(admin_auth.check_password(SECRET))
        self.assertFalse(admin_auth.check_password(SECRET + " "))
        self.assertFalse(admin_auth.check_password(""))
        self.assertFalse(admin_auth.check_password("Correct horse battery staple"))

    # --- the token ---
    def test_a_fresh_token_verifies_and_a_tampered_one_does_not(self):
        self.set_password()
        token = admin_auth.issue_token()
        self.assertTrue(admin_auth.verify_token(token))
        expiry, nonce, signature = token.split(".")
        # Flip the last character to a different one: replacing it with a fixed digit left the token
        # untouched one time in sixteen, and the check failed on itself.
        flipped = "1" if signature[-1] != "1" else "2"
        self.assertFalse(admin_auth.verify_token("%s.%s.%s" % (expiry, nonce, signature[:-1] + flipped)),
                         "a changed signature must not verify")
        self.assertFalse(admin_auth.verify_token("%s.%s.%s" % (int(expiry) + 60, nonce, signature)),
                         "moving the expiry out must break the signature")
        self.assertFalse(admin_auth.verify_token("%s.%s.%s" % (expiry, "0" * 16, signature)),
                         "swapping the nonce must break it too")
        self.assertFalse(admin_auth.verify_token(expiry))
        self.assertFalse(admin_auth.verify_token(""))
        self.assertFalse(admin_auth.verify_token("1.2"))

    def test_two_logins_in_the_same_second_are_different_tokens(self):
        # The expiry has one-second resolution, so without the nonce these two strings would be
        # identical and signing one out would sign the other out.
        self.set_password()
        self.assertNotEqual(admin_auth.issue_token(now=1000), admin_auth.issue_token(now=1000))

    def test_a_signed_out_token_stops_verifying(self):
        self.set_password()
        token = admin_auth.issue_token()
        self.assertTrue(admin_auth.verify_token(token))
        admin_auth.revoke(token)
        self.assertFalse(admin_auth.verify_token(token))
        self.assertTrue(admin_auth.verify_token(admin_auth.issue_token()),
                        "and only that token: the next login still works")

    def test_an_expired_token_stops_working(self):
        self.set_password()
        token = admin_auth.issue_token(now=1000)
        self.assertTrue(admin_auth.verify_token(token, now=1000 + admin_auth.TTL_SECONDS - 1))
        self.assertFalse(admin_auth.verify_token(token, now=1000 + admin_auth.TTL_SECONDS + 1))

    def test_changing_the_password_invalidates_every_session(self):
        self.set_password()
        token = admin_auth.issue_token()
        self.assertTrue(admin_auth.verify_token(token))
        self.set_password("a completely different password")
        self.assertFalse(admin_auth.verify_token(token),
                         "the cookie is keyed on the password, so a change must end old sessions")

    # --- the cookie ---
    def test_the_cookie_carries_the_flags_that_matter(self):
        cookie = admin_auth.cookie_header("123.abc", secure=True)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("; Secure", cookie)
        self.assertIn("Path=/", cookie)
        plain = admin_auth.cookie_header("123.abc", secure=False)
        self.assertNotIn("; Secure", plain, "a loopback http server cannot set Secure or the cookie is dropped")
        self.assertIn("Max-Age=0", admin_auth.clear_cookie(False))

    def test_the_token_is_found_in_a_header_with_other_cookies(self):
        self.assertEqual(admin_auth.token_from_cookie("a=1; teemo_admin=9.8; b=2"), "9.8")
        self.assertEqual(admin_auth.token_from_cookie("teemo_admin=9.8"), "9.8")
        self.assertEqual(admin_auth.token_from_cookie("other=1"), "")
        self.assertEqual(admin_auth.token_from_cookie(""), "")
        self.assertEqual(admin_auth.token_from_cookie("teemo_admin_extra=9.8"), "")

    # --- rate limiting ---
    def test_five_failures_then_that_address_waits(self):
        now = 1000.0
        for _ in range(admin_auth.FAIL_LIMIT):
            self.assertTrue(admin_auth.login_allowed("1.2.3.4", now))
            admin_auth.note_failure("1.2.3.4", now)
        self.assertFalse(admin_auth.login_allowed("1.2.3.4", now), "the sixth attempt is refused")
        self.assertTrue(admin_auth.login_allowed("5.6.7.8", now), "another address is unaffected")
        self.assertTrue(admin_auth.login_allowed("1.2.3.4", now + admin_auth.FAIL_WINDOW + 1),
                        "the window slides")

    def test_a_success_clears_the_count(self):
        now = 1000.0
        for _ in range(admin_auth.FAIL_LIMIT - 1):
            admin_auth.note_failure("1.2.3.4", now)
        admin_auth.note_success("1.2.3.4")
        for _ in range(admin_auth.FAIL_LIMIT):
            self.assertTrue(admin_auth.login_allowed("1.2.3.4", now))
            admin_auth.note_failure("1.2.3.4", now)


class WriteGate(unittest.TestCase):
    class FakeHandler:
        def __init__(self, headers):
            self.headers = headers
            self.client_address = ("10.0.0.9", 1234)

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._original = admin_auth.PASSWORD_FILE
        admin_auth.PASSWORD_FILE = Path(self.dir) / ".admin_password"
        admin_auth.PASSWORD_FILE.write_bytes(SECRET.encode("utf-8"))

    def tearDown(self):
        admin_auth.PASSWORD_FILE = self._original

    def test_a_write_needs_a_session_and_the_header(self):
        token = admin_auth.issue_token()
        browser = self.FakeHandler({"Cookie": "teemo_admin=" + token,
                                    admin_auth.REQUIRED_HEADER: "teemo-admin"})
        self.assertEqual(admin_auth.write_request_ok(browser), (True, ""))

        no_cookie = self.FakeHandler({admin_auth.REQUIRED_HEADER: "teemo-admin"})
        self.assertFalse(admin_auth.write_request_ok(no_cookie)[0])

        # A session without the custom header: the header is what a cross-site form post cannot set.
        no_header = self.FakeHandler({"Cookie": "teemo_admin=" + token})
        ok, why = admin_auth.write_request_ok(no_header)
        self.assertFalse(ok)
        self.assertIn(admin_auth.REQUIRED_HEADER, why)

    def test_secure_is_read_from_the_proxy_header(self):
        plain = self.FakeHandler({})
        self.assertFalse(admin_auth.is_secure(plain))
        proxied = self.FakeHandler({"X-Forwarded-Proto": "https"})
        self.assertTrue(admin_auth.is_secure(proxied))
        mixed = self.FakeHandler({"X-Forwarded-Proto": "https, http"})
        self.assertTrue(admin_auth.is_secure(mixed))

    def test_the_caller_address_comes_from_the_proxy_header(self):
        self.assertEqual(admin_auth.client_ip(self.FakeHandler({"X-Forwarded-For": "9.9.9.9, 10.0.0.1"})),
                         "9.9.9.9")
        self.assertEqual(admin_auth.client_ip(self.FakeHandler({})), "10.0.0.9")


if __name__ == "__main__":
    unittest.main(verbosity=2)
