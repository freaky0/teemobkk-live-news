from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from members.models import MemberProfile
from .models import Post


class MemberMenuTests(TestCase):
    def test_public_profile_only_published_posts_and_nickname(self):
        user = get_user_model().objects.create_user(username='private-login@example.test', email='private@example.test')
        MemberProfile.objects.create(user=user, email_key='private@example.test', nickname_key='publicname', accepted_at=timezone.now(), email_verified_at=timezone.now())
        Post.objects.create(author=user, title='Public title', body='public')
        Post.objects.create(author=user, title='Hidden title', body='hidden', status=Post.Status.HIDDEN)
        response = self.client.get(f'/community/members/{user.pk}/')
        self.assertContains(response, 'publicname')
        self.assertContains(response, 'Public title')
        self.assertNotContains(response, 'Hidden title')
        self.assertNotContains(response, 'private@example.test')
        self.assertNotContains(response, 'private-login@example.test')

    def test_list_nickname_menu_uses_public_nickname(self):
        user = get_user_model().objects.create_user(username='secret@example.test')
        MemberProfile.objects.create(user=user, email_key='secret@example.test', nickname_key='publicname', accepted_at=timezone.now(), email_verified_at=timezone.now())
        Post.objects.create(author=user, title='Public title', body='public')
        response = self.client.get('/community/')
        self.assertContains(response, 'publicname')
        self.assertContains(response, f'/community/members/{user.pk}/')
        self.assertNotContains(response, 'secret@example.test')

    def test_block_authorization_csrf_and_isolation(self):
        from django.test import Client
        from .models import MemberBlock, PrivateMessage
        alice = get_user_model().objects.create_user(username='alice')
        bob = get_user_model().objects.create_user(username='bob')
        eve = get_user_model().objects.create_user(username='eve')
        for user in (alice, bob, eve):
            MemberProfile.objects.create(user=user, email_key=user.username+'@example.test', nickname_key=user.username, accepted_at=timezone.now(), email_verified_at=timezone.now())
        path = f'/community/members/{bob.pk}/block/'
        self.assertEqual(self.client.post(path).status_code, 302)
        self.client.force_login(alice)
        self.assertEqual(self.client.post(f'/community/members/{alice.pk}/block/').status_code, 403)
        self.assertEqual(self.client.get(path).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(alice)
        self.assertEqual(csrf.post(path).status_code, 403)
        self.assertEqual(self.client.post('/community/messages/send/', {'recipient': 'bob', 'body': 'before'}).status_code, 302)
        self.assertEqual(self.client.post(path).status_code, 302)
        self.assertEqual(self.client.post(path).status_code, 302)
        self.assertEqual(MemberBlock.objects.count(), 1)
        self.client.force_login(eve)
        self.assertNotContains(self.client.get('/community/blocks/'), 'bob')
        self.assertEqual(self.client.post(f'/community/members/{bob.pk}/unblock/').status_code, 302)
        self.assertEqual(MemberBlock.objects.count(), 1)
        self.assertEqual(PrivateMessage.objects.count(), 1)
        self.client.force_login(bob)
        self.assertContains(self.client.get('/community/messages/'), 'before')

    def test_block_prevents_messages_both_ways_and_can_be_reversed(self):
        from .models import PrivateMessage
        alice = get_user_model().objects.create_user(username='alice')
        bob = get_user_model().objects.create_user(username='bob')
        for user in (alice, bob):
            MemberProfile.objects.create(user=user, email_key=user.username+'@example.test', nickname_key=user.username, accepted_at=timezone.now(), email_verified_at=timezone.now())
        self.client.force_login(alice)
        self.assertEqual(self.client.post(f'/community/members/{bob.pk}/block/').status_code, 302)
        self.assertEqual(self.client.post('/community/messages/send/', {'recipient': 'bob', 'body': 'blocked'}).status_code, 400)
        self.client.force_login(bob)
        self.assertEqual(self.client.post('/community/messages/send/', {'recipient': 'alice', 'body': 'blocked'}).status_code, 400)
        self.assertEqual(PrivateMessage.objects.count(), 0)
        self.client.force_login(alice)
        self.assertEqual(self.client.post(f'/community/members/{bob.pk}/unblock/').status_code, 302)
        self.assertEqual(self.client.post('/community/messages/send/', {'recipient': 'bob', 'body': 'allowed'}).status_code, 302)
