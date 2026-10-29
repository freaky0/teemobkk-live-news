"""Video article media extraction contract. All fixtures are synthetic."""
from pathlib import Path
from contextlib import closing
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import live_news_dashboard as core


class ArticleMediaTests(unittest.TestCase):
    def test_extracts_open_graph_video_and_static_poster(self):
        markup = '''<html><head>
        <meta property="og:video:secure_url" content="https://video.example/clip.mp4">
        <meta property="og:image" content="https://image.example/poster.jpg">
        </head></html>'''
        self.assertEqual(
            core.parse_article_media(markup, "https://publisher.example/story"),
            {
                "image_url": "https://image.example/poster.jpg",
                "video_url": "https://video.example/clip.mp4",
            },
        )

    def test_extracts_video_source_and_poster_from_article_markup(self):
        markup = '''<html><body><video poster="/media/poster.jpg" controls>
        <source src="/media/clip.mp4" type="video/mp4"></video></body></html>'''
        self.assertEqual(
            core.parse_article_media(markup, "https://publisher.example/story"),
            {
                "image_url": "https://publisher.example/media/poster.jpg",
                "video_url": "https://publisher.example/media/clip.mp4",
            },
        )

    def test_prefers_video_poster_over_generic_social_image(self):
        markup = '''<html><head><meta property="og:image" content="https://image.example/generic.jpg"></head>
        <body><video poster="https://image.example/video-frame.jpg"><source src="https://video.example/clip.mp4"></video></body></html>'''
        result = core.parse_article_media(markup, "https://publisher.example/story")
        self.assertEqual(result["image_url"], "https://image.example/video-frame.jpg")

    def test_skips_untrusted_first_iframe_and_keeps_supported_video(self):
        markup = '''<iframe src="https://ads.example/slot"></iframe>
        <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'''
        result = core.parse_article_media(markup, "https://publisher.example/story")
        self.assertEqual(result["video_url"], "https://www.youtube.com/embed/dQw4w9WgXcQ")

    def test_extracts_supported_twitter_player_metadata(self):
        markup = '''<meta name="twitter:player" content="https://www.youtube.com/embed/dQw4w9WgXcQ">'''
        result = core.parse_article_media(markup, "https://publisher.example/story")
        self.assertEqual(result["video_url"], "https://www.youtube.com/embed/dQw4w9WgXcQ")

    def test_fetch_rejects_non_http_source_without_opening_it(self):
        with patch.object(core.urllib.request, "urlopen") as urlopen:
            result = core.fetch_article_media("file:///etc/passwd")
        self.assertFalse(result["checked"])
        urlopen.assert_not_called()

    def test_init_db_adds_video_url_to_legacy_article_table(self):
        with TemporaryDirectory() as temp:
            db_path = Path(temp) / "legacy.sqlite3"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "CREATE TABLE articles (link TEXT PRIMARY KEY, title TEXT NOT NULL, "
                    "summary TEXT, source TEXT, source_type TEXT, region TEXT, category TEXT, "
                    "categories TEXT, asset TEXT, priority INTEGER, published_at TEXT NOT NULL, "
                    "collected_at TEXT)"
                )
            previous = core.DB_FILE
            try:
                core.DB_FILE = db_path
                core.init_db()
                with closing(sqlite3.connect(db_path)) as connection:
                    columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
                self.assertIn("video_url", columns)
                self.assertIn("media_checked_at", columns)
            finally:
                core.DB_FILE = previous


    def test_backfill_persists_poster_video_and_check_time(self):
        with TemporaryDirectory() as temp:
            db_path = Path(temp) / "media.sqlite3"
            previous = core.DB_FILE
            connections = []
            real_connect = core.db_connect
            def tracked_connect():
                connection = real_connect()
                connections.append(connection)
                return connection
            try:
                core.DB_FILE = db_path
                with patch.object(core, "db_connect", side_effect=tracked_connect):
                    core.init_db()
                    link = "https://publisher.example/story"
                    core.insert_articles([core.make_article(
                        "Synthetic video story", link, "A fixture summary", datetime.now(timezone.utc).isoformat(), "Fixture", "media"
                    )])
                    poster = "https://image.example/poster.jpg"
                    video = "https://video.example/story.mp4"
                    def fetch_fixture(url):
                        return {
                            "image_url": poster if url == link else "",
                            "video_url": video if url == link else "",
                            "checked": True,
                        }
                    with patch.object(core, "original_links", return_value={}), \
                         patch.object(core.google_news, "original_for", return_value=""), \
                         patch.object(core, "fetch_article_media", side_effect=fetch_fixture):
                        core.backfill_article_media(limit=1)
                connection = sqlite3.connect(db_path)
                try:
                    row = connection.execute(
                        "SELECT image_url, video_url, media_checked_at FROM articles WHERE link=?", (link,)
                    ).fetchone()
                finally:
                    connection.close()
                self.assertEqual(row[0], poster)
                self.assertEqual(row[1], video)
                self.assertTrue(row[2])
            finally:
                for connection in connections:
                    connection.close()
                core.DB_FILE = previous


if __name__ == "__main__":
    unittest.main()
