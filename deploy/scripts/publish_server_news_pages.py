#!/usr/bin/env python3
"""Build live news dashboards in staging and atomically publish their seed pages."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


PUBLISHED_PAGES = (
    "news/index.html",
    "news/ko/index.html",
    "news/assets/dashboard.css",
    "thai/news/index.html",
    "thai/news/ko/index.html",
)


def publish(code_root: Path, db_path: Path, static_root: Path,
            staging_root: Path) -> list[tuple[str, int]]:
    if not code_root.is_dir():
        raise RuntimeError(f"code root does not exist: {code_root}")
    if not db_path.is_file():
        raise RuntimeError(f"news database does not exist: {db_path}")
    if not static_root.is_dir() or not staging_root.is_dir():
        raise RuntimeError("static root and staging root must already exist")

    sys.path.insert(0, str(code_root))
    from pages.build import page_build

    original_root, original_docs = page_build.ROOT, page_build.DOCS
    published: list[tuple[str, int]] = []
    try:
        with tempfile.TemporaryDirectory(prefix=".news-pages-build-", dir=staging_root) as tmp:
            build_root = Path(tmp)
            page_build.ROOT = build_root
            page_build.DOCS = build_root / "docs"
            outputs = page_build.build_server(db_path=str(db_path))

            missing = [name for name in PUBLISHED_PAGES
                       if name not in outputs or not (build_root / name).is_file()]
            if missing:
                raise RuntimeError("builder did not produce: " + ", ".join(missing))

            for name in PUBLISHED_PAGES:
                source = build_root / name
                target = static_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                temp_name = None
                try:
                    with tempfile.NamedTemporaryFile(
                            prefix=f".{target.name}.", suffix=".tmp",
                            dir=target.parent, delete=False) as temp_file:
                        temp_name = Path(temp_file.name)
                    shutil.copyfile(source, temp_name)
                    os.chmod(temp_name, 0o644)
                    os.replace(temp_name, target)
                    published.append((name, source.stat().st_size))
                finally:
                    if temp_name is not None and temp_name.exists():
                        temp_name.unlink()
    finally:
        page_build.ROOT, page_build.DOCS = original_root, original_docs

    return published


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-root", required=True, type=Path)
    parser.add_argument("--db-path", required=True, type=Path)
    parser.add_argument("--static-root", required=True, type=Path)
    parser.add_argument("--staging-root", required=True, type=Path)
    args = parser.parse_args()

    try:
        published = publish(
            args.code_root.resolve(), args.db_path.resolve(),
            args.static_root.resolve(), args.staging_root.resolve())
    except Exception as exc:
        print(f"news page publish failed: {exc}", file=sys.stderr)
        return 1

    for name, size in published:
        print(f"published {name} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
