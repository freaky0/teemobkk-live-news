#!/usr/bin/env python3
"""Report Korean text a reader would see on an English page.

The Korean page is the source: the English documents are the same document with a phrase table
applied, and the table is built from the interface string tables. Anything the table does not know
survives into the English page, and a reader there sees Korean in a control label - which is how
"+ 조건 추가" and "최근 7일" shipped on the English dashboard.

Data is not a gap: category values, region names, the trend stop-word lists and the regex character
ranges are Korean on purpose and are skipped. What is left is interface text a reader sees, either
as element text or as a quoted literal (the script builds most of its strings that way).

    python tools/probe_english_text.py            # the three public documents
    python tools/probe_english_text.py --thai
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import page_build  # noqa: E402
import ui_text  # noqa: E402

HANGUL = re.compile(r"[\uac00-\ud7a3]+")
# Element text, and quoted literals up to a line: the script writes its strings in quotes.
ELEMENT_TEXT = re.compile(r">([^<>{}]+)<")
QUOTED = re.compile(r"'([^'\n\\]{2,90})'")
CONFIG_LINE = re.compile(r"const CFG=\{[^\n]*\};")


def has_hangul(text: str) -> bool:
    return bool(HANGUL.search(text))


def skip_words() -> set[str]:
    """Korean that belongs in an English document: data, not interface."""
    words = set()
    for lang in ("ko", "en"):
        for region in ("global", "thai"):
            for pair in ui_text.cats(lang)[region]:
                words.add(pair[0].strip())
                words.add(pair[1].strip())
    # Region values the API takes, the language switcher's own label, and the names the calendar's
    # speaker roster is built from: all of it is data the page carries on purpose.
    words.update({"글로벌", "태국", "한국어"})
    words.update({"파월", "워시", "베센트", "라가르드", "머스크", "푸틴", "시진핑", "네타냐후", "우에다"})
    # The trend lists skip these on purpose, and the character ranges name the scripts themselves.
    words.update({"가", "힣", "건", "일", "시간", "개"})
    # The two trend skip lists are data the script carries verbatim.
    words.update({"bitcoin", "btc", "crypto", "cryptocurrency", "비트코인", "암호화폐", "코인",
                  "thai", "thailand", "bangkok", "태국인", "교민", "방콕"})
    return words


def fragments(page: str, allowed: set[str]) -> dict[str, int]:
    body = CONFIG_LINE.sub("", page)
    found: dict[str, int] = {}
    for text in ELEMENT_TEXT.findall(body) + QUOTED.findall(body):
        if not has_hangul(text):
            continue
        stripped = text.strip()
        # A fragment that is only a known value (a category, a region) is data.
        residue = HANGUL.sub(lambda m: "" if m.group(0) in allowed else m.group(0), stripped)
        if not has_hangul(residue):
            continue
        found[stripped[:60]] = found.get(stripped[:60], 0) + 1
    return found


def document(name: str, **kwargs) -> str:
    return page_build.render(public=False, datadir="", icon_prefix="/", admin=False, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thai", action="store_true", help="the Thailand dashboard instead")
    args = parser.parse_args()

    allowed = skip_words()
    pages = {
        "news/index.html": document("en page", want_thai=args.thai, lang="en",
                                    alt="ko/index.html", seed_html=""),
        "news/ko/index.html": document("ko page", want_thai=args.thai, lang="ko",
                                       alt="../index.html", seed_html=""),
    }
    total = 0
    for name, page in pages.items():
        if name.endswith("ko/index.html"):
            print("%s: the source language, nothing to check" % name)
            continue
        found = fragments(page, allowed)
        total += len(found)
        print("%s: %d fragment(s) a reader would see in Korean" % (name, len(found)))
        for text, count in sorted(found.items(), key=lambda kv: (-kv[1], kv[0])):
            print("   %2dx  %s" % (count, text))
    if total:
        print("\nAdd these to ui_text.UI_KO/UI_EN so the phrase table covers them.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
