"""Launch the local dashboard in a fully detached process and return at once.

Called by start_dashboard_bg.bat. Python is used for the spawn rather than
Start-Process because of how a hidden child is attached: a hidden Start-Process
window inherits the caller's console, and anything that launched it then waits for
the server to exit (measured: a 5-minute agent tool call hanging on a server that
was healthy the whole time). DETACHED_PROCESS gives the child no console at all, so
the caller is free the moment this returns and the server outlives it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = os.environ.get("DASH_PORT", "8765")
INTERVAL = os.environ.get("DASH_INTERVAL", "30")
LOG = HERE / "local.log"
ERR = HERE / "local.log.err"

# Keep the previous run's output instead of truncating it: a hidden, console-less
# server leaves no other trace, so a crash would otherwise have nothing to read.
for path in (LOG, ERR):
    if not path.exists():
        continue
    previous = path.with_name(path.name + ".prev")
    if previous.exists():
        previous.unlink()
    path.rename(previous)

out = open(LOG, "ab", buffering=0)
err = open(ERR, "ab", buffering=0)
flags = 0
if hasattr(subprocess, "DETACHED_PROCESS"):
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

process = subprocess.Popen(
    [sys.executable, "live_news_dashboard.py", "--interval", INTERVAL, "--port", PORT],
    cwd=str(HERE),
    stdin=subprocess.DEVNULL,
    stdout=out,
    stderr=err,
    creationflags=flags,
    close_fds=True,
)
print("  spawned pid %d with python %s" % (process.pid, sys.version.split()[0]))