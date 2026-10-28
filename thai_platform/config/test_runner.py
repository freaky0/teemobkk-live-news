"""Keep test caches isolated without changing application throttling."""
from unittest import TextTestResult

from django.core.cache import caches
from django.test import override_settings
from django.test.runner import (
    DiscoverRunner, ParallelTestSuite, RemoteTestResult, RemoteTestRunner,
)


class IsolatedRemoteResult(RemoteTestResult):
    def startTest(self, test):
        caches['default'].clear()
        super().startTest(test)


class IsolatedRemoteRunner(RemoteTestRunner):
    resultclass = IsolatedRemoteResult


class IsolatedParallelSuite(ParallelTestSuite):
    runner_class = IsolatedRemoteRunner


class IsolatedCacheTestRunner(DiscoverRunner):
    parallel_test_suite = IsolatedParallelSuite
    def setup_test_environment(self, **kwargs):
        # Never clear a configured external cache when running tests.
        self._test_caches = override_settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'isolated-test-cache',
            },
        })
        self._test_caches.enable()
        super().setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        try:
            super().teardown_test_environment(**kwargs)
        finally:
            self._test_caches.disable()

    def get_resultclass(self):
        parent = super().get_resultclass() or TextTestResult

        class IsolatedCacheResult(parent):
            def startTest(self, test):
                caches['default'].clear()
                super().startTest(test)

        return IsolatedCacheResult
