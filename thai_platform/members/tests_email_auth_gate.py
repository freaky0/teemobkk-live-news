from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from allauth.account.models import EmailAddress

from members.models import EmailChallenge, MemberProfile


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="auth@example.test",
    POST_PUBLIC_ORIGIN="https://testserver",
)
class ExistingMemberEmailAuthWithSignupClosedTests(TestCase):
    def test_existing_member_can_request_email_login_when_signup_is_closed(self):
        user = get_user_model().objects.create_user(
            username="existing-member",
            email="existing@example.test",
        )
        MemberProfile.objects.create(
            user=user,
            email_key=user.email,
            email_login_enabled=True,
            email_verified_at=timezone.now(),
            age_band="adult",
            accepted_at=timezone.now(),
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True,
        )

        self.assertFalse(settings.POST_SIGNUP_ENABLED)
        self.assertTrue(settings.POST_AUTH_EMAIL_ENABLED)
        response = self.client.post(
            "/accounts/email/", {"email": user.email}, secure=True
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(EmailChallenge.objects.filter(user=user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_unknown_email_does_not_create_account_or_send_mail_when_signup_is_closed(self):
        response = self.client.post(
            "/accounts/email/", {"email": "unknown@example.test"}, secure=True
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(EmailChallenge.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
