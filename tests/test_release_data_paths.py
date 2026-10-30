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
                    "from server import live_news_dashboard as app; print(app.ROOT); print(app.DB_FILE)",
                ],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.stdout.splitlines(),
                [str(data_root.resolve()), str(database.resolve())],
            )


if __name__ == "__main__":
    unittest.main()
