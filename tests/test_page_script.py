"""The page builder's script, checked by a JavaScript parser instead of by reading it.

`page_build.py` keeps its CSS and its script inside Python string literals, and the script is the
part that keeps breaking: two defects in one session - a lost `=>` that made a click handler run
while the page was rendering, and a surrogate pair that could not be encoded into the file at all -
were both found by hand, by running `node --check` after the fact. A syntax error in that string
does not fail the build. It produces a page that ships, loads, and then does nothing, which looks
like a network problem to a reader.

So every document the builder can produce is rendered here and every script it carries is handed to
`node --check`. `node` is already a test dependency: the page tests run against jsdom, and a missing
`node` fails this check rather than skipping it, because a skipped check here reads as a pass.

    python tests/test_page_script.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import admin_page  # noqa: E402
import page_build  # noqa: E402

SEED = ('<article class="card seed"><h2 class="t"><a href="https://example.com/x">Example story</a>'
        '</h2><p class="s">A seeded story.</p></article>')

SCRIPTS = re.compile(r"<script>(.*?)</script>", re.S)


def documents() -> dict[str, str]:
    """Every document the builder writes or serves, under its own name.

    The interface languages are the two the deployment actually builds a copy for: /news and /news/ko,
    /thai/news and /thai/news/ko. Thai is a *section* whose pages are English or Korean, not a third
    interface language: `ui_text.UI` has no "th" table, so `render(lang="th")` raises KeyError. Nothing
    calls it that way, so this test does not either - it covers what ships.
    """
    built = {}
    for lang, alt in (("ko", "en/index.html"), ("en", "ko/index.html")):
        for want_thai, tag in ((False, "global"), (True, "thai")):
            built["public %s %s" % (tag, lang)] = page_build.render(
                public=False, datadir="", want_thai=want_thai, icon_prefix="/",
                admin=False, lang=lang, alt=alt, seed_html=SEED)
    built["operator"] = page_build.render(
        public=False, datadir="", want_thai=False, icon_prefix="/",
        admin=True, lang="ko", alt="en/index.html", seed_html=SEED)
    built["login"] = admin_page.login_page()
    return built


def check(script: str, name: str):
    """Hand one script body to node. Returns None when it parses, or node's own complaint."""
    handle, path = tempfile.mkstemp(suffix=".js", prefix="page-script-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(script)
        done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if done.returncode == 0:
        return None
    return "%s\n%s" % (done.stdout.strip(), done.stderr.strip())


class PageScript(unittest.TestCase):
    def test_node_is_available(self):
        self.assertTrue(shutil.which("node"),
                        "the page tests already need node; a missing node must fail, not skip")

    def test_every_document_carries_a_script_that_parses(self):
        for name, page in documents().items():
            found = SCRIPTS.findall(page)
            self.assertTrue(found, "%s carries no script at all" % name)
            for index, script in enumerate(found):
                complaint = check(script, name)
                self.assertIsNone(complaint, "%s script %d does not parse:\n%s"
                                  % (name, index, complaint))

    def test_the_script_is_not_truncated_by_its_own_string(self):
        """The script closing tag must not appear inside the Python string it lives in.

        `page_build.SCRIPT` is written into the document between <script> and </script>. A stray
        closing tag inside it would end the document's script early and turn everything after it
        into page text - visible on the page, and invisible to a parse check that reads the
        builder's own string.
        """
        self.assertNotIn("</script", page_build.SCRIPT,
                         "the builder's script must not contain a closing script tag")


if __name__ == "__main__":
    unittest.main(verbosity=2)
