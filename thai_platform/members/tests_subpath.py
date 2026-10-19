from urllib.parse import urlsplit

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import set_script_prefix


MIDDLEWARE_WITH_PREVIEW_GATE = list(settings.MIDDLEWARE)
if "members.preview.RestrictedPreviewMiddleware" not in MIDDLEWARE_WITH_PREVIEW_GATE:
    MIDDLEWARE_WITH_PREVIEW_GATE.append("members.preview.RestrictedPreviewMiddleware")


@override_settings(
    POST_AUTH_EMAIL_ENABLED=True,
    POST_SIGNUP_ENABLED=True,
    POST_RESTRICTED_PREVIEW=True,
    POST_PREVIEW_ALLOWED_EMAILS=frozenset({"subpath@example.com"}),
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="auth@example.com",
    POST_PUBLIC_ORIGIN="https://preview.example.com",
    FORCE_SCRIPT_NAME="/thai",
    MIDDLEWARE=MIDDLEWARE_WITH_PREVIEW_GATE,
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

        denied = self.client.post(
            "/accounts/email/",
            {"email": "outside-preview@example.com"},
            SCRIPT_NAME="/thai",
        )
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(denied["Location"], "/thai/accounts/email/sent/")
        self.assertEqual(len(mail.outbox), 0)

        response = self.client.post(
            "/accounts/email/",
            {"email": "subpath@example.com"},
            SCRIPT_NAME="/thai",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/thai/accounts/email/sent/")
        self.assertEqual(len(mail.outbox), 1)

        link = next(line for line in mail.outbox[-1].body.splitlines() if line.startswith("https://"))
        parsed = urlsplit(link)
        self.assertEqual(parsed.netloc, "preview.example.com")
        self.assertEqual(parsed.path, "/thai/accounts/email/confirm/")
        self.assertFalse(parsed.query)
        self.assertTrue(parsed.fragment)

        confirmation = self.client.get("/accounts/email/confirm/", SCRIPT_NAME="/thai")
        self.assertEqual(confirmation.status_code, 200)
