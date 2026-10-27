from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

class ProfileMigrationTests(TransactionTestCase):
    def test_existing_member_survives_additive_migration(self):
        old = [('members', '0004_memberprofile_email_answer_notifications')]
        new = [('members', '0005_memberprofile_avatar_and_more')]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            User = apps.get_model('auth', 'User')
            Profile = apps.get_model('members', 'MemberProfile')
            user = User.objects.create(username='preserved', email='preserved@example.com')
            profile = Profile.objects.create(user_id=user.pk, email_key=user.email, nickname_key='preserved', terms_version='v1')
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            saved = apps.get_model('members', 'MemberProfile').objects.get(pk=profile.pk)
            self.assertEqual((saved.user_id, saved.email_key, saved.nickname_key, saved.terms_version), (user.pk, user.email, 'preserved', 'v1'))
            self.assertEqual(saved.avatar, 'person')
            self.assertIsNone(saved.nickname_changed_at)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
