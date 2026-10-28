from django.core.cache import cache
from django.test import TestCase


class CacheIsolationTests(TestCase):
    def test_a_cache_state_can_be_used_within_a_test(self):
        cache.set('test-isolation-probe', 'present')
        self.assertEqual(cache.get('test-isolation-probe'), 'present')

    def test_b_cache_state_does_not_leak_between_tests(self):
        self.assertIsNone(cache.get('test-isolation-probe'))


class AnotherCacheIsolationTests(TestCase):
    def test_cache_is_available(self):
        self.assertIsNone(cache.get('another-probe'))
