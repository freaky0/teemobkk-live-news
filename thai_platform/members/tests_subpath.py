from urllib.parse import urlsplit

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import set_script_prefix


# Simulate legacy env values; a public email address must not be filtered by them.
@override_settings(
    POST_AUTH_EMAIL_ENABLED=True,
    POST_SIGNUP_ENABLED=True,
    POST_RESTRICTED_PREVIEW=True,
    POST_PREVIEW_ALLOWED_EMAILS=frozenset({"subpath@example.com"}),
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="auth@example.com",
    POST_PUBLIC_ORIGIN="https://preview.example.com",
    FORCE_SCRIPT_NAME="/thai",
)
class EmailLinkSubpathTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        set_script_prefix("/thai/")
        self.addCleanup(set_script_prefix, "/")

    def test_confirmation_link_and_redirect_keep_mount_prefix(self):
        login = self.client.get("/accounts/login/", SCRIPT_NAME="/thai")
        self.assertEqual(login.status_code, 200)
        self.assertIn("private", login["Cache-Control"])
        self.assertIn("no-store", login["Cache-Control"])

        public_request = self.client.post(
            "/accounts/email/",
            {"email": "outside-preview@example.com"},
            SCRIPT_NAME="/thai",
        )
        self.assertEqual(public_request.status_code, 302)
        self.assertEqual(public_request["Location"], "/thai/accounts/email/sent/")
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            "/accounts/email/",
            {"email": "subpath@example.com"},
            SCRIPT_NAME="/thai",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/thai/accounts/email/sent/")
        self.assertEqual(len(mail.outbox), 2)

        link = next(line for line in mail.outbox[-1].body.splitlines() if line.startswith("https://"))
        parsed = urlsplit(link)
        self.assertEqual(parsed.netloc, "preview.example.com")
        self.assertEqual(parsed.path, "/thai/accounts/email/confirm/")
        self.assertFalse(parsed.query)
        self.assertTrue(parsed.fragment)

        confirmation = self.client.get("/accounts/email/confirm/", SCRIPT_NAME="/thai")
        self.assertEqual(confirmation.status_code, 200)

    def test_public_reads_and_write_permissions_keep_mount_prefix(self):
        home = self.client.get("/", SCRIPT_NAME="/thai")
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "태국 주요 소식")
        self.assertEqual(home["X-Robots-Tag"], "index, follow")

        community = self.client.get("/community/", SCRIPT_NAME="/thai")
        self.assertEqual(community.status_code, 200)

        news = self.client.get("/newsroom/", SCRIPT_NAME="/thai")
        self.assertIn(news.status_code, {200, 503})
        self.assertNotIn("/thai/accounts/login/", news.get("Location", ""))

        private = self.client.get("/accounts/profile/", SCRIPT_NAME="/thai")
        self.assertEqual(private.status_code, 302)
        self.assertTrue(private["Location"].startswith("/thai/accounts/login/?next="))

        write = self.client.post("/api/v1/posts/", {"title": "guest"}, SCRIPT_NAME="/thai")
        self.assertEqual(write.status_code, 403)

    def test_short_policy_urls_render_under_mount_prefix(self):
        for path, marker in [("/terms", "서비스 이용약관"), ("/privacy", "개인정보처리방침")]:
            with self.subTest(path=path):
                response = self.client.get(path, SCRIPT_NAME="/thai")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, marker)
