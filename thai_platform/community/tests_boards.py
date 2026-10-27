from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from . import services
from .models import Post


class BoardTests(TestCase):
    def test_each_new_board_can_create_filter_and_edit(self):
        user = get_user_model().objects.create_user(username='writer')
        self.client.force_login(user)
        for category in ('free', 'questions', 'market', 'jobs', 'foodtravel'):
            with self.subTest(category=category):
                form = self.client.get(f'/community/new/?category={category}')
                self.assertEqual(form.context['form']['category'].value(), category)
                payload = {'title': f'Test {category} post', 'body': 'This is a sufficiently long community post.', 'region': 'common', 'category': category, 'privacy': 'on'}
                response = self.client.post('/community/new/', payload)
                self.assertEqual(response.status_code, 302)
                post = Post.objects.get(title=payload['title'])
                self.assertEqual(post.category, category)
                self.assertContains(self.client.get(f'/community/?category={category}'), payload['title'])
                payload['title'] = f'Edited {category} post'
                self.assertEqual(self.client.post(f'/community/{post.pk}/edit/', payload).status_code, 302)
                post.refresh_from_db()
                self.assertEqual(post.category, category)
                self.assertEqual(post.title, payload['title'])

    def test_board_links_and_legacy_posts_remain_accessible(self):
        user = get_user_model().objects.create_user(username='writer')
        legacy = Post.objects.create(author=user, title='Legacy question', body='Old content', category='visa')
        response = self.client.get('/community/')
        for category in ('notice', 'free', 'questions', 'market', 'jobs', 'foodtravel', 'housing', 'visa'):
            self.assertContains(response, f'category={category}')
        self.assertContains(self.client.get('/community/?category=visa'), legacy.title)
        self.assertEqual(Post.objects.get(pk=legacy.pk).category, 'visa')

    def test_notice_write_requires_moderator_and_prevents_category_bypass(self):
        User = get_user_model()
        member = User.objects.create_user(username='member')
        staff = User.objects.create_user(username='staff', is_staff=True)
        data = {'title': 'Notice title', 'body': 'Notice body', 'category': 'notice'}
        with self.assertRaises(PermissionDenied):
            services.create_post(member, data)
        notice = services.create_post(staff, data)
        self.assertContains(self.client.get('/community/?category=notice'), notice.title)
        with self.assertRaises(PermissionDenied):
            services.update_post(member, notice, {'category': 'living'})
        with self.assertRaises(PermissionDenied):
            services.delete_post(member, notice)
        ordinary = services.create_post(member, {'title': 'Normal title', 'body': 'Normal body', 'category': 'living'})
        with self.assertRaises(PermissionDenied):
            services.update_post(member, ordinary, {'category': 'notice'})

    def test_notice_api_and_web_reject_forged_member_writes(self):
        User = get_user_model()
        member = User.objects.create_user(username='member')
        staff = User.objects.create_user(username='staff', is_staff=True)
        notice = Post.objects.create(author=staff, title='Public notice', body='Public notice content', category='notice')
        ordinary = Post.objects.create(author=member, title='Ordinary post', body='Ordinary content', category='living')
        self.client.force_login(member)
        payload = {'title': 'Forged notice', 'body': 'This content is long enough for the form.', 'region': 'common', 'category': 'notice', 'privacy': 'on'}
        self.assertEqual(self.client.post('/community/new/', payload).status_code, 403)
        self.assertEqual(self.client.post(f'/community/{notice.pk}/delete/').status_code, 403)
        self.assertEqual(self.client.post(f'/community/{ordinary.pk}/edit/', payload).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/v1/posts/{ordinary.pk}/', data='{"category":"notice"}', content_type='application/json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/v1/posts/{notice.pk}/').status_code, 403)
        ordinary.refresh_from_db(); notice.refresh_from_db()
        self.assertEqual(ordinary.category, 'living')
        self.assertEqual(notice.status, Post.Status.PUBLISHED)
