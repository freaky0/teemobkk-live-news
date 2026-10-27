from unittest.mock import patch
from django.db import OperationalError
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone
from .models import MemberProfile

class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='original', email='person@example.com')
        self.profile = MemberProfile.objects.create(user=self.user, email_key=self.user.email, email_verified_at=timezone.now(), accepted_at=timezone.now(), nickname_key='original')
        self.client.force_login(self.user)

    def test_profile_lookup_lock_returns_retryable_response(self):
        with patch('members.views.MemberProfile.objects.filter', side_effect=OperationalError('locked')):
            response = self.client.post('/accounts/profile/edit/', {'nickname': 'newname'})
        self.assertEqual(response.status_code, 503)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'original')

    def test_change_nickname_and_enforce_thirty_day_cooldown(self):
        response = self.client.post('/accounts/profile/edit/', {'nickname': 'newname'})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db(); self.profile.refresh_from_db()
        self.assertEqual(self.user.username, 'newname')
        self.assertEqual(self.profile.nickname_key, 'newname')
        self.assertIsNotNone(self.profile.nickname_changed_at)
        self.client.post('/accounts/profile/edit/', {'nickname': 'another'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newname')
        MemberProfile.objects.filter(pk=self.profile.pk).update(nickname_changed_at=timezone.now()-timedelta(days=30, seconds=1))
        self.client.post('/accounts/profile/edit/', {'nickname': 'another'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'another')

    def test_rejects_invalid_and_taken_nicknames_without_changing_other_user(self):
        other = get_user_model().objects.create_user(username='other', email='other@example.com')
        MemberProfile.objects.create(user=other, email_key=other.email, nickname_key='other')
        for nickname in ['other', '<script>', 'x']:
            self.client.post('/accounts/profile/edit/', {'nickname': nickname, 'user': other.pk})
        self.user.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(self.user.username, 'original')
        self.assertEqual(other.username, 'other')

    def test_choose_avatar_and_reject_unknown_choice(self):
        self.client.post('/accounts/profile/avatar/', {'avatar': 'cat'})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar, 'cat')
        self.client.post('/accounts/profile/avatar/', {'avatar': '../evil.svg'})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar, 'cat')

    def test_unauthenticated_and_csrf_rejected(self):
        self.assertEqual(Client().post('/accounts/profile/edit/', {'nickname':'stranger'}).status_code, 302)
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post('/accounts/profile/edit/', {'nickname':'stranger'}).status_code, 403)
        self.user.refresh_from_db(); self.assertEqual(self.user.username, 'original')
