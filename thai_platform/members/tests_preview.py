from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import MemberProfile, EmailChallenge


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    POST_AUTH_EMAIL_ENABLED=True,
    POST_SIGNUP_ENABLED=True,
    DEFAULT_FROM_EMAIL='test@example.invalid',
)
class PublicSignupTests(TestCase):
    def test_policy_pages_are_readable_before_authentication(self):
        for kind in ['terms', 'privacy']:
            for method in ['get', 'head']:
                with self.subTest(kind=kind, method=method):
                    response=getattr(self.client, method)('/accounts/policy/'+kind+'/')
                    self.assertEqual(response.status_code,200)


    def test_public_content_is_readable_without_joining(self):
        for path in ['/', '/community/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
        # News data may be unavailable in this test environment; it must not be
        # replaced with an authentication redirect.
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
                     '/community/notifications/', '/community/new/', '/admin/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertIn(response.status_code,{302,403})
        self.assertEqual(self.client.get('/health/').status_code,200)
        for path in ['/community/1/helpful/', '/community/1/comments/']:
            with self.subTest(path=path):
                response=self.client.post(path, {'active':'true','body':'test'})
                self.assertIn(response.status_code,{302,403})
        self.assertEqual(self.client.post('/api/v1/posts/', {'title':'test'}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/me/').status_code,403)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(EmailChallenge.objects.exists())

    def test_public_email_can_request_a_sign_in_link_without_invitation(self):
        response=self.client.post('/accounts/email/', {'email':'stranger@example.invalid'})
        self.assertRedirects(response, '/accounts/email/sent/')
        self.assertEqual(get_user_model().objects.count(),1)
        self.assertEqual(EmailChallenge.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_any_email_can_request_real_flow(self):
        self.client.post('/accounts/email/', {'email':'REVIEWER@example.invalid'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailChallenge.objects.count(), 1)

    def test_email_alone_does_not_grant_member_permissions(self):
        user=get_user_model().objects.create_user(username='pending',email='reviewer@example.invalid')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn(self.client.get('/accounts/profile/').status_code,{200,302})
        MemberProfile.objects.create(user=user,email_key=user.email)
        self.assertEqual(self.client.get('/community/activity/').status_code,403)

    def test_verified_member_can_view_and_onboard(self):
        user=get_user_model().objects.create_user(username='reviewer',email='reviewer@example.invalid')
        MemberProfile.objects.create(user=user,email_key=user.email,email_verified_at=timezone.now())
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/accounts/onboarding/').status_code,200)

    def test_verified_new_member_can_reach_onboarding_without_invitation(self):
        user=get_user_model().objects.create_user(username='other',email='other@example.invalid')
        MemberProfile.objects.create(user=user,email_key=user.email,email_verified_at=timezone.now())
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/admin/').status_code,302)
        self.assertRedirects(self.client.get('/accounts/profile/'),'/accounts/onboarding/',fetch_redirect_response=False)

    def test_public_auth_pages_and_logout_are_reachable(self):
        for path in ['/accounts/login/','/accounts/email/','/accounts/email/sent/','/accounts/email/confirm/']:
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertNotEqual(self.client.get('/accounts/logout/').status_code,403)
        # The existing provider boundary rejects Google before this gate when unconfigured.
        self.assertEqual(self.client.get('/accounts/google/login/').status_code,503)
