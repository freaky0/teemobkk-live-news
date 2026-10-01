"""The jsdom suite must never inspect an unrelated listener on its default port."""
import importlib.util
import socket
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("dashboard_test_runner", Path(__file__).with_name("run.py"))
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class LocalFixtureTest(unittest.TestCase):
    def test_allocate_port_does_not_reuse_an_existing_listener(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            chosen = runner.allocate_local_port(occupied.getsockname()[1])
            self.assertNotEqual(chosen, occupied.getsockname()[1])
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", chosen))

    def test_local_suite_uses_selected_url(self):
        selected = "http://127.0.0.1:12345/"
        args = runner.suite_args([runner.LOCAL_URL], "local", selected)
        self.assertEqual(args, [selected])
        self.assertEqual(runner.suite_args(["-", runner.LIVE_EN], "live", selected), ["-", runner.LIVE_EN])


if __name__ == "__main__":
    unittest.main()
