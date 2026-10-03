import io
import json
import tempfile
import unittest
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import landing
import landing_thai
import page_build
import theme


class SharedThemeContract(unittest.TestCase):
    def test_shared_module_exports_tokens_renderers_and_date_formatter(self):
        self.assertIn(":root{", theme.CSS_CUSTOM_PROPERTIES)
        self.assertIn(".button{", theme.BUTTON_CSS)
        self.assertIn("data-theme=dark", theme.DARK_THEME_CSS)
        self.assertIn(".urow", theme.USAGE_BAR_CSS)
        self.assertIn("<nav", theme.render_header())
        self.assertIn('href="/perspectives/"', theme.render_header())
        self.assertIn('href="/indicators/"', theme.render_header())
        self.assertIn('<footer class="footer">', theme.render_footer())
        self.assertEqual(theme.display_date("2026-10-03"), "2026년 10월 3일")
        self.assertEqual(landing.display_date("2026-10-03"), "2026년 10월 3일")

    def test_landing_renders_shared_components_without_placeholders(self):
        posts = [{
            "title": "검증용 관점",
            "date": "2026-10-03",
            "url": "https://teemobkk.substack.com/p/test",
            "summary": "고정 입력",
        }]
        with patch.object(landing, "editorial_posts", return_value=posts):
            html = landing.render_landing()
        for text in ("data-theme=dark", ".urow", 'localStorage.getItem("tbn-theme")',
                     "teemo@bkk", "사이트 정보", "2026년 10월 3일"):
            self.assertIn(text, html)
        self.assertNotIn("__THEME_HEAD__", html)
        self.assertNotIn("__SHARED_THEME_CSS__", html)
        self.assertNotIn("__HEADER__", html)
        self.assertNotIn("__FOOTER__", html)
        self.assertNotIn("__INDICATOR_CSS__", html)
        self.assertNotIn("__INDICATORS__", html)

    def test_standalone_pages_share_the_theme_and_render_their_full_catalogues(self):
        posts = [{
            "title": "관점 글 {}".format(index),
            "date": "2026-10-{:02d}".format(index),
            "url": "https://teemobkk.substack.com/p/post-{}".format(index),
            "summary": "요약 {}".format(index),
        } for index in range(1, 13)]
        with patch.object(landing, "editorial_posts", return_value=posts[:3]):
            home = landing.render_landing()
        perspectives = landing.render_perspectives_page(posts)
        indicators = landing.render_indicators_page()

        self.assertEqual(home.count('class="post"'), 3)
        self.assertIn('href="/perspectives/">$ open /perspectives/ →', home)
        self.assertIn('href="/indicators/">$ open /indicators/ →', home)
        self.assertEqual(perspectives.count('class="page-post"'), 10)
        self.assertIn("관점 글 10", perspectives)
        self.assertNotIn("관점 글 11", perspectives)
        self.assertIn('href="/perspectives/"', perspectives)
        self.assertEqual(indicators.count('class="indicator"'), len(landing.INDICATORS))
        self.assertEqual(home.count('class="indicator"'), len(landing.INDICATORS))
        self.assertIn(".page-main", perspectives)
        self.assertIn(".indicator{", indicators)

    def test_substack_refresh_returns_the_ten_latest_matching_posts(self):
        payload = [{
            "title": "관점 글 {}".format(index),
            "post_date": "2026-10-{:02d}T00:00:00Z".format(index),
            "canonical_url": "https://teemobkk.substack.com/p/post-{}".format(index),
            "subtitle": "요약 {}".format(index),
            "postTags": [],
        } for index in range(1, 16)]
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        with patch.object(landing, "_fresh_cache", return_value=None), \
                patch.object(landing, "urlopen", return_value=response) as fetch, \
                patch.object(landing, "_write_cache"):
            posts = landing.editorial_posts(limit=10)
        self.assertEqual(len(posts), 10)
        self.assertEqual(posts[0]["date"], "2026-10-15")
        self.assertEqual(posts[-1]["date"], "2026-10-06")
        self.assertIn("limit=50", fetch.call_args.args[0].full_url)

    def test_server_build_writes_both_standalone_documents(self):
        posts = [{
            "title": "관점 빌드 {}".format(index),
            "date": "2026-10-{:02d}".format(index),
            "url": "https://teemobkk.substack.com/p/build-{}".format(index),
            "summary": "빌드 요약",
        } for index in range(12, 0, -1)]

        def selected_posts(limit=3):
            return posts[:limit]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(page_build, "ROOT", root), \
                    patch.object(page_build, "seed_from_db", return_value=""), \
                    patch.object(page_build, "seed_briefing_from_db", return_value=("", "")), \
                    patch.object(page_build, "_prune_sections", return_value=[]), \
                    patch.object(landing, "editorial_posts", side_effect=selected_posts):
                sizes = page_build.build_server(db_path="not-used.db")

            perspectives = (root / "perspectives" / "index.html").read_text(encoding="utf-8")
            indicators = (root / "indicators" / "index.html").read_text(encoding="utf-8")
            self.assertIn("perspectives/index.html", sizes)
            self.assertIn("indicators/index.html", sizes)
            self.assertEqual(perspectives.count('class="page-post"'), 10)
            self.assertIn("관점 빌드 12", perspectives)
            self.assertNotIn("관점 빌드 2</a>", perspectives)
            self.assertEqual(indicators.count('class="indicator"'), len(landing.INDICATORS))

    def test_thai_landing_and_dashboards_use_shared_theme(self):
        thai = landing_thai.render_thai_landing()
        news = page_build.render(
            public=True, datadir="", want_thai=True, icon_prefix="/",
            admin=False, lang="ko", alt="", seed_html="",
            briefing_html="", briefing_source="")
        self.assertEqual(page_build.CSS, theme.DASHBOARD_CSS + "\n" + theme.USAGE_BAR_CSS)
        self.assertEqual(page_build.THEME_SCRIPT, theme.NEWS_THEME_SCRIPT)
        self.assertIn("localStorage.getItem(\"tbn-theme\")", thai)
        for page in (thai, news):
            self.assertIn(".urow{", page)
            self.assertIn(".ubar{", page)
        self.assertIn(landing_thai.HERO_IMG, thai)

    def test_dashboard_summary_uses_full_available_width(self):
        page = page_build.render(
            public=True, datadir="", want_thai=False, icon_prefix="/",
            admin=False, lang="ko", alt="", seed_html="",
            briefing_html="", briefing_source="")
        self.assertIn(".summary{", page)
        summary_rule = page.split(".summary{", 1)[1].split("}", 1)[0]
        self.assertNotIn("max-width", summary_rule)
        self.assertIn(".title{", page)

    def test_dark_active_pills_use_light_theme_text(self):
        dark = theme.DASHBOARD_CSS
        self.assertIn(
            "body.public .pill.active,body.public .pill.on,body.public .pill.pick.active,\n"
            "  body.public .trend .tbtn.on,body.public .pill.th.active,body.public .pill.src.th.active{color:var(--text)}",
            dark,
        )
        self.assertIn(
            'html[data-theme="dark"] body.local .pill.active,html[data-theme="dark"] body.local .pill.on,\n'
            'html[data-theme="dark"] body.local .pill.pick.active,html[data-theme="dark"] body.local .trend .tbtn.on,\n'
            'html[data-theme="dark"] body.local .pill.th.active,html[data-theme="dark"] body.local .pill.src.th.active{color:var(--text)}',
            dark,
        )
        self.assertIn('html[data-theme="light"] body.public,html[data-theme="light"] body.local{', dark)

    def test_mobile_primary_touch_targets_have_44px_minimum(self):
        dashboard = theme.DASHBOARD_CSS
        for selector in ("body.public .tab", "body.public .pill", "body.public .trend .tbtn",
                         "body.public .expand", "body.public #more", "body.public #cal-retry"):
            self.assertIn(selector, dashboard)
        mobile_rules = dashboard.rsplit("@media(max-width:767px){", 1)[1]
        self.assertIn("min-height:44px", mobile_rules)

        thai = theme.THAI_CSS
        for selector in (".nav nav a", ".filters .chip", ".retry"):
            self.assertIn(selector, thai)
        self.assertIn("min-height:44px", thai)

        homepage = landing.render_landing()
        self.assertIn(".retry{min-height:44px", homepage)

    def test_public_mobile_header_is_single_row_and_filter_hint_fades(self):
        mobile_rules = theme.DASHBOARD_CSS.rsplit("@media(max-width:767px){", 1)[1]
        self.assertIn("body.public .bar-in{flex-wrap:nowrap", mobile_rules)
        self.assertIn("body.public .bar-in>div:first-child{display:flex", mobile_rules)
        self.assertIn("body.public .pills{-webkit-mask-image:linear-gradient", mobile_rules)
        self.assertIn("mask-image:linear-gradient", mobile_rules)


if __name__ == "__main__":
    unittest.main()
