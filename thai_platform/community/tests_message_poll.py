from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse, set_script_prefix
from django.utils import timezone
from members.models import MemberProfile

from .models import PrivateMessage


class MessagePollTests(TestCase):
    def setUp(self):
        self.alice = self.member("alice")
        self.bob = self.member("bob")

    def member(self, username):
        user = get_user_model().objects.create_user(username=username)
        MemberProfile.objects.create(
            user=user,
            email_key=f"{username}@example.test",
            nickname_key=username,
            email_verified_at=timezone.now(),
            accepted_at=timezone.now(),
        )
        return user

    def test_count_is_authenticated_and_scoped_to_the_recipient(self):
        unread = PrivateMessage.objects.create(sender=self.alice, recipient=self.bob, body="unread")
        PrivateMessage.objects.create(
            sender=self.alice, recipient=self.bob, body="read", read_at=timezone.now()
        )
        PrivateMessage.objects.create(sender=self.bob, recipient=self.alice, body="other recipient")

        response = self.client.get("/community/messages/unread-count/")
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.bob)
        response = self.client.get("/community/messages/unread-count/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1})

        self.client.force_login(self.alice)
        response = self.client.get("/community/messages/unread-count/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1})
        self.assertEqual(unread.recipient_id, self.bob.pk)

    def test_incomplete_members_cannot_read_unread_counts(self):
        incomplete = get_user_model().objects.create_user(username="incomplete")
        self.client.force_login(incomplete)
        response = self.client.get("/community/messages/unread-count/")
        self.assertEqual(response.status_code, 403)

    def test_count_changes_when_a_message_becomes_read(self):
        item = PrivateMessage.objects.create(sender=self.alice, recipient=self.bob, body="unread")
        self.client.force_login(self.bob)

        before = self.client.get("/community/messages/unread-count/")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json(), {"count": 1})

        read = self.client.post(f"/community/messages/{item.pk}/read/")
        self.assertEqual(read.status_code, 302)
        after = self.client.get("/community/messages/unread-count/")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json(), {"count": 0})

    def test_count_response_is_private_and_not_cached(self):
        self.client.force_login(self.bob)
        response = self.client.get("/community/messages/unread-count/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_named_route_resolves_under_thai_mount_prefix(self):
        set_script_prefix("/thai/")
        self.addCleanup(set_script_prefix, "/")
        self.assertEqual(
            reverse("community-unread-count"),
            "/thai/community/messages/unread-count/",
        )
