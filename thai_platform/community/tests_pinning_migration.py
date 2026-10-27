from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PinMigrationTests(TransactionTestCase):
    def test_old_model_can_insert_after_latest_migrations(self):
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state([('community', '0017_alter_post_category')]).apps
        OldPost = old_apps.get_model('community', 'Post')
        User = old_apps.get_model('auth', 'User')
        user = User.objects.create(username='rollback-user')
        post = OldPost.objects.create(author_id=user.pk, title='Rollback', body='Old release', category='notice')
        from community.models import Post
        self.assertFalse(Post.objects.get(pk=post.pk).is_pinned)

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
            executor.migrate([('community', '0019_merge_pin_memberblock')])
            apps = executor.loader.project_state([('community', '0019_merge_pin_memberblock')]).apps
            migrated = apps.get_model('community', 'Post').objects.get(pk=post.pk)
            self.assertEqual((migrated.title, migrated.body, migrated.category, migrated.is_pinned), ('Legacy title', 'Legacy body', 'notice', False))
            self.assertEqual(apps.get_model('community', 'MemberBlock').objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
