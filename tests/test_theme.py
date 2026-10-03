import unittest
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
