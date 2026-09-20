"""Move the category tables out of the collector core and switch it to multi-label matching.

Multi-line edits in a Python file have produced IndentationError before (the replacement's
indentation lands wrong and the module dies at import), so this slices the file by marker and
rebuilds it, then parses the result before writing anything to disk.

    python tools/split_taxonomy_out.py --dry     # show what would move
    python tools/split_taxonomy_out.py --apply
"""
import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "live_news_dashboard.py")
TABLE = os.path.join(ROOT, "category_rules.py")

BOUNDARY_MARK = "# Terms that must match a whole word, chosen from measurement rather than taste."
BOUNDARY_END = "def canonical_link("
DICT_START = "CATEGORY_RULES = {"
DICT_END = "def fetch_bytes("
CALL_START = "rules = THAI_CATEGORY_RULES if region =="
CALL_END = "break"
NEW_CALL = [
    "    categories = taxonomy.match_all(text, taxonomy.rules_for(region, THAI_REGION)) or [GENERIC_CATEGORY]\n",
    "    category = categories[0]\n",
]
RETURN_ANCHOR = '        "category": category,\n'
RETURN_ADD = '        "categories": categories,\n'


def cut(text, start_mark, end_mark):
    start = text.index(start_mark)
    end = text.index(end_mark, start)
    return text[:start] + text[end:], text[start:end]


def main():
    apply = "--apply" in sys.argv
    text = io.open(CORE, encoding="utf-8").read()
    original = text

    # 1. the boundary-term block (comments with the measurements + the set + the matcher)
    text, moved_boundary = cut(text, BOUNDARY_MARK, BOUNDARY_END)

    # 2. the two category tables
    text, moved_tables = cut(text, DICT_START, DICT_END)

    # 3. the import
    anchor = "import bluesky_source\n"
    if "import category_rules" not in text:
        text = text.replace(anchor, "import category_rules as taxonomy\n" + anchor, 1)

    # 4. the classification loop, replaced by the multi-label call
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.strip().startswith(CALL_START))
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == CALL_END)
    lines[start:end + 1] = NEW_CALL
    text = "".join(lines)

    # 5. carry the whole list into the stored row
    if RETURN_ADD not in text:
        text = text.replace(RETURN_ANCHOR, RETURN_ANCHOR + RETURN_ADD, 1)

    ast.parse(text)  # raises before anything is written

    print("moved out of the core:")
    print("  boundary terms + matcher: %d lines" % moved_boundary.count("\n"))
    print("  category tables         : %d lines" % moved_tables.count("\n"))
    print("core shrinks by %d lines, grows by 8 (import, call, return field)" % (
        (moved_boundary.count("\n") + moved_tables.count("\n"))))
    print("syntax: OK (ast.parse on the rebuilt module)")

    if not apply:
        print("\ndry run: nothing written. Re-run with --apply.")
        return 0

    # The measured comments that justified BOUNDARY_TERMS are appended to category_rules.py by
    # hand (they are ASCII, so they carry no write-corruption risk) rather than string-pasted
    # back here, which produced tangled placeholder replacements.
    io.open(CORE, "w", encoding="utf-8", newline="\n").write(text)
    print("\nwrote %s" % os.path.basename(CORE))
    print("core changed by %d characters" % (len(text) - len(original)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
