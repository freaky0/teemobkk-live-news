from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pages.build import landing  # noqa: E402


class LandingEditorialAssets(unittest.TestCase):
    def test_homepage_renders_all_local_visual_assets_with_alt_text(self):
        html = landing.render_landing()
        expected = {
            "/assets/landing/hero-editorial.webp": "방콕의 저녁, 금융 뉴스와 시장 자료를 살펴보는 책상",
            "/assets/landing/news-editorial.webp": "방콕의 편집 데스크에서 경제 뉴스와 시장 자료를 살펴보는 장면",
            "/assets/landing/btc-analysis.webp": "비트코인 가격 구조를 살펴보는 분석 화면과 노트",
        }
        for src, alt in expected.items():
            with self.subTest(src=src):
                self.assertTrue((ROOT / src.lstrip("/")).is_file())
                self.assertIn(f'src="{src}"', html)
                self.assertIn(f'alt="{alt}"', html)
        self.assertIn('content="https://teemobkk.io/assets/landing/hero-editorial.webp"', html)
        self.assertIn('fetchpriority="high"', html)
        self.assertIn('.hero{grid-template-columns:1fr', html)
        self.assertIn('@media(prefers-reduced-motion:reduce)', html)


if __name__ == "__main__":
    unittest.main()
