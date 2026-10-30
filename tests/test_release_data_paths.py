"""A released service must be able to keep its existing database and static data tree."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class ReleaseDataPathTests(unittest.TestCase):
    def test_release_code_can_use_external_data_and_database_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "existing-data"
            database = Path(tmp) / "protected" / "news.db"
            env = os.environ.copy()
            env["TEEMO_DATA_ROOT"] = str(data_root)
            env["TEEMO_NEWS_DB_FILE"] = str(database)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from server import live_news_dashboard as app; "
                        "from server import admin_auth; "
                        "print(app.ROOT); print(app.DB_FILE); "
                        "print(admin_auth.PASSWORD_FILE)"
                    ),
                ],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.stdout.splitlines(),
                [
                    str(data_root.resolve()),
                    str(database.resolve()),
                    str((data_root / ".admin_password").resolve()),
                ],
            )

    def test_page_builder_keeps_code_and_output_roots_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "existing-data"
            env = os.environ.copy()
            env["TEEMO_DATA_ROOT"] = str(data_root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pages.build import page_build as build; "
                        "print(build.ROOT); print(build.DATA_ROOT); "
                        "print(build.BLOG_CONTENT_DIR); "
                        "build.write(build.DATA_ROOT / 'release-probe.html', 'ok')"
                    ),
                ],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.stdout.splitlines(),
                [
                    str(ROOT.resolve()),
                    str(data_root.resolve()),
                    str((data_root / "content" / "blog").resolve()),
                ],
            )
            self.assertEqual((data_root / "release-probe.html").read_text(), "ok")
            self.assertFalse((ROOT / "release-probe.html").exists())


if __name__ == "__main__":
    unittest.main()
