from datetime import date
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

from django.test import RequestFactory, SimpleTestCase

from config import sitemaps


NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/sitemap.xml")

    def test_index_splits_large_news_and_community_lists(self):
        posts = Mock()
        posts.count.return_value = 4
        with (
            patch("config.sitemaps.news.sitemap_article_count", return_value=25843),
            patch("config.sitemaps.services.public_posts", return_value=posts),
        ):
            response = sitemaps.sitemap_xml(self.request)

        root = ET.fromstring(response.content)
        locations = [node.text for node in root.findall("sm:sitemap/sm:loc", NS)]
        self.assertEqual(root.tag, f"{{{NS['sm']}}}sitemapindex")
        self.assertEqual(
            locations,
            [
                "https://teemobkk.io/thai/sitemap-static.xml",
                "https://teemobkk.io/thai/sitemap-news-1.xml",
                "https://teemobkk.io/thai/sitemap-news-2.xml",
                "https://teemobkk.io/thai/sitemap-community-1.xml",
            ],
        )

    def test_news_chunk_uses_offset_and_returns_only_its_urls(self):
        articles = [
            {"id": "story-20001", "published_at": date(2026, 11, 1)},
        ]
        with (
            patch("config.sitemaps.news.sitemap_article_count", return_value=25843),
            patch("config.sitemaps.news.sitemap_articles", return_value=articles) as read_page,
            patch.object(sitemaps, "MAX_URLS_PER_SITEMAP", 20000),
        ):
            response = sitemaps.sitemap_news_xml(self.request, part=2)
            out_of_range = sitemaps.sitemap_news_xml(self.request, part=3)

        read_page.assert_called_once_with(limit=20000, offset=20000)
        root = ET.fromstring(response.content)
        locations = [node.text for node in root.findall("sm:url/sm:loc", NS)]
        self.assertEqual(locations, ["https://teemobkk.io/thai/newsroom/story-20001/"])
        self.assertEqual(out_of_range.status_code, 404)

    def test_community_chunks_use_slice_offsets(self):
        posts = Mock()
        posts.count.return_value = 3
        posts.values_list.return_value = [
            (40, date(2026, 11, 1)),
            (41, date(2026, 11, 1)),
            (42, date(2026, 11, 1)),
        ]
        with (
            patch("config.sitemaps.services.public_posts", return_value=posts),
            patch.object(sitemaps, "MAX_URLS_PER_SITEMAP", 2),
        ):
            response = sitemaps.sitemap_community_xml(self.request, part=2)

        posts.values_list.assert_called_once_with("pk", "updated_at")
        root = ET.fromstring(response.content)
        locations = [node.text for node in root.findall("sm:url/sm:loc", NS)]
        self.assertEqual(locations, ["https://teemobkk.io/thai/community/42/"])

    def test_static_sitemap_keeps_the_three_public_entry_points(self):
        response = sitemaps.sitemap_static_xml(self.request)
        root = ET.fromstring(response.content)
        locations = [node.text for node in root.findall("sm:url/sm:loc", NS)]
        self.assertEqual(
            locations,
            [
                "https://teemobkk.io/thai/",
                "https://teemobkk.io/thai/newsroom/",
                "https://teemobkk.io/thai/community/",
            ],
        )
