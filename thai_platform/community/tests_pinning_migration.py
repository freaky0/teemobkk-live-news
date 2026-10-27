from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PinMigrationTests(TransactionTestCase):
    def test_existing_posts_preserved_and_unpinned(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('community', '0017_alter_post_category')])
        old_apps = executor.loader.project_state([('community', '0017_alter_post_category')]).apps
        User = old_apps.get_model('auth', 'User')
        Post = old_apps.get_model('community', 'Post')
        user = User.objects.create(username='legacy-user')
        post = Post.objects.create(author_id=user.pk, title='Legacy title', body='Legacy body', category='notice')
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([('community', '0018_post_is_pinned')])
            apps = executor.loader.project_state([('community', '0018_post_is_pinned')]).apps
            migrated = apps.get_model('community', 'Post').objects.get(pk=post.pk)
            self.assertEqual((migrated.title, migrated.body, migrated.category, migrated.is_pinned), ('Legacy title', 'Legacy body', 'notice', False))
        finally:
            MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
