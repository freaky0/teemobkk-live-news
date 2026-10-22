from django.test import TestCase, override_settings
from django.templatetags.static import static
from django.urls import reverse, set_script_prefix


@override_settings(FORCE_SCRIPT_NAME="/thai", STATIC_URL="static/")
class SubpathMountTests(TestCase):
    def setUp(self):
        set_script_prefix("/thai/")
        self.addCleanup(set_script_prefix, "/")

    def test_named_and_static_urls_stay_under_mount_prefix(self):
        self.assertEqual(reverse("post-list"), "/thai/community/")
        self.assertEqual(reverse("news-list"), "/thai/newsroom/")
        self.assertEqual(reverse("google_callback"), "/thai/accounts/google/login/callback/")
        self.assertEqual(static("app.css"), "/thai/static/app.css")

    def test_home_renders_prefixed_links_and_assets(self):
        response = self.client.get("/", SCRIPT_NAME="/thai")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-script-prefix="/thai"')
        self.assertContains(response, 'href="/thai/static/app.css"')
        self.assertContains(response, 'href="/thai/newsroom/"')
        self.assertContains(response, 'href="/thai/community/"')
        self.assertContains(response, 'href="/thai/accounts/login/"')

    def test_newsroom_route_resolves_below_mount_prefix(self):
        response = self.client.get("/newsroom/", SCRIPT_NAME="/thai")
        self.assertEqual(response.status_code, 503)

    def test_auth_redirect_and_unconfigured_google_gate_keep_prefix(self):
        response = self.client.get("/accounts/profile/", SCRIPT_NAME="/thai")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/thai/accounts/login/"))

        google = self.client.post("/accounts/google/login/", SCRIPT_NAME="/thai")
        self.assertEqual(google.status_code, 503)

    def test_private_auth_response_is_not_cacheable_under_prefix(self):
        response = self.client.get("/accounts/login/", SCRIPT_NAME="/thai")
        self.assertIn("no-store", response.get("Cache-Control", ""))
        self.assertIn("private", response.get("Cache-Control", ""))
