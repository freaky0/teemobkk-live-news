"""Put the pointer-only hover rule back, and take out the standalone one.

The first pass edited the stylesheet in the wrong order: it inserted the media-wrapped hover rule
and then deleted the first bare match, which was the one just inserted, leaving the original rule
in place and no media query at all.
"""
import ast
import io

P = "C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py"
text = io.open(P, encoding="utf-8").read()

BARE = ".trend .tbtn:hover{border-color:var(--accent);color:var(--accent)}"
WRAPPED = "@media (hover:hover){" + BARE + "}"
ANCHOR = ".trend .tbtn.clear{border-style:dashed;border-color:var(--warn);color:var(--warn);font-weight:600}"

n = text.count(BARE)
print("  bare hover rule x%d" % n)
text = text.replace(BARE, "", n)
if WRAPPED in text:
    text = text.replace(WRAPPED, "", 1)
assert ANCHOR in text
text = text.replace(ANCHOR, ANCHOR + "\n" + WRAPPED, 1)

io.open(P, "w", encoding="utf-8", newline="").write(text)
src = io.open(P, encoding="utf-8").read()
ast.parse(src)
print("  ast OK · bare %d · wrapped %d" % (src.count(BARE), src.count(WRAPPED)))
