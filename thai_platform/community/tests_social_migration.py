from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SocialMigrationTests(TransactionTestCase):
    def test_existing_post_survives_private_message_migration(self):
        old = [('community', '0014_alter_comment_parent')]
        new = [('community', '0015_alter_notification_kind_privatemessage')]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('auth', 'User').objects.create(username='preserved-post')
            post = apps.get_model('community', 'Post').objects.create(author_id=user.pk, title='Keep this', body='existing content')
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            saved = apps.get_model('community', 'Post').objects.get(pk=post.pk)
            self.assertEqual((saved.author_id, saved.title, saved.body), (user.pk, 'Keep this', 'existing content'))
            self.assertEqual(apps.get_model('community', 'PrivateMessage').objects.count(), 0)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
