from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import MemberProfile, EmailChallenge


@override_settings(
    POST_RESTRICTED_PREVIEW=True,
    POST_PREVIEW_ALLOWED_EMAILS=frozenset({'reviewer@example.invalid'}),
    MIDDLEWARE=[*settings.MIDDLEWARE, 'members.preview.RestrictedPreviewMiddleware'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    POST_AUTH_EMAIL_ENABLED=True,
    POST_SIGNUP_ENABLED=True,
    DEFAULT_FROM_EMAIL='test@example.invalid',
)
class RestrictedPreviewTests(TestCase):
    def test_policy_pages_are_readable_before_authentication(self):
        for kind in ['terms', 'privacy']:
            for method in ['get', 'head']:
                with self.subTest(kind=kind, method=method):
                    response=getattr(self.client, method)('/accounts/policy/'+kind+'/')
                    self.assertEqual(response.status_code,200)
                    self.assertIn('no-store',response['Cache-Control'])
                    self.assertEqual(response['X-Robots-Tag'],'noindex, nofollow, noarchive')

    def test_policy_exception_does_not_open_other_paths_or_methods(self):
        for path in ['/accounts/policy/unknown/', '/accounts/policy/privacy/extra/',
                     '/accounts/policy/terms/edit/', '/accounts/profile/']:
            with self.subTest(path=path):
                self.assertRedirects(self.client.get(path),'/accounts/login/',fetch_redirect_response=False)
        for kind in ['terms','privacy']:
            self.assertRedirects(self.client.post('/accounts/policy/'+kind+'/'),'/accounts/login/',fetch_redirect_response=False)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(EmailChallenge.objects.exists())

    def test_public_content_is_readable_without_joining(self):
        for path in ['/', '/community/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')
        # News data may be unavailable in this test environment; it must not be
        # replaced with the preview login redirect.
        for path in ['/newsroom/', '/newsroom/article-id/', '/api/v1/news/',
                     '/api/v1/news/article-id/', '/community/1/',
                     '/api/v1/posts/1/', '/api/v1/posts/1/comments/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertIn(response.status_code,{200,404,503})
        self.assertEqual(self.client.get('/api/v1/posts/').status_code,200)

    def test_public_app_header_exposes_theme_toggle(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-theme-toggle')
        self.assertContains(response,'다크 모드로 전환')

    def test_private_pages_and_guest_write_actions_still_require_login(self):
        for path in ['/accounts/profile/', '/community/activity/',
                     '/community/notifications/', '/community/new/', '/admin/', '/health/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertRedirects(response, '/accounts/login/', fetch_redirect_response=False)
        for path in ['/community/1/helpful/', '/community/1/comments/']:
            with self.subTest(path=path):
                response=self.client.post(path, {'active':'true','body':'test'})
                self.assertRedirects(response, '/accounts/login/', fetch_redirect_response=False)
        self.assertEqual(self.client.post('/api/v1/posts/', {'title':'test'}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/me/').status_code,403)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(EmailChallenge.objects.exists())

    def test_uninvited_email_creates_neither_user_challenge_nor_mail(self):
        response=self.client.post('/accounts/email/', {'email':'stranger@example.invalid'})
        self.assertRedirects(response, '/accounts/email/sent/')
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(EmailChallenge.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_invited_email_can_request_real_flow(self):
        self.client.post('/accounts/email/', {'email':'REVIEWER@example.invalid'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailChallenge.objects.count(), 1)

    def test_allowed_email_without_verified_profile_is_not_identity_proof(self):
        user=get_user_model().objects.create_user(username='pending',email='reviewer@example.invalid')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/accounts/profile/').status_code,403)
        MemberProfile.objects.create(user=user,email_key=user.email)
        self.assertEqual(self.client.get('/community/activity/').status_code,403)

    def test_verified_invitee_can_view_and_onboard(self):
        user=get_user_model().objects.create_user(username='reviewer',email='reviewer@example.invalid')
        MemberProfile.objects.create(user=user,email_key=user.email,email_verified_at=timezone.now())
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/accounts/onboarding/').status_code,200)

    def test_verified_uninvited_and_staff_users_do_not_bypass_gate(self):
        user=get_user_model().objects.create_user(username='other',email='other@example.invalid',is_staff=True,is_superuser=True)
        MemberProfile.objects.create(user=user,email_key=user.email,email_verified_at=timezone.now())
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/admin/').status_code,403)
        self.assertEqual(self.client.get('/accounts/profile/').status_code,403)

    def test_gate_is_inert_when_disabled(self):
        with override_settings(POST_RESTRICTED_PREVIEW=False):
            self.assertEqual(self.client.get('/').status_code,200)

    def test_public_auth_pages_and_logout_are_reachable(self):
        for path in ['/accounts/login/','/accounts/email/','/accounts/email/sent/','/accounts/email/confirm/']:
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertNotEqual(self.client.get('/accounts/logout/').status_code,403)
        # The existing provider boundary rejects Google before this gate when unconfigured.
        self.assertEqual(self.client.get('/accounts/google/login/').status_code,503)
