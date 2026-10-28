from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from . import services
from .models import Post


class MarketBoardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='market-writer')
        self.client.force_login(self.user)

    def test_market_fields_are_available_when_category_changes(self):
        from .forms import PostForm

        form = PostForm(initial={'category': 'free'})
        for field_name in ('market_kind', 'market_price', 'market_region', 'market_status'):
            with self.subTest(field=field_name):
                self.assertIn(field_name, form.fields)

    def test_irrelevant_market_field_does_not_block_non_market_form(self):
        response = self.client.post('/community/new/', {
            'title': 'An ordinary post', 'body': 'A sufficiently long ordinary post body.',
            'region': 'common', 'category': 'living', 'privacy': 'on', 'market_price': 'invalid',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Post.objects.get(title='An ordinary post').market_price)

    def test_market_fields_save_and_render(self):
        payload = {
            'title': 'Used bicycle for sale',
            'body': 'A carefully maintained bicycle is available in Bangkok.',
            'region': 'bangkok', 'category': 'market', 'privacy': 'on',
            'market_kind': 'sell', 'market_price': '1250.50',
            'market_region': 'bangkok', 'market_status': 'reserved',
        }
        response = self.client.post('/community/new/', payload)
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(title=payload['title'])
        self.assertEqual(post.market_kind, 'sell')
        self.assertEqual(str(post.market_price), '1250.50')
        self.assertEqual(post.market_region, 'bangkok')
        self.assertEqual(post.market_status, 'reserved')
        detail = self.client.get(f'/community/{post.pk}/')
        self.assertContains(detail, '1,250.50 THB')
        self.assertContains(detail, '예약')
        listing = self.client.get('/community/?category=market')
        self.assertContains(listing, '1,250.50 THB')
        edit = self.client.get(f'/community/{post.pk}/edit/')
        self.assertEqual(edit.context['form']['market_kind'].value(), 'sell')

    def test_market_price_rejects_negative_and_invalid_kind(self):
        cases = (
            {'market_price': '-1', 'market_kind': 'sell'},
            {'market_price': '10', 'market_kind': 'rent'},
        )
        for bad in cases:
            with self.subTest(bad=bad):
                payload = {'title': 'Invalid market entry', 'body': 'This is a sufficiently long post body.',
                           'region': 'common', 'category': 'market', 'privacy': 'on',
                           'market_region': 'common', 'market_status': 'active', **bad}
                response = self.client.post('/community/new/', payload)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Post.objects.filter(title='Invalid market entry').exists())

    def test_non_market_payload_cannot_store_market_fields(self):
        post = services.create_post(self.user, {
            'title': 'A non-market post', 'body': 'A sufficiently long ordinary post body.',
            'category': 'living', 'market_kind': 'sell', 'market_price': '50',
            'market_region': 'bangkok', 'market_status': 'active',
        })
        post.refresh_from_db()
        self.assertEqual(post.category, 'living')
        self.assertEqual(post.market_kind, '')
        self.assertIsNone(post.market_price)
        self.assertEqual(post.market_region, '')
        self.assertEqual(post.market_status, '')


class MarketMigrationPreservationTests(TransactionTestCase):
    reset_sequences = True

    def test_existing_post_rows_survive_market_migration(self):
        executor = MigrationExecutor(connection)
        old_target = ('community', '0021_commentlike')
        executor.migrate([old_target])
        old_apps = executor.loader.project_state([old_target]).apps
        User = old_apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
        PostBefore = old_apps.get_model('community', 'Post')
        user = User.objects.create(username='legacy-market-row')
        legacy = PostBefore.objects.create(
            author_id=user.pk, title='Pre-existing post', body='Unchanged legacy body',
            category='visa', region='common',
        )
        old_pk = legacy.pk

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        leaves = executor.loader.graph.leaf_nodes()
        PostAfter = executor.loader.project_state(leaves).apps.get_model('community', 'Post')
        migrated = PostAfter.objects.get(pk=old_pk)
        self.assertEqual((migrated.author_id, migrated.title, migrated.body),
                         (user.pk, 'Pre-existing post', 'Unchanged legacy body'))
        self.assertEqual((migrated.market_kind, migrated.market_region, migrated.market_status), ('', '', ''))
        self.assertIsNone(migrated.market_price)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()
