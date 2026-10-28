from django.apps import apps
from django.test import TestCase


class IndependentBoardStorageTests(TestCase):
    def test_each_board_has_a_distinct_post_table(self):
        models = {
            name: apps.get_model('community', f'{name.title()}Post', require_ready=True)
            for name in ('notice', 'free', 'market', 'jobs', 'living')
        }
        self.assertEqual(len({model._meta.db_table for model in models.values()}), 5)
        self.assertNotIn(apps.get_model('community', 'Post')._meta.db_table,
                         {model._meta.db_table for model in models.values()})
