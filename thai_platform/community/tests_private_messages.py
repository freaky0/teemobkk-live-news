from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone
from members.models import MemberProfile


class PrivateMessageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.alice = self.member('alice')
        self.bob = self.member('bob')
        self.eve = self.member('eve')

    def member(self, name):
        user = get_user_model().objects.create_user(username=name)
        MemberProfile.objects.create(user=user, email_key=name + '@example.test', nickname_key=name,
                                     email_verified_at=timezone.now(), accepted_at=timezone.now())
        return user

    def send(self, body='private <script>alert(1)</script>', recipient='bob'):
        return self.client.post('/community/messages/send/', {'recipient': recipient, 'body': body})

    def test_private_inbox_sent_read_and_notification(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.send().status_code, 302)
        self.assertContains(self.client.get('/community/messages/sent/'), 'private &lt;script&gt;', html=False)
        self.client.force_login(self.eve)
        self.assertNotContains(self.client.get('/community/messages/'), 'private &lt;script&gt;')
        self.assertEqual(self.client.get('/community/messages/1/').status_code, 404)
        self.assertEqual(self.client.post('/community/messages/1/read/').status_code, 404)
        self.client.force_login(self.bob)
        inbox = self.client.get('/community/messages/')
        self.assertContains(inbox, 'private &lt;script&gt;', html=False)
        self.assertIn('no-store', inbox['Cache-Control'])
        self.assertIn('private', inbox['Cache-Control'])
        notification = self.client.get('/community/notifications/')
        self.assertContains(notification, '새 쪽지가 도착했습니다')
        self.assertNotContains(notification, 'private &lt;script&gt;')
        self.assertEqual(self.client.post('/community/messages/1/read/').status_code, 302)
        from .models import PrivateMessage
        self.assertIsNotNone(PrivateMessage.objects.get(pk=1).read_at)

    def test_auth_csrf_validation_and_limits(self):
        self.assertEqual(self.send().status_code, 302)
        self.client.force_login(self.alice)
        for recipient, body in [('nobody', 'x'), ('alice', 'x'), ('bob', ' '), ('bob', 'x' * 3001)]:
            self.assertEqual(self.send(body, recipient).status_code, 400)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.alice)
        self.assertEqual(csrf.post('/community/messages/send/', {'recipient': 'bob', 'body': 'x'}).status_code, 403)
        cache.clear()
        for _ in range(10):
            self.assertEqual(self.send('valid message').status_code, 302)
        self.assertEqual(self.send('too many').status_code, 429)

    def test_deletion_cannot_silently_delete_counterparty_messages(self):
        self.client.force_login(self.alice)
        self.send('preserve')
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.alice.delete()

    def test_incomplete_account_and_csrf_read_are_denied(self):
        incomplete = get_user_model().objects.create_user(username='incomplete')
        self.client.force_login(incomplete)
        self.assertEqual(self.client.get('/community/messages/').status_code, 403)
        self.client.force_login(self.alice)
        self.send('hello')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.bob)
        self.assertEqual(csrf.post('/community/messages/1/read/').status_code, 403)
        from .models import PrivateMessage
        self.assertIsNone(PrivateMessage.objects.get(pk=1).read_at)
