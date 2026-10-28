"""Acceptance contract for physically independent community board post storage.

Run against a disposable Django test database, never a production database.
The public routes and globally-addressed post IDs are existing compatibility APIs.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from .models import Post, Comment, Bookmark


BOARDS = ('notice', 'free', 'market', 'jobs', 'living')


class IndependentBoardAcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.member = User.objects.create_user(username='storage-member')
        cls.other = User.objects.create_user(username='storage-other')
        cls.staff = User.objects.create_user(username='storage-staff', is_staff=True)

    def create(self, board, title):
        self.client.force_login(self.staff if board == 'notice' else self.member)
        response = self.client.post('/api/v1/posts/', {
            'title': title, 'body': 'An independently stored community post.',
            'category': board, 'region': 'common',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def title_tables(self, title):
        """Locate concrete rows without requiring specific model/table names."""
        found = set()
        with connection.cursor() as cursor:
            for table in connection.introspection.table_names(cursor):
                if not table.startswith('community_'):
                    continue
                columns = {c.name for c in connection.introspection.get_table_description(cursor, table)}
                if 'title' not in columns:
                    continue
                quoted = connection.ops.quote_name(table)
                cursor.execute(f'SELECT COUNT(*) FROM {quoted} WHERE title = %s', [title])
                if cursor.fetchone()[0]:
                    found.add(table)
        return found

    def test_each_board_writes_a_distinct_concrete_post_table(self):
        tables = {}
        for board in BOARDS:
            title = f'Unique storage marker {board}'
            self.create(board, title)
            # A shared identity table may coexist, but each board needs its own
            # physical table containing its post, not a proxy or category filter.
            tables[board] = self.title_tables(title) - {Post._meta.db_table}
        for board in BOARDS:
            with self.subTest(board=board):
                self.assertTrue(tables[board], f'{board}: no board-specific table contains its post')
        for board in BOARDS:
            for other in BOARDS:
                if board != other:
                    self.assertFalse(tables[board] & tables[other], f'{board} and {other} share post storage')

    def test_api_and_web_filter_boards_without_leaking_other_posts(self):
        titles = {b: f'Board isolation marker {b}' for b in BOARDS}
        for board, title in titles.items():
            self.create(board, title)
        self.client.logout()
        for board in BOARDS:
            with self.subTest(board=board):
                for url in (f'/community/?category={board}', f'/api/v1/posts/?category={board}'):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, titles[board])
                    for other in BOARDS:
                        if other != board:
                            self.assertNotContains(response, titles[other])

    def test_web_create_api_edit_and_web_delete_keep_identity(self):
        for board in BOARDS:
            with self.subTest(board=board):
                self.client.force_login(self.staff if board == 'notice' else self.member)
                title = f'Lifecycle original {board}'
                payload = {'title': title, 'body': 'An adequately long community post body.',
                           'category': board, 'region': 'common', 'privacy': 'on'}
                response = self.client.post('/community/new/', payload)
                self.assertEqual(response.status_code, 302, response.content)
                post = Post.objects.get(title=title)
                updated = f'Lifecycle updated {board}'
                response = self.client.patch(f'/api/v1/posts/{post.pk}/', {'title': updated}, content_type='application/json')
                self.assertEqual(response.status_code, 200, response.content)
                self.assertContains(self.client.get(f'/community/{post.pk}/'), updated)
                board_tables = self.title_tables(updated) - {Post._meta.db_table}
                self.assertEqual(self.client.post(f'/community/{post.pk}/delete/').status_code, 302)
                self.assertNotContains(self.client.get(f'/community/?category={board}'), updated)
                self.assertEqual(self.client.get(f'/api/v1/posts/{post.pk}/').status_code, 404)
                self.assertTrue(board_tables, f'{board}: updated row absent from board table')

    def test_notice_writes_and_other_authors_remain_protected(self):
        notice = self.create('notice', 'Restricted notice marker')
        free = self.create('free', 'Restricted member marker')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post('/api/v1/posts/', {'title': 'Forged notice', 'body': 'Not permitted', 'category': 'notice'}, content_type='application/json').status_code, 403)
        for pk in (notice, free):
            with self.subTest(pk=pk):
                self.assertEqual(self.client.patch(f'/api/v1/posts/{pk}/', {'title': 'Forged edit'}, content_type='application/json').status_code, 403)
                self.assertEqual(self.client.post(f'/community/{pk}/delete/').status_code, 403)
        self.assertContains(self.client.get(f'/community/{notice}/'), 'Restricted notice marker')
        self.assertContains(self.client.get(f'/community/{free}/'), 'Restricted member marker')

    def test_existing_shared_comment_and_bookmark_follow_board_post(self):
        for board in BOARDS:
            with self.subTest(board=board):
                pk = self.create(board, f'Shared engagement {board}')
                post = Post.objects.get(pk=pk)
                comment = Comment.objects.create(post=post, author=self.other, body=f'Comment on {board}')
                bookmark = Bookmark.objects.create(post=post, user=self.other)
                self.assertContains(self.client.get(f'/community/{pk}/'), comment.body)
                self.assertEqual(bookmark.post_id, pk)
                self.assertEqual(comment.post_id, pk)
