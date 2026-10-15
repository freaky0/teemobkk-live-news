from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Post, Comment, Report

class WebTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user(username="owner")
        self.other = get_user_model().objects.create_user(username="other")
        self.post = Post.objects.create(author=self.owner, title="방콕 첫 생활 준비 질문입니다", body="개인정보 없는 검증용 질문입니다. 동네를 정할 때 어떤 기준을 살펴볼지 질문합니다.", region="bangkok", category="housing")
    def test_public_html_and_google_unconfigured(self):
        for url in ["/", "/community/", reverse("post-detail", args=[self.post.pk]), "/accounts/login/"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, "TEEMOBKK")
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertContains(self.client.get("/accounts/login/"), "Google 로그인 연결 전")
        self.assertEqual(self.client.post("/accounts/google/login/").status_code, 503)
    def test_anonymous_cannot_write(self):
        before = Post.objects.count()
        self.assertEqual(self.client.post("/community/new/", {"title": "몰래 등록 시도"}).status_code, 302)
        self.assertEqual(Post.objects.count(), before)
    def test_create_edit_delete_server_persistence(self):
        self.client.force_login(self.owner)
        payload = {"title": "서버에 실제로 저장되는 질문", "body": "개인정보가 없는 테스트 게시글입니다. 서버 데이터베이스 저장과 권한을 확인하는 질문입니다.", "region": "phuket", "category": "living", "privacy": "on"}
        result = self.client.post("/community/new/", payload)
        self.assertEqual(result.status_code, 302)
        post = Post.objects.get(title=payload["title"])
        self.assertEqual(post.author_id, self.owner.pk)
        other_browser = Client()
        self.assertContains(other_browser.get(result.url), payload["title"])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("post-edit", args=[post.pk]), payload).status_code, 403)
        self.assertEqual(self.client.post(reverse("post-delete", args=[post.pk])).status_code, 403)
        self.client.force_login(self.owner)
        payload["title"] = "정상 작성자 수정 질문입니다"
        self.assertEqual(self.client.post(reverse("post-edit", args=[post.pk]), payload).status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.title, payload["title"])
        self.assertEqual(self.client.post(reverse("post-delete", args=[post.pk])).status_code, 302)
        self.assertEqual(other_browser.get(reverse("post-detail", args=[post.pk])).status_code, 404)
    def test_csrf_and_private_report(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.owner)
        self.assertEqual(c.post("/community/new/", {}).status_code, 403)
        c.get("/community/new/")
        token = c.cookies["csrftoken"].value
        result = c.post(reverse("report-create", args=[self.post.pk]), {"reason": "privacy", "details": "공개해서는 안 되는 개인정보가 있는지 검토해 주세요.", "csrfmiddlewaretoken": token})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(Report.objects.count(), 1)
        self.assertNotContains(Client().get(reverse("post-detail", args=[self.post.pk])), "공개해서는 안 되는")
    def test_xss_and_validation(self):
        self.post.title = '<script>alert("test")</script>'
        self.post.save()
        self.assertContains(self.client.get(reverse("post-detail", args=[self.post.pk])), "&lt;script&gt;")
        self.client.force_login(self.owner)
        response = self.client.post("/community/new/", {"title": "짧음", "body": "짧음", "region": "bangkok", "category": "living"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertEqual(Post.objects.count(), 1)
    def test_comment_and_filter(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("comment-create", args=[self.post.pk]), {"body": "도움이 되는 답변을 남기는 서버 검증입니다."})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.get().author_id, self.other.pk)
        self.assertContains(Client().get(reverse("post-detail", args=[self.post.pk])), "도움이 되는 답변")
        self.assertNotContains(self.client.get("/community/?region=phuket"), self.post.title)
        self.assertContains(self.client.get("/community/?q=방콕"), self.post.title)
    @override_settings(GOOGLE_CONFIGURED=True)
    def test_google_login_page_has_real_provider_form(self):
        # Only template wiring is exercised. This does not prove external OAuth.
        from django.contrib.sites.models import Site
        from allauth.socialaccount.models import SocialApp
        app = SocialApp.objects.create(provider="google", name="Test-only OAuth configuration", client_id="test-client-id", secret="test-fixture-not-a-real-secret")
        app.sites.add(Site.objects.get(pk=1))
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "/accounts/google/login/")
        self.assertContains(response, "Google로 계속하기")
