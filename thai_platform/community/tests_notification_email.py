from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from allauth.account.models import EmailAddress
from unittest.mock import patch

from members.models import MemberProfile
from . import services
from .models import Comment, Notification, Post


@override_settings(
    DEFAULT_FROM_EMAIL="notifications@example.test",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    POST_MAIL_ENABLED=True,
    POST_PUBLIC_ORIGIN="https://preview.example.test",
)
class AnswerEmailNotificationTests(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user(
            username="question-author",
            email="author@example.test",
        )
        self.answerer = User.objects.create_user(username="answerer")
        self.post = Post.objects.create(
            author=self.author,
            title="Private question title",
            body="Private question details",
        )
        self.profile = MemberProfile.objects.create(
            user=self.author,
            email_key=self.author.email,
            email_login_enabled=True,
            email_verified_at=timezone.now(),
            email_answer_notifications=True,
            nickname_key="question-author",
            accepted_at=timezone.now(),
        )
        EmailAddress.objects.create(
            user=self.author,
            email=self.author.email,
            verified=True,
            primary=True,
        )

    def test_opted_in_author_gets_private_minimal_email_after_outer_commit(self):
        with transaction.atomic():
            comment = services.create_comment(
                self.answerer,
                self.post,
                {"body": "PRIVATE ANSWER TEXT MUST NOT BE EMAILED"},
            )
            self.assertEqual(mail.outbox, [])
            self.assertEqual(
                Notification.objects.filter(
                    recipient=self.author,
                    kind=Notification.Kind.REPLY,
                    comment=comment,
                ).count(),
                1,
            )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.author.email])
        self.assertNotIn(self.author.email, message.subject + message.body)
        self.assertNotIn(self.post.title, message.subject + message.body)
        self.assertNotIn("PRIVATE ANSWER TEXT MUST NOT BE EMAILED", message.body)
        self.assertIn(
            f"https://preview.example.test{reverse('post-detail', kwargs={'pk': self.post.pk})}",
            message.body,
        )

    def test_question_author_can_opt_in_and_opt_out_from_profile(self):
        self.profile.email_answer_notifications = False
        self.profile.save(update_fields=["email_answer_notifications"])
        self.client.force_login(self.author)

        profile_path = "/accounts/profile/"
        script_name = settings.FORCE_SCRIPT_NAME or ""
        response = self.client.get(profile_path, SCRIPT_NAME=script_name)
        self.assertContains(response, 'name="email_answer_notifications"')
        self.assertContains(response, "답변 내용은 이메일에 포함하지 않습니다.")

        response = self.client.post(
            profile_path,
            {"email_answer_notifications": "on"},
            SCRIPT_NAME=script_name,
        )
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_answer_notifications)

        response = self.client.post(profile_path, {}, SCRIPT_NAME=script_name)
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.email_answer_notifications)

    def test_profile_rejects_opt_in_without_verified_email_accessibly(self):
        self.profile.email_answer_notifications = False
        self.profile.save(update_fields=["email_answer_notifications"])
        EmailAddress.objects.filter(user=self.author).delete()
        self.client.force_login(self.author)

        response = self.client.post(
            "/accounts/profile/",
            {"email_answer_notifications": "on"},
            SCRIPT_NAME=settings.FORCE_SCRIPT_NAME or "",
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.email_answer_notifications)
        self.assertContains(response, "인증된 이메일 주소를 확인한 뒤 다시 설정해 주세요.")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_email_answer_notifications_error"')

    def test_new_profile_defaults_answer_email_notifications_to_off(self):
        user = get_user_model().objects.create_user(
            username="quiet-member",
            email="quiet@example.test",
        )
        profile = MemberProfile.objects.create(user=user, email_key=user.email)
        self.assertFalse(profile.email_answer_notifications)

    def test_opted_out_owner_keeps_in_app_notification_without_email(self):
        self.profile.email_answer_notifications = False
        self.profile.save(update_fields=["email_answer_notifications"])

        comment = services.create_comment(
            self.answerer,
            self.post,
            {"body": "Answer without email"},
        )

        self.assertEqual(mail.outbox, [])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.author,
                kind=Notification.Kind.REPLY,
                comment=comment,
            ).exists()
        )

    def test_unverified_email_address_is_never_notified(self):
        EmailAddress.objects.filter(user=self.author).delete()

        services.create_comment(
            self.answerer,
            self.post,
            {"body": "Answer to an account with no verified address"},
        )

        self.assertEqual(mail.outbox, [])

    def test_email_failure_does_not_undo_committed_answer_or_log_recipient(self):
        with patch("community.services.send_mail", side_effect=OSError(self.author.email)):
            with self.assertLogs("community.services", level="ERROR") as logged:
                with transaction.atomic():
                    comment = services.create_comment(
                        self.answerer,
                        self.post,
                        {"body": "Answer survives email failure"},
                    )

        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())
        self.assertNotIn(self.author.email, "\n".join(logged.output))

    def test_rolled_back_answer_does_not_send_email(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                services.create_comment(
                    self.answerer,
                    self.post,
                    {"body": "This answer rolls back"},
                )
                raise RuntimeError("roll back transaction")

        self.assertFalse(Comment.objects.filter(post=self.post).exists())
        self.assertEqual(mail.outbox, [])
