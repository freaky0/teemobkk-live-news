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
    def test_all_content_families_are_closed_to_anonymous_users(self):
        for path in ['/', '/community/', '/community/new/', '/news/', '/news/any/', '/admin/', '/health/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertRedirects(response, '/accounts/login/', fetch_redirect_response=False)
                self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')
        for path in ['/api/v1/news/', '/api/v1/posts/', '/api/v1/me/']:
            self.assertEqual(self.client.get(path).status_code, 403)

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
        self.assertEqual(self.client.get('/').status_code,403)
        MemberProfile.objects.create(user=user,email_key=user.email)
        self.assertEqual(self.client.get('/').status_code,403)

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
        self.assertEqual(self.client.get('/').status_code,403)
        self.assertEqual(self.client.get('/admin/').status_code,403)

    def test_gate_is_inert_when_disabled(self):
        with override_settings(POST_RESTRICTED_PREVIEW=False):
            self.assertEqual(self.client.get('/').status_code,200)

    def test_public_auth_pages_and_logout_are_reachable(self):
        for path in ['/accounts/login/','/accounts/email/','/accounts/email/sent/','/accounts/email/confirm/']:
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertNotEqual(self.client.get('/accounts/logout/').status_code,403)
        # The existing provider boundary rejects Google before this gate when unconfigured.
        self.assertEqual(self.client.get('/accounts/google/login/').status_code,503)
