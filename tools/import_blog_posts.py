"""Import converted Substack POV-briefing markdown into the articles table (TEE-82).

Each converted-*.md carries frontmatter::

    title, date (original publish date YYYY-MM-DD), original_slug,
    original_post_id, category (관점 브리핑)

Rules (per spec):
- ``published_at`` is the frontmatter ``date`` (the Substack original date),
  never the import work date.
- Body numbers stay exactly as written; only an excerpt goes to ``summary``.
- Import is idempotent: rows key on ``link`` (``/blog/<slug>/``), so a
  re-import updates instead of duplicating.

Usage:
    python tools/import_blog_posts.py --src <dir> --db <news.db> [--dry-run]
"""

import argparse
import datetime
import os
import re
import sqlite3
import sys

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
REQUIRED = ("title", "date", "original_slug", "original_post_id", "category")
DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


def parse_frontmatter(text: str, path: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("frontmatter block missing")
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    missing = [key for key in REQUIRED if not meta.get(key)]
    if missing:
        raise ValueError("frontmatter missing: %s" % ",".join(missing))
    if not DATE_RE.match(meta["date"]):
        raise ValueError("date must be YYYY-MM-DD, got %r" % meta["date"])
    datetime.date.fromisoformat(meta["date"])  # validates real calendar date
    return meta, text[match.end():]


def excerpt(body: str, limit: int = 300) -> str:
    text = re.sub(r"[#>*-`]", "", body).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def import_dir(src: str, db_path: str, dry_run: bool = False) -> dict:
    files = sorted(
        name for name in os.listdir(src)
        if name.endswith(".md") and os.path.isfile(os.path.join(src, name))
    )
    if not files:
        raise SystemExit("no .md files in %s" % src)
    collected_at = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=7))).isoformat(timespec="seconds")
    rows = []
    errors = []
    for name in files:
        path = os.path.join(src, name)
        try:
            with open(path, encoding="utf-8") as handle:
                meta, body = parse_frontmatter(handle.read(), path)
            slug = meta["original_slug"]
            rows.append((
                "/blog/%s/" % slug, meta["title"], excerpt(body),
                "substack", "briefing", "글로벌", meta["category"], meta["category"],
                "", 0, meta["date"], collected_at,
            ))
        except (OSError, ValueError) as exc:
            errors.append("%s: %s" % (name, exc))
    result = {"files": len(files), "imported": 0, "updated": 0, "errors": errors}
    if dry_run:
        result["imported"] = len(rows)
        return result
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
        if not columns:
            connection.execute(
                "CREATE TABLE articles ("
                "link TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, source TEXT, "
                "source_type TEXT, region TEXT, category TEXT, categories TEXT, asset TEXT, "
                "priority INTEGER, published_at TEXT NOT NULL, collected_at TEXT)"
            )
            columns = {"link", "title", "summary", "source", "source_type", "region",
                       "category", "categories", "asset", "priority",
                       "published_at", "collected_at"}
        full = ["link", "title", "summary", "source", "source_type", "region",
                "category", "categories", "asset", "priority",
                "published_at", "collected_at"]
        use = [col for col in full if col in columns]
        placeholders = ",".join("?" for _ in use)
        updates = ",".join(
            "%s=excluded.%s" % (col, col) for col in use if col != "link")
        existing = {row[0] for row in connection.execute("SELECT link FROM articles")}
        for row in rows:
            values = dict(zip(full, row))
            connection.execute(
                "INSERT INTO articles (%s) VALUES (%s) "
                "ON CONFLICT(link) DO UPDATE SET %s" % (
                    ",".join(use), placeholders, updates),
                [values[col] for col in use],
            )
            if values["link"] in existing:
                result["updated"] += 1
            else:
                result["imported"] += 1
                existing.add(values["link"])
        connection.commit()
    finally:
        connection.close()
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import TEE-82 blog markdown (frontmatter date = published_at).")
    parser.add_argument("--src", required=True, help="directory with converted-*.md")
    parser.add_argument("--db", required=True, help="target sqlite db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = import_dir(args.src, args.db, args.dry_run)
    print("files=%d imported=%d updated=%d errors=%d" % (
        result["files"], result["imported"], result["updated"], len(result["errors"])))
    for err in result["errors"]:
        print("ERROR " + err)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
