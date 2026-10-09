"""TEE-82: /blog/ list plus one page per imported briefing post."""
import os
import sys
import tempfile
import unittest

_sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _sys_path)

from pages.build import landing
from pages.build import page_build

SAMPLE = """---
title: "Sample post"
date: 2026-10-07
original_slug: sample-post
original_post_id: 1
category: 관점 브리핑
---

# Sample post

Body **bold** text.
"""


class BlogBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self.tmp.name, "a.md"), "w", encoding="utf-8") as handle:
            handle.write(SAMPLE)
        with open(os.path.join(self.tmp.name, "bad.md"), "w", encoding="utf-8") as handle:
            handle.write("no frontmatter here\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_blog_posts_parses_frontmatter_and_skips_invalid(self):
        posts = page_build.read_blog_posts(self.tmp.name)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["date"], "2026-10-07")
        self.assertEqual(posts[0]["original_slug"], "sample-post")

    def test_read_blog_posts_missing_dir_is_empty(self):
        self.assertEqual(page_build.read_blog_posts(os.path.join(self.tmp.name, "nope")), [])

    def test_blog_list_links_to_post_pages(self):
        posts = page_build.read_blog_posts(self.tmp.name)
        html = landing.render_blog_list(posts)
        self.assertIn('/blog/sample-post/', html)
        self.assertIn('datetime="2026-10-07"', html)

    def test_blog_post_keeps_body_numbers_verbatim(self):
        posts = page_build.read_blog_posts(self.tmp.name)
        html = landing.render_blog_post(
            posts[0], landing.blog_markdown_to_html(posts[0]["body"]))
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn('href="/blog/"', html)

    def test_markdown_escapes_raw_html(self):
        html = landing.blog_markdown_to_html('<script>alert(1)</script>')
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
