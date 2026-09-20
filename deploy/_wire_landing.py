"""Wire the new front page in, and turn the published copy into a pointer at the live site."""
import ast
import io
import re

P = "C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py"
text = io.open(P, encoding="utf-8").read()

# 1. the front page moved to its own module
if "import landing" not in text:
    text = text.replace("import ui_text\n", "import landing\nimport ui_text\n", 1)

# 2. drop the old inline landing template and its builder
start = text.index('LANDING = """<!doctype html>')
end = text.index("def build_server(")
print("removing %d chars of the old landing" % (end - start))
text = text[:start] + text[end:]

# 3. build_server uses the module
text = text.replace('sizes["index.html"] = write(ROOT / "index.html", render_landing())',
                    'sizes["index.html"] = write(ROOT / "index.html", landing.render_landing())', 1)

# 4. the published pages become redirects
new_public = '''# Where each published address should send its reader. The domain was split into sections
# (/news, /thai) and the collector runs on its own host, so these addresses are old links.
MOVED = {
    "docs/index.html": "https://teemobkk.io/",
    "docs/ko/index.html": "https://teemobkk.io/news/ko/",
    "docs/thai/index.html": "https://teemobkk.io/thai/",
    "docs/ko/thai/index.html": "https://teemobkk.io/thai/ko/",
}

REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK</title>
<link rel="canonical" href="__TO__">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url=__TO__">
<style>
html{background:#05070d;color:#8b9bbd;font:14px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;text-align:center}
b{display:block;color:#eef3ff;font-size:17px;letter-spacing:-.02em;margin-bottom:10px}
a{color:#64d7ff;word-break:break-all}
</style>
</head>
<body>
<main>
<b>TeemoBKK has moved.</b>
<a href="__TO__">__TO__</a>
</main>
<script>location.replace("__TO__");</script>
</body>
</html>
"""


def redirect_page(to: str) -> str:
    """A pointer, not a second copy.

    These addresses were published before the domain was split into sections, so links to them
    exist and must keep working. A copy of the dashboard here would be stale the moment the
    collector moved on, and a reader landing on it would have no way to know. So: a meta refresh
    for the browser, a real link for a reader whose refresh is blocked, and noindex so the old
    address is not what a search result offers.
    """
    return REDIRECT.replace("__TO__", to)


def build_public() -> dict[str, int]:
    """Write the published pages as redirects to the live site.

    Only docs/ is touched. An earlier version also rewrote the local page at the repository
    root, which left an unstaged modification in the CI working tree on every run, so
    `git pull --rebase` refused to start ("cannot pull with rebase: You have unstaged changes")
    and the published site silently stopped updating while the workflow still reported a run
    every five minutes.

    The redirects are rewritten every cycle on purpose: whatever the publish step does, the old
    address must not come back as a copy of the dashboard.
    """
    sizes = {}
    for name, to in MOVED.items():
        sizes[name] = write(ROOT / name, redirect_page(to))
    return sizes
'''

start = text.index("def build_public() -> dict[str, int]:")
end = text.index("def build_server(")
text = text[:start] + new_public + "\n\n" + text[end:]

io.open(P, "w", encoding="utf-8", newline="").write(text)
ast.parse(io.open(P, encoding="utf-8").read())
print("page_build rewritten; ast OK")

check = io.open(P, encoding="utf-8").read()
print("  old LANDING gone:", "LANDING = \"\"\"" not in check)
print("  render_landing calls: %d" % check.count("render_landing()"))
print("  build_public redirects: %d" % len(re.findall(r'"docs/[^"]+": "https', check)))
print("  broken jamo:", len([c for c in check if 0x1100 <= ord(c) <= 0x11FF]))
