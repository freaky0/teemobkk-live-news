from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import Client, TransactionTestCase
from django.utils import timezone
from .models import MemberProfile

class ProfileConcurrentTests(TransactionTestCase):
    def test_simultaneous_changes_allow_at_most_one(self):
        user = get_user_model().objects.create_user(username='original', email='race@example.com')
        profile = MemberProfile.objects.create(user=user, email_key=user.email, email_verified_at=timezone.now(), accepted_at=timezone.now(), nickname_key='original')
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(user)
        barrier = Barrier(2)
        def change(pair):
            client, nickname = pair
            close_old_connections()
            barrier.wait()
            try:
                return client.post('/accounts/profile/edit/', {'nickname': nickname}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(change, zip(clients, ['first', 'second'])))
        self.assertEqual(results, [302, 302])
        profile.refresh_from_db(); user.refresh_from_db()
        self.assertIn(user.username, ['first', 'second'])
        self.assertEqual(profile.nickname_key, user.username)
        self.assertIsNotNone(profile.nickname_changed_at)
