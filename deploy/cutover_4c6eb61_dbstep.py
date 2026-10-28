#!/usr/bin/env python3
"""DB step for the 4c6eb61 cutover (option A: migrate the DB first, then activate).

What it does, in order, and nothing else:
  1. reads the release's shipped migration files and the target DB read-only;
     refuses to run unless the DB head is community.0021_commentlike and the
     release ships 0022..0029;
  2. takes a FRESH ONLINE BACKUP of the target DB (sqlite3 backup API) into
     --backup-dir, then verifies the backup (integrity, FK check, per-table row
     counts, exact Post rows byte-for-byte);
  3. re-reads the target and aborts if anything was written between the backup
     and the migrate (that is the only window in which option A can lose data);
  4. runs `manage.py migrate --noinput` against the target DB as the service
     user, so journal files keep the service user's ownership;
  5. verifies: head == 0029, tables 33 -> 39, every pre-existing table's row
     count unchanged, every Post row unchanged, and every board-category Post
     has exactly one board row with identical title/body (and non-board posts
     have none), integrity + FK check clean;
  6. prints PASS, or a single ABORT block with the exact restore commands.

Safety: refuses to act on the live DB path without --confirm-live and while the
service unit is active. With --db pointing anywhere else it runs in rehearsal
mode and never touches the live DB.

Exit codes: 0 pass, 2 precondition/abort, 3 migrate failed, 4 verification failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LIVE_DB = Path("/var/lib/teemobkk-post-preview/community.sqlite3")
DEFAULT_RELEASE = Path("/opt/teemobkk-post-preview/releases/4c6eb610d42e197318751d68c92e643d5064e637")
ENV_FILES = (
    "/etc/teemobkk-post-preview.env",
    "/etc/teemobkk-post-preview-thai.env",
    "/etc/teemobkk-post-preview-policy-c57dd4e.env",
)
SERVICE = "teemobkk-post-preview.service"
SERVICE_USER = "teemo-post-preview"

EXPECTED_HEAD_BEFORE = "community.0021_commentlike"
EXPECTED_HEAD_AFTER = "community.0029_backfill_board_content"
SHIPPED = [
    "0022_post_market_kind_post_market_price_and_more",
    "0023_post_job_compensation_post_job_kind_post_job_region_and_more",
    "0024_alter_post_market_kind_alter_post_market_region_and_more",
    "0025_add_foodtravel_place_details",
    "0026_unify_life_board_categories",
    "0027_boardcategory_post_board_category",
    "0028_freepost_jobspost_livingpost_marketpost_noticepost",
    "0029_backfill_board_content",
]
# canonical board category -> authoritative table (housing/banking are living)
BOARD_TABLE = {
    "notice": "community_noticepost",
    "free": "community_freepost",
    "market": "community_marketpost",
    "jobs": "community_jobspost",
    "living": "community_livingpost",
    "housing": "community_livingpost",
    "banking": "community_livingpost",
}
BOARD_TABLES = (
    "community_noticepost",
    "community_freepost",
    "community_marketpost",
    "community_jobspost",
    "community_livingpost",
    "community_boardcategory",
)
# Tables Django's post_migrate hooks add rows to (new models appear in
# django_content_type and auth_permission).  Growth is expected; loss is not.
METADATA_TABLES = {"django_migrations", "django_content_type", "auth_permission"}

_state: dict = {}


def out(msg: str = "") -> None:
    print(msg, flush=True)


def fail(code: int, stage: str, detail: str) -> "NoReturn":  # type: ignore[valid-type]
    _state["failed"] = True
    _state["stage"] = stage
    _state["detail"] = detail
    print_abort(stage, detail)
    sys.exit(code)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]


def row_counts(conn: sqlite3.Connection) -> dict:
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables(conn)}


def posts(conn: sqlite3.Connection) -> dict:
    return {
        r[0]: {"category": r[1], "title": r[2], "body": r[3]}
        for r in conn.execute("SELECT id, category, title, body FROM community_post ORDER BY id")
    }


def migrations(conn: sqlite3.Connection) -> dict:
    out_: dict = {}
    for app, name in conn.execute("SELECT app, name FROM django_migrations"):
        out_.setdefault(app, []).append(name)
    return out_


def head(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT app || '.' || name FROM django_migrations ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else ""


def snapshot(db: Path) -> dict:
    conn = ro(db)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        return {
            "sha256": sha256(db),
            "size": db.stat().st_size,
            "integrity": integrity,
            "fk_violations": len(fk),
            "tables": tables(conn),
            "counts": row_counts(conn),
            "posts": posts(conn),
            "migrations": migrations(conn),
            "head": head(conn),
        }
    finally:
        conn.close()


def parse_env_files(paths) -> dict:
    env: dict = {}
    for p in paths:
        try:
            fh = open(p)
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.lstrip().startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                env[k.strip()] = v
    return env


def drop_to(user: str):
    pw = pwd.getpwnam(user)

    def _drop():
        os.setgroups([])
        os.setgid(pw.pw_gid)
        os.setuid(pw.pw_uid)

    return _drop


def run_django(release: Path, db: Path, args: list[str], run_as: str) -> subprocess.CompletedProcess:
    env = parse_env_files(ENV_FILES)
    env["POST_DB_PATH"] = str(db)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [str(release / "venv/bin/python"), "manage.py"] + args
    preexec = drop_to(run_as) if os.geteuid() == 0 else None
    return subprocess.run(cmd, cwd=str(release / "thai_platform"), env=env,
                          capture_output=True, text=True, preexec_fn=preexec, timeout=600)


def backup_db(src: Path, dst: Path, run_as: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        os.chmod(dst.parent, 0o700)
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(str(dst))
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
    finally:
        source.close()
    with open(dst, "rb") as fh:
        os.fsync(fh.fileno())
    if os.geteuid() == 0:
        os.chmod(dst, 0o600)
        pw = pwd.getpwnam(run_as)
        os.chown(dst, pw.pw_uid, pw.pw_gid)


def check_board_rows(db: Path, pre_posts: dict) -> list[str]:
    errors = []
    conn = ro(db)
    try:
        existing = set(tables(conn))
        for t in BOARD_TABLES:
            if t not in existing:
                errors.append(f"missing table {t}")
        if errors:
            return errors
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            errors.append("integrity_check not ok")
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            errors.append(f"{len(fk)} foreign key violation(s)")
        now_posts = posts(conn)
        if set(now_posts) != set(pre_posts):
            errors.append(f"post id set changed: before {sorted(pre_posts)} after {sorted(now_posts)}")
        for pid, row in pre_posts.items():
            cur = now_posts.get(pid)
            if cur is None:
                continue
            if (cur["category"], cur["title"], cur["body"]) != (row["category"], row["title"], row["body"]):
                errors.append(f"post {pid}: legacy Post.title/body/category changed by migration")
            table = BOARD_TABLE.get(row["category"])
            if table is None:
                for t in BOARD_TABLES[:-1]:
                    n = conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE post_id=?', (pid,)).fetchone()[0]
                    if n:
                        errors.append(f"post {pid} ({row['category']}) has unexpected row in {t}")
                continue
            got = conn.execute(
                f'SELECT title, body FROM "{table}" WHERE post_id=?', (pid,)
            ).fetchall()
            if len(got) != 1:
                errors.append(f"post {pid} ({row['category']}): {len(got)} rows in {table}, expected 1")
            elif got[0] != (row["title"], row["body"]):
                errors.append(f"post {pid}: board title/body differs from Post title/body")
        # no orphan board rows
        all_posts = set(now_posts)
        for t in BOARD_TABLES[:-1]:
            orphans = [r[0] for r in conn.execute(f'SELECT post_id FROM "{t}"') if r[0] not in all_posts]
            if orphans:
                errors.append(f"{t}: orphan board rows {orphans[:5]}")
        expected_rows = sum(1 for r in pre_posts.values() if r["category"] in BOARD_TABLE)
        actual_rows = sum(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in BOARD_TABLES[:-1])
        if actual_rows != expected_rows:
            errors.append(f"board rows total {actual_rows}, expected {expected_rows}")
    finally:
        conn.close()
    return errors


def print_abort(stage: str, detail: str) -> None:
    backup = _state.get("backup")
    live = _state.get("db") == LIVE_DB
    out("")
    out("!" * 78)
    out(f"ABORT at stage: {stage}")
    out(f"Reason: {detail}")
    out("!" * 78)
    if backup and Path(backup).exists():
        out(f"Verified pre-migrate backup: {backup}")
        out(f"  sha256: {sha256(Path(backup))}")
        out(f"  size:   {Path(backup).stat().st_size} bytes")
        out("")
        out("RESTORE (this discards everything written after the backup):")
        out(f"  systemctl stop {SERVICE}")
        out(f"  install -o {SERVICE_USER} -g {SERVICE_USER} -m 600 \\")
        out(f"    {backup} {LIVE_DB}")
        out(f"  rm -f {LIVE_DB}-journal {LIVE_DB}-wal {LIVE_DB}-shm")
        out(f"  sha256sum {LIVE_DB}   # must equal the sha256 above")
        out(f"  python3 -c \"import sqlite3;print(sqlite3.connect('file:{LIVE_DB}?mode=ro',uri=True)"
            ".execute('pragma integrity_check').fetchone()[0])\"   # must print ok")
        out(f"  # keep the OLD release active (do not run activate_4c6eb61.py)")
        out(f"  systemctl start {SERVICE}")
        out("")
        out("If the migration was partially applied, also confirm the rollback marker:")
        out("  sqlite3 (or python) query: SELECT app||'.'||name FROM django_migrations "
            "ORDER BY id DESC LIMIT 3;")
        out("  The restored backup must report community.0021_commentlike and 33 user tables.")
        if not live:
            out("")
            out(f"NOTE: --db was {_state.get('db')} (rehearsal copy). The live DB was never touched;")
            out("      this restore block applies only if you replaced $LIVE_DB by hand.")
    else:
        out("No verified backup was produced, so no automatic restore is advised.")
        out("The target DB was NOT migrated: nothing to restore.")
    out("!" * 78)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="4c6eb61 DB step: backup, migrate, verify")
    ap.add_argument("--db", required=True, help="target sqlite DB (live path or an isolated copy)")
    ap.add_argument("--release", default=str(DEFAULT_RELEASE))
    ap.add_argument("--backup-dir", default=None)
    ap.add_argument("--expect-posts", type=int, default=7)
    ap.add_argument("--run-as", default=SERVICE_USER)
    ap.add_argument("--confirm-live", action="store_true",
                    help="required when --db is the live DB path")
    ap.add_argument("--rebackfill", action="store_true",
                    help="re-run 0029's idempotent backfill (post-activation gap repair), then verify")
    args = ap.parse_args(argv)

    db = Path(args.db).resolve()
    release = Path(args.release).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(args.backup_dir) if args.backup_dir else db.parent / "backups" / f"dbstep-4c6eb61-{stamp}"
    backup = backup_dir / "community.sqlite3"
    live = db == LIVE_DB
    _state.update({"db": db, "backup": None, "failed": False})

    out("=" * 78)
    out(f"4c6eb61 DB step ({'LIVE' if live else 'REHEARSAL COPY'})  {stamp}")
    out(f"target:  {db}")
    out(f"release: {release}")
    out("=" * 78)

    if live and not args.confirm_live:
        fail(2, "preconditions", "target is the live DB; pass --confirm-live to proceed")
    if not db.exists():
        fail(2, "preconditions", f"target DB not found: {db}")
    if not (release / "venv/bin/python").exists() or not (release / "thai_platform/manage.py").exists():
        fail(2, "preconditions", f"release venv/manage.py missing under {release}")
    shipped_dir = release / "thai_platform/community/migrations"
    missing = [n for n in SHIPPED if not (shipped_dir / f"{n}.py").exists()]
    if missing:
        fail(2, "preconditions", f"release does not ship migrations: {missing}")

    pre = snapshot(db)
    out(f"head: {pre['head']}   tables: {len(pre['tables'])}   posts: {len(pre['posts'])}")
    if pre["integrity"] != "ok":
        fail(2, "preconditions", f"target integrity_check = {pre['integrity']}")
    if args.rebackfill:
        if pre["head"] != EXPECTED_HEAD_AFTER:
            fail(2, "preconditions",
                 f"--rebackfill expects an already-migrated DB ({EXPECTED_HEAD_AFTER}), "
                 f"found {pre['head']!r}")
    else:
        if pre["head"] != EXPECTED_HEAD_BEFORE:
            fail(2, "preconditions",
                 f"target head is {pre['head']!r}, expected {EXPECTED_HEAD_BEFORE!r} "
                 f"(already migrated, or the wrong DB)")
        if len(pre["posts"]) != args.expect_posts:
            fail(2, "preconditions", f"{len(pre['posts'])} posts, expected {args.expect_posts}")

    if live:
        active = subprocess.run(["systemctl", "is-active", SERVICE],
                                capture_output=True, text=True).stdout.strip()
        if active == "active":
            fail(2, "preconditions",
                 f"{SERVICE} is active; stop it first so no write can land during the migration")

    if args.rebackfill:
        out(f"\n[rebackfill] backup -> {backup}")
        backup_db(db, backup, args.run_as)
        _state["backup"] = str(backup)
        out(f"      backup sha256 {sha256(backup)}")
        out("[rebackfill] re-running 0029 backfill (get_or_create, non-destructive)")
        r = run_django(release, db, ["shell", "-c",
            "import importlib,types,django;from django.db import connection;"
            "m=importlib.import_module('community.migrations.0029_backfill_board_content');"
            "m.backfill_board_content(django.apps.apps,types.SimpleNamespace(connection=connection));"
            "print('REBACKFILL_OK')"], args.run_as)
        out(r.stdout.strip()[-500:]); out(r.stderr.strip()[-800:])
        if r.returncode != 0:
            fail(3, "rebackfill", f"exit {r.returncode}")
        errs = check_board_rows(db, pre["posts"])
        if errs:
            fail(4, "rebackfill verify", "; ".join(errs))
        out("REBACKFILL PASS: every board-category post has a matching board row")
        return 0

    # ---- 1. fresh online backup, immediately before the migration ----
    out(f"\n[1/4] online backup -> {backup}")
    backup_db(db, backup, args.run_as)
    _state["backup"] = str(backup)
    bsnap = snapshot(backup)
    if bsnap["integrity"] != "ok":
        fail(2, "backup verify", f"backup integrity_check = {bsnap['integrity']}")
    if bsnap["fk_violations"]:
        fail(2, "backup verify", f"backup has {bsnap['fk_violations']} FK violations")
    if bsnap["tables"] != pre["tables"] or bsnap["counts"] != pre["counts"]:
        fail(2, "backup verify", "backup table list/row counts differ from the source snapshot")
    if bsnap["posts"] != pre["posts"]:
        fail(2, "backup verify", "backup Post rows differ from the source snapshot")
    out(f"      backup sha256 {bsnap['sha256']}")
    out(f"      backup verified: integrity ok, 0 FK violations, "
        f"{len(bsnap['tables'])} tables, {len(bsnap['posts'])} posts, rows identical")

    # ---- 2. no writes between backup and migrate ----
    out("\n[2/4] re-reading target to prove nothing changed since the backup")
    now = snapshot(db)
    if now["posts"] != pre["posts"] or now["counts"] != pre["counts"]:
        fail(2, "drift check",
             "the target changed between the backup and the migration; a post or row was written "
             "in that window. Restore nothing; delete the backup and re-run this script.")
    out("      unchanged: no posts or rows written in the backup window")

    # ---- 3. migrate ----
    out("\n[3/4] applying migrations 0022..0029")
    r = run_django(release, db, ["migrate", "--noinput"], args.run_as)
    for line in (r.stdout + r.stderr).splitlines():
        if line.strip():
            out("      " + line.strip())
    if r.returncode != 0:
        fail(3, "migrate", f"manage.py migrate exited {r.returncode}")

    # ---- 4. verify ----
    out("\n[4/4] verification")
    post = snapshot(db)
    errs = []
    if post["integrity"] != "ok":
        errs.append(f"integrity_check = {post['integrity']}")
    if post["fk_violations"]:
        errs.append(f"{post['fk_violations']} FK violations")
    if post["head"] != EXPECTED_HEAD_AFTER:
        errs.append(f"head is {post['head']!r}, expected {EXPECTED_HEAD_AFTER!r}")
    applied = set(post["migrations"].get("community", []))
    missing_applied = [n for n in SHIPPED if n not in applied]
    if missing_applied:
        errs.append(f"not recorded in django_migrations: {missing_applied}")
    new_tables = set(post["tables"]) - set(pre["tables"])
    if new_tables != set(BOARD_TABLES):
        errs.append(f"new tables {sorted(new_tables)}, expected {sorted(BOARD_TABLES)}")
    gone = set(pre["tables"]) - set(post["tables"])
    if gone:
        errs.append(f"tables lost: {sorted(gone)}")
    for t, n in pre["counts"].items():
        got = post["counts"].get(t)
        if got != n:
            if t in METADATA_TABLES:
                # post_migrate legitimately adds content types / permissions
                if got is None or got < n:
                    errs.append(f"metadata rows removed from {t}: {n} -> {got}")
            else:
                errs.append(f"row count changed in {t}: {n} -> {got}")
    errs += check_board_rows(db, pre["posts"])
    if errs:
        fail(4, "verification", "; ".join(errs))

    board_rows = sum(post["counts"][t] for t in BOARD_TABLES[:-1])
    receipt = {
        "stamp": stamp, "db": str(db), "live": live, "release": str(release),
        "backup": str(backup), "backup_sha256": bsnap["sha256"], "backup_size": bsnap["size"],
        "head_before": pre["head"], "head_after": post["head"],
        "tables_before": len(pre["tables"]), "tables_after": len(post["tables"]),
        "posts": len(post["posts"]), "board_rows": board_rows,
        "migrated_sha256": post["sha256"], "migrated_size": post["size"],
        "applied": [f"community.{n}" for n in SHIPPED],
    }
    receipt_path = backup_dir / "dbstep-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    if os.geteuid() == 0:
        os.chmod(receipt_path, 0o600)

    out(f"      head {post['head']}  tables {len(pre['tables'])} -> {len(post['tables'])}  "
        f"posts {len(post['posts'])}  board rows {board_rows}")
    out(f"      all {len(pre['counts'])} pre-existing tables keep their exact row counts")
    out(f"      all {len(post['posts'])} posts: legacy title/body unchanged, board row identical")
    out(f"      receipt {receipt_path}")
    out("")
    out("=" * 78)
    out("DB STEP PASS")
    out(f"  backup: {backup}  (sha256 {bsnap['sha256']})")
    out(f"  migrated: {db}  (sha256 {post['sha256']})")
    out("=" * 78)
    if live:
        out("")
        out("OPTION A WINDOW IS NOW OPEN: the DB is migrated, the old release is still serving.")
        out("  * old code writes Post.title/body only -> new code will show blank/stale content")
        out("  * activate immediately (activate_4c6eb61.py --apply with post-migration facts)")
        out("  * if any post is created or edited before activation, repair with:")
        out(f"      python3 {Path(__file__).name} --db {db} --release {release} --rebackfill")
        out("    0029 is idempotent: it fills missing board rows and never overwrites existing ones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
