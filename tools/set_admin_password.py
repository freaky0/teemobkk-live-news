#!/usr/bin/env python3
"""Set the admin password for the deployed dashboard.

Run this on the host that serves the site. It reads the password without echoing it, so it never
enters a shell history, a chat log or this repository:

    ssh root@<host> "cd /opt/teemo-live-news && runuser -u teemo -- python3 tools/set_admin_password.py"

Writing the file also invalidates every existing session, because the cookie key is derived from it.

    --remove   delete the password file, which closes every write path again
"""
import argparse
import getpass
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / ".admin_password"
MIN_LENGTH = 12


def write_secret(path: Path, secret: bytes) -> None:
    # Create with the right mode from the start, then narrow it: a file created world-readable and
    # chmodded afterwards was readable for that moment.
    handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(handle, secret)
    finally:
        os.close(handle)
    os.chmod(str(path), stat.S_IRUSR | stat.S_IWUSR)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="delete the password file")
    parser.add_argument("--file", default=str(TARGET))
    args = parser.parse_args()
    path = Path(args.file)

    if args.remove:
        if path.exists():
            path.unlink()
            print("removed %s - every write path is closed again" % path)
        else:
            print("no password file at %s" % path)
        return 0

    first = getpass.getpass("admin password: ")
    if len(first) < MIN_LENGTH:
        print("too short: use at least %d characters" % MIN_LENGTH)
        return 1
    if first != getpass.getpass("repeat: "):
        print("the two entries differ")
        return 1
    write_secret(path, first.encode("utf-8"))
    mode = stat.S_IMODE(path.stat().st_mode)
    print("wrote %s (mode %o)" % (path, mode))
    print("existing sessions are invalid; log in again on /admin/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
