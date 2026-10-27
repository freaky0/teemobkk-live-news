from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Post


class PinningTests(TestCase):
    def test_staff_can_create_pinned_notice_and_list_it_first(self):
        staff = get_user_model().objects.create_user(username='staff', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post('/api/v1/posts/', {'title': 'Pinned notice', 'body': 'Notice body', 'category': 'notice', 'is_pinned': True}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['is_pinned'])
        Post.objects.create(author=staff, title='Newer post', body='Body', category='free')
        self.assertEqual(self.client.get('/api/v1/posts/').json()['results'][0]['title'], 'Pinned notice')

    def test_staff_web_create_and_unpin_notice(self):
        staff = get_user_model().objects.create_user(username='webstaff', is_staff=True)
        self.client.force_login(staff)
        self.assertContains(self.client.get('/community/new/'), 'name="is_pinned"')
        data = {'title': 'Web pinned notice', 'body': 'A sufficiently long notice body for everyone.', 'region': 'common', 'category': 'notice', 'privacy': 'on', 'is_pinned': 'on'}
        self.assertEqual(self.client.post('/community/new/', data).status_code, 302)
        post = Post.objects.get(title=data['title'])
        self.assertTrue(post.is_pinned)
        self.assertContains(self.client.get('/community/'), '상단 고정')
        self.assertContains(self.client.get(f'/community/{post.pk}/'), '상단 고정')
        data.pop('is_pinned')
        self.assertEqual(self.client.post(f'/community/{post.pk}/edit/', data).status_code, 302)
        post.refresh_from_db()
        self.assertFalse(post.is_pinned)

    def test_member_cannot_forge_pin_on_web_or_api(self):
        member = get_user_model().objects.create_user(username='member')
        self.client.force_login(member)
        self.assertNotContains(self.client.get('/community/new/'), 'name="is_pinned"')
        data = {'title': 'Member normal post', 'body': 'A sufficiently long normal community body.', 'region': 'common', 'category': 'free', 'privacy': 'on', 'is_pinned': 'on'}
        self.assertEqual(self.client.post('/community/new/', data).status_code, 403)
        data.pop('privacy')
        self.assertEqual(self.client.post('/api/v1/posts/', data).status_code, 403)

    def test_api_authorization_category_transitions_and_unpin(self):
        User = get_user_model()
        member = User.objects.create_user(username='owner')
        staff = User.objects.create_user(username='operator', is_staff=True)
        post = Post.objects.create(author=member, title='Existing post', body='Body', category='free')
        self.client.force_login(member)
        url = f'/api/v1/posts/{post.pk}/'
        self.assertEqual(self.client.patch(url, {'is_pinned': True}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.patch(url, {'category': 'notice'}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post(f'/community/{post.pk}/edit/', {'is_pinned': 'on'}).status_code, 403)
        self.client.force_login(staff)
        self.assertEqual(self.client.post('/api/v1/posts/', {'title': 'Invalid pin', 'body': 'Body', 'category': 'free', 'is_pinned': True}, content_type='application/json').status_code, 400)
        notice = Post.objects.create(author=staff, title='Notice', body='Body', category='notice', is_pinned=True)
        url = f'/api/v1/posts/{notice.pk}/'
        self.assertEqual(self.client.patch(url, {'category': 'free'}, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'is_pinned': False, 'category': 'free'}, content_type='application/json').status_code, 200)
        notice.refresh_from_db()
        self.assertEqual((notice.category, notice.is_pinned), ('free', False))

    def test_pagination_stays_unique_and_filters_are_respected(self):
        user = get_user_model().objects.create_user(username='pages')
        pinned = Post.objects.create(author=user, title='Pinned', body='Body', category='notice', is_pinned=True)
        Post.objects.bulk_create([Post(author=user, title=f'Post {i}', body='Body', category='free') for i in range(25)])
        first = self.client.get('/api/v1/posts/?page=1').json()
        second = self.client.get('/api/v1/posts/?page=2').json()
        ids = [item['id'] for item in first['results'] + second['results']]
        self.assertEqual(ids[0], pinned.pk)
        self.assertEqual(len(set(ids)), 26)
        filtered = self.client.get('/api/v1/posts/?category=free').json()
        self.assertEqual(filtered['count'], 25)
        self.assertNotIn(pinned.pk, [item['id'] for item in filtered['results']])
