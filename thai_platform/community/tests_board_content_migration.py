from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from .models import FreePost, Post

CUTOVER = [('community', '0028_freepost_jobspost_livingpost_marketpost_noticepost')]
TARGET = [('community', '0029_backfill_board_content')]


class BoardContentMigrationTests(TransactionTestCase):
    """Round-trips are verified through a real migrate forward and back.

    TransactionTestCase flushes tables during migrate(), so fixtures are created
    inside an atomic block after the forward migration: the flush rolls back the
    outer test transaction, and the committed fixture rows survive it.
    """

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.leaves = self.executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(self.leaves))

    def apps_at(self, targets):
        return self.executor.loader.project_state(targets).apps

    def test_backfill_preserves_existing_rows_and_legacy_categories(self):
        self.executor.migrate(CUTOVER)
        apps = self.apps_at(CUTOVER)
        user = apps.get_model('auth', 'User').objects.create(username='migration-user')
        posts = {}
        for category in ('notice', 'free', 'market', 'jobs', 'living', 'housing', 'banking', 'questions'):
            posts[category] = apps.get_model('community', 'Post').objects.create(
                author_id=user.pk, category=category, title=f'{category} title',
                body=f'{category} body', status='hidden')
        existing = apps.get_model('community', 'Post').objects.create(
            author_id=user.pk, category='free', title='', body='')
        apps.get_model('community', 'FreePost').objects.create(
            post_id=existing.pk, title='Existing slice', body='Do not overwrite')
        MigrationExecutor(connection).migrate(TARGET)
        apps = self.apps_at(TARGET)
        for category, post in posts.items():
            name = {'notice': 'NoticePost', 'free': 'FreePost', 'market': 'MarketPost',
                    'jobs': 'JobsPost', 'living': 'LivingPost', 'housing': 'LivingPost',
                    'banking': 'LivingPost'}.get(category)
            if name:
                row = apps.get_model('community', name).objects.get(post_id=post.pk)
                self.assertEqual((row.title, row.body), (post.title, post.body))
        row = apps.get_model('community', 'FreePost').objects.get(post_id=existing.pk)
        self.assertEqual((row.title, row.body), ('Existing slice', 'Do not overwrite'))
        self.assertEqual(apps.get_model('community', 'Post').objects.get(pk=posts['questions'].pk).title,
                         'questions title')

    def test_reverse_restores_authoritative_content_before_schema_drop(self):
        """A reversal that silently dropped rows would leave the stale legacy text."""
        self.executor.migrate(TARGET)
        with transaction.atomic():
            user = get_user_model().objects.create_user(username='reverse-owner')
            post = Post.objects.create(author_id=user.pk, category='free',
                                       title='Legacy title', body='Legacy body')
            FreePost.objects.create(post_id=post.pk, title='Authoritative title',
                                    body='Authoritative body')
        MigrationExecutor(connection).migrate(CUTOVER)
        self.assertEqual(
            (Post.objects.get(pk=post.pk).title, Post.objects.get(pk=post.pk).body),
            ('Authoritative title', 'Authoritative body'))
        MigrationExecutor(connection).migrate(self.leaves)

    def test_reverse_leaves_categories_without_board_rows_untouched(self):
        self.executor.migrate(TARGET)
        with transaction.atomic():
            user = get_user_model().objects.create_user(username='reverse-legacy')
            post = Post.objects.create(author_id=user.pk, category='questions',
                                       title='No board row', body='Kept as is')
        MigrationExecutor(connection).migrate(CUTOVER)
        self.assertEqual(
            (Post.objects.get(pk=post.pk).title, Post.objects.get(pk=post.pk).body),
            ('No board row', 'Kept as is'))
        MigrationExecutor(connection).migrate(self.leaves)
