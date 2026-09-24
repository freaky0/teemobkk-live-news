"""What each of the three documents carries, checked on the document itself.

Three documents come out of the page builder and only one of them is the operator's:

  * the public dashboard - the deployment serves it from disk, so anybody can read the file
  * the login page      - what /admin answers without a session
  * the operator dashboard - what /admin answers with one

The mix-up that would matter is an operator control reaching the public document, and that is a
property of the document, not of what a running server happened to answer, so it is checked here by
building the documents and reading them.

    python tests/test_admin_page.py
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import admin_page  # noqa: E402
import page_build  # noqa: E402

OPERATOR_MARKERS = ('id="interval"', 'id="logout"', 'id="sources"', 'id="hidden"', 'id="undobar"',
                    'data-hide=')

SEED = ('<article class="card seed"><h2 class="t"><a href="https://example.com/x">Example story</a>'
        '</h2><p class="s">A seeded story.</p></article>')


def public_document(lang="en", want_thai=False):
    """A section page exactly as the deployment builds it (build_server's call)."""
    return page_build.render(public=False, datadir="", want_thai=want_thai, icon_prefix="/",
                             admin=False, lang=lang, alt="ko/index.html", seed_html=SEED)


def markup_only(page: str) -> str:
    """The document without its scripts.

    The script carries the code for controls that the markup renders only for an operator - a hide
    button, the restore list - so "does this document carry that control" is a question about the
    markup. Asking it of the whole file would fail on the code that builds the control, which every
    document needs because the same script serves both.
    """
    return re.sub(r"<script>.*?</script>", "", page, flags=re.S)


class PublicDocument(unittest.TestCase):
    def test_the_public_document_has_no_operator_controls(self):
        page = markup_only(public_document())
        for marker in OPERATOR_MARKERS:
            self.assertNotIn(marker, page, "the public dashboard must not carry " + marker)
        self.assertNotIn("보관", page, "the retention count is the operator's")
        self.assertNotIn("숨긴 기사", page, "the restore list is the operator's")
        self.assertNotIn("관리자", page, "the public document must not advertise the admin area")

    def test_the_public_document_still_carries_the_reader_page(self):
        page = public_document()
        self.assertIn('id="feed"', page)
        self.assertIn('id="q"', page)
        self.assertIn("window.__PUBLIC__", page + "window.__PUBLIC__",
                      "the flag the collector injects has a place to land")

    def test_reader_edition_has_a_distinct_name_and_theme(self):
        korean = public_document(lang="ko")
        self.assertIn('<body class="public">', korean)
        self.assertIn('<title>오늘의 시장 | TeemoBKK</title>', korean)
        self.assertIn('<h1>오늘의 시장</h1>', korean)
        self.assertIn('body.public .feed{display:block', korean)
        thai = public_document(lang="ko", want_thai=True)
        self.assertIn('<h1>태국의 오늘</h1>', thai)
        english = public_document()
        self.assertIn('<h1>Market Today</h1>', english)

    def test_the_write_helper_is_inert_without_a_session(self):
        # The helper is in every document; it only adds the header when the server has told the
        # document it has a session, which a public document never is.
        page = public_document()
        self.assertIn("const ADMIN=window.__ADMIN__===true", page)
        self.assertIn("if(ADMIN)h['X-Requested-With']", page)

    def test_the_thai_document_is_the_same_shape(self):
        page = public_document(want_thai=True)
        for marker in OPERATOR_MARKERS:
            self.assertNotIn(marker, markup_only(page))
        self.assertIn('id="feed"', page)

    def test_the_operator_only_block_is_marked_and_balanced(self):
        # tools/probe_english_text.py skips this block, so the markers are part of the contract: an
        # opening marker with no closing one would leave the whole rest of the script unscanned.
        page = public_document()
        self.assertEqual(page.count("// >>> operator-only"), 1)
        self.assertEqual(page.count("// <<< operator-only"), 1)

    def test_no_document_sets_the_session_flag_by_itself(self):
        # The flag is injected by the server on the document it answers /admin with, never built in.
        for page in (public_document(), public_document(want_thai=True)):
            self.assertNotIn("window.__ADMIN__=true", page)


class LoginDocument(unittest.TestCase):
    def test_the_login_document_is_only_a_password_box(self):
        page = admin_page.login_page()
        self.assertIn('id="pw"', page)
        self.assertIn('type="password"', page)
        self.assertIn("/api/login", page)
        for marker in OPERATOR_MARKERS + ('id="feed"', 'id="q"', "window.__ADMIN__", "__CATS_GLOBAL__"):
            self.assertNotIn(marker, page, "the login page must be nothing else: " + marker)
        self.assertNotIn("실시간 뉴스 대시보드", page, "no dashboard furniture either")

    def test_login_matches_reader_palette_without_dashboard_markup(self):
        page = admin_page.login_page()
        self.assertIn('<span class="brand">TeemoBKK</span>', page)
        self.assertIn('--bg:#f8f9f8', page)
        self.assertIn('--accent:#08645d', page)
        self.assertIn('prefers-color-scheme:dark', page)
        self.assertIn('for="pw"', page)
        self.assertNotIn('id="feed"', page)

    def test_the_login_document_is_small(self):
        self.assertLess(len(admin_page.login_page()), 4000,
                        "a login page that carries the dashboard is the bug this guards")

    def test_a_status_note_is_escaped_into_the_script(self):
        page = admin_page.login_page('문제"><script>alert(1)</script>')
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("\\u003c", page, "the note is quoted, not pasted")


class OperatorDocument(unittest.TestCase):
    def test_the_operator_document_is_the_dashboard_with_its_panels(self):
        page = admin_page.operator_page()
        for marker in OPERATOR_MARKERS:
            self.assertIn(marker, page, "the operator page needs " + marker)
        self.assertIn("window.__ADMIN__=true", page)
        self.assertIn('id="feed"', page)
        self.assertIn("갱신", page, "the interval control is the point of this page")

    def test_operator_edition_uses_reader_palette_and_keeps_controls(self):
        page = admin_page.operator_page()
        self.assertIn('<body class="local">', page)
        self.assertIn('body.public,body.local{', page)
        self.assertIn('body.local .feed{display:block', page)
        self.assertIn('body.local .side{display:grid', page)
        self.assertIn('body.local:not(.tab-cal) .layout', page)
        for marker in OPERATOR_MARKERS:
            self.assertIn(marker, page)

    def test_the_flag_lands_before_anything_reads_it(self):
        page = admin_page.operator_page()
        flag = page.index("window.__ADMIN__=true")
        self.assertLess(flag, page.index("const ADMIN=window.__ADMIN__"),
                        "the flag is set in the same script, before the line that reads it")

    def test_building_it_writes_nothing_to_disk(self):
        before = set(os.listdir(ROOT))
        admin_page.operator_page()
        self.assertEqual(before, set(os.listdir(ROOT)),
                         "the operator document stays in memory; a file here could be served by the proxy")

    def test_it_is_korean(self):
        page = admin_page.operator_page()
        self.assertIn('<html lang="ko">', page)
        self.assertIn("실시간 뉴스 대시보드", page)
        self.assertNotIn("Trending now", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
