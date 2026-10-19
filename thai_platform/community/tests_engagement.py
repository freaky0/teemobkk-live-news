from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from rest_framework.test import APIClient
from .models import Post, Comment


class EngagementTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username='activity-owner', email='private@example.test')
        self.other = users.objects.create_user(username='activity-other')
        self.post = Post.objects.create(author=self.owner, title='저장과 반응 검사 질문', body='테스트 자료입니다.')
        self.api = APIClient()

    def test_authority_validation_and_unavailable_posts(self):
        from members.models import MemberProfile
        for action in ['helpful', 'bookmark']:
            url = f'/api/v1/posts/{self.post.pk}/{action}/'
            self.assertEqual(self.api.post(url, {'active': True}, format='json').status_code, 403)
            self.api.force_authenticate(self.owner)
            for data in [{}, {'active': 'invalid'}, {'active': True, 'user': self.other.pk}]:
                self.assertEqual(self.api.post(url, data, format='json').status_code, 400)
            self.assertEqual(self.api.get(url).status_code, 405)
            csrf = APIClient(enforce_csrf_checks=True)
            csrf.force_login(self.owner)
            self.assertEqual(csrf.post(url, {'active': True}, format='json').status_code, 403)
            for status in ['hidden', 'deleted']:
                self.post.status = status
                self.post.save()
                self.assertEqual(self.api.post(url, {'active': True}, format='json').status_code, 404)
                self.client.force_login(self.owner)
                self.assertEqual(self.client.post(f'/community/{self.post.pk}/{action}/', {'active': 'true'}).status_code, 404)
            self.post.status = 'published'
            self.post.save()
            self.api.force_authenticate(None)
        MemberProfile.objects.create(user=self.owner, email_key='incomplete@example.test')
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.post(f'/api/v1/posts/{self.post.pk}/helpful/', {'active': True}, format='json').status_code, 403)
        self.assertEqual(self.api.post(f'/api/v1/posts/{self.post.pk}/bookmark/', {'active': True}, format='json').status_code, 403)

    def test_database_unique_constraints_and_audit_privacy(self):
        from .models import Helpful, Bookmark, AuditEvent
        for model in [Helpful, Bookmark]:
            model.objects.create(user=self.owner, post=self.post)
            with self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(user=self.owner, post=self.post)
        self.api.force_authenticate(self.owner)
        self.api.post(f'/api/v1/posts/{self.post.pk}/bookmark/', {'active': False}, format='json')
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_activity_types_exclude_other_users_and_hidden_content(self):
        from .models import Helpful, Bookmark
        alien = Post.objects.create(author=self.other, title='다른 회원만의 질문', body='Other')
        Comment.objects.create(author=self.owner, post=self.post, body='내 답변')
        Comment.objects.create(author=self.other, post=alien, body='다른 회원 답변')
        Helpful.objects.create(user=self.owner, post=self.post)
        Bookmark.objects.create(user=self.owner, post=self.post)
        self.api.force_authenticate(self.owner)
        for kind in ['posts', 'comments', 'helpful', 'bookmarks']:
            response = self.api.get(f'/api/v1/activity/?kind={kind}')
            self.assertEqual(response.data['count'], 1)
            self.assertNotIn('다른 회원', str(response.data))
        self.post.status = 'hidden'
        self.post.save()
        for kind in ['posts', 'comments', 'helpful', 'bookmarks']:
            self.assertEqual(self.api.get(f'/api/v1/activity/?kind={kind}').data['count'], 0)
        self.assertEqual(self.api.get('/api/v1/activity/?kind=bogus').status_code, 400)

    def test_mutation_responses_keep_counts_and_my_state(self):
        self.api.force_authenticate(self.owner)
        self.api.post(f'/api/v1/posts/{self.post.pk}/helpful/', {'active': True}, format='json')
        self.api.post(f'/api/v1/posts/{self.post.pk}/bookmark/', {'active': True}, format='json')
        responses = [
            self.api.patch(f'/api/v1/posts/{self.post.pk}/', {'title': '제목을 수정한 테스트 질문'}, format='json'),
            self.api.post(f'/api/v1/posts/{self.post.pk}/resolution/', {'resolution': 'resolved'}, format='json'),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['helpful_count'], 1)
            self.assertTrue(response.data['helpful_active'])
            self.assertTrue(response.data['bookmarked'])

    def test_activity_pagination_is_bounded(self):
        from .models import Bookmark
        posts = Post.objects.bulk_create([Post(author=self.owner, title=f'저장 글 {i}', body='Test') for i in range(25)])
        Bookmark.objects.bulk_create([Bookmark(user=self.owner, post=post) for post in posts])
        self.api.force_authenticate(self.owner)
        first = self.api.get('/api/v1/activity/?kind=bookmarks')
        second = self.api.get('/api/v1/activity/?kind=bookmarks&page=2')
        self.assertEqual(first.data['count'], 25)
        self.assertEqual(len(first.data['results']), 20)
        self.assertEqual(len(second.data['results']), 5)
        self.assertTrue(first.data['next'])
        self.assertFalse({x['id'] for x in first.data['results']} & {x['id'] for x in second.data['results']})

    def test_post_list_has_no_per_row_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.api.force_authenticate(self.owner)
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.api.get('/api/v1/posts/').status_code, 200)
        Post.objects.bulk_create([Post(author=self.owner, title=f'질문 {i}', body='Test') for i in range(15)])
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.api.get('/api/v1/posts/').status_code, 200)
        self.assertEqual(len(small), len(large))

    def test_bookmarks_and_activity_are_private(self):
        self.api.force_authenticate(self.owner)
        url = f'/api/v1/posts/{self.post.pk}/bookmark/'
        for _ in range(2):
            self.assertEqual(self.api.post(url, {'active': True}, format='json').status_code, 200)
        response = self.api.get('/api/v1/activity/?kind=bookmarks')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.post.pk)
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get('/api/v1/activity/?kind=bookmarks').data['count'], 0)
        self.assertEqual(self.api.get(f'/api/v1/activity/?kind=bookmarks&user={self.owner.pk}').data['count'], 0)
        self.assertEqual(self.api.get(f'/api/v1/activity/{self.owner.pk}/').status_code, 404)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get('/api/v1/activity/').status_code, 403)
        self.assertEqual(self.client.get('/community/activity/').status_code, 403)

    def test_public_counts_and_viewer_state_do_not_leak(self):
        self.api.force_authenticate(self.owner)
        self.api.post(f'/api/v1/posts/{self.post.pk}/helpful/', {'active': True}, format='json')
        self.api.post(f'/api/v1/posts/{self.post.pk}/bookmark/', {'active': True}, format='json')
        own = self.api.get(f'/api/v1/posts/{self.post.pk}/')
        self.assertEqual(own.data['helpful_count'], 1)
        self.assertTrue(own.data['helpful_active'])
        self.assertTrue(own.data['bookmarked'])
        self.assertEqual(own['Cache-Control'], 'no-store, private')
        self.api.force_authenticate(self.other)
        other = self.api.get(f'/api/v1/posts/{self.post.pk}/')
        self.assertFalse(other.data['helpful_active'])
        self.assertFalse(other.data['bookmarked'])
        self.assertEqual(other.data['helpful_count'], 1)
        self.api.force_authenticate(None)
        public = self.api.get(f'/api/v1/posts/{self.post.pk}/')
        self.assertFalse(public.data['helpful_active'])
        self.assertFalse(public.data['bookmarked'])
        for key in ['helpful_votes', 'bookmarks', 'email', 'voters', 'saved_by']:
            self.assertNotIn(key, public.data)
        self.assertNotIn('private@example.test', str(public.data))

    def test_web_actions_and_activity(self):
        for action in ['helpful', 'bookmark']:
            url = f'/community/{self.post.pk}/{action}/'
            self.assertEqual(self.client.post(url, {'active': 'true'}).status_code, 403)
            csrf = Client(enforce_csrf_checks=True)
            csrf.force_login(self.owner)
            self.assertEqual(csrf.post(url, {'active': 'true'}).status_code, 403)
            csrf.get(f'/community/{self.post.pk}/')
            result = csrf.post(url, {'active': 'true', 'csrfmiddlewaretoken': csrf.cookies['csrftoken'].value})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.owner)
        response = self.client.get('/community/activity/?kind=bookmarks')
        self.assertContains(response, self.post.title)
        self.assertContains(response, '비공개 스크랩')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('private', response['Cache-Control'])
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/community/activity/?kind=bookmarks'), self.post.title)

    def test_helpful_repeated_request_is_single_vote(self):
        self.api.force_authenticate(self.owner)
        url = f'/api/v1/posts/{self.post.pk}/helpful/'
        for _ in range(3):
            response = self.api.post(url, {'active': True}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {'active': True, 'helpful_count': 1})
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.post(url, {'active': True}, format='json').data['helpful_count'], 2)
        self.assertEqual(self.api.post(url, {'active': False}, format='json').data['helpful_count'], 1)
