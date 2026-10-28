from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class BoardContentMigrationTests(TransactionTestCase):
    def test_backfill_preserves_existing_rows_and_legacy_categories(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate([('community', '0028_freepost_jobspost_livingpost_marketpost_noticepost')])
        apps = executor.loader.project_state([('community', '0028_freepost_jobspost_livingpost_marketpost_noticepost')]).apps
        User = apps.get_model('auth', 'User')
        Post = apps.get_model('community', 'Post')
        FreePost = apps.get_model('community', 'FreePost')
        user = User.objects.create(username='migration-user')
        posts = {}
        for category in ('notice', 'free', 'market', 'jobs', 'living', 'housing', 'banking', 'questions'):
            posts[category] = Post.objects.create(author_id=user.pk, category=category, title=f'{category} title', body=f'{category} body', status='hidden')
        existing = Post.objects.create(author_id=user.pk, category='free', title='', body='')
        FreePost.objects.create(post_id=existing.pk, title='Existing slice', body='Do not overwrite')
        executor = MigrationExecutor(connection)
        executor.migrate([('community', '0029_backfill_board_content')])
        apps = executor.loader.project_state([('community', '0029_backfill_board_content')]).apps
        for category, post in posts.items():
            name = {'notice': 'NoticePost', 'free': 'FreePost', 'market': 'MarketPost', 'jobs': 'JobsPost', 'living': 'LivingPost', 'housing': 'LivingPost', 'banking': 'LivingPost'}.get(category)
            if name:
                row = apps.get_model('community', name).objects.get(post_id=post.pk)
                self.assertEqual((row.title, row.body), (post.title, post.body))
        row = apps.get_model('community', 'FreePost').objects.get(post_id=existing.pk)
        self.assertEqual((row.title, row.body), ('Existing slice', 'Do not overwrite'))
        self.assertEqual(apps.get_model('community', 'Post').objects.get(pk=posts['questions'].pk).title, 'questions title')
