#!/usr/bin/env bash
# Update the host from this repository and restart the collector. Run from the repository root.
#
# Three things the order here protects against:
#
#  * The collector reads index.html from disk on every request, and this repository also holds a
#    committed index.html - the operator's page, which shows collection state. A checkout that is
#    not immediately followed by a rebuild would briefly serve that page, so the rebuild happens
#    between the update and the restart.
#  * An upload runs as root, and root-owned files make both the rebuild and a later git reset
#    fail with a permission error, so ownership is restored before either happens.
#  * The page builder reads the stored rows, so the schema is migrated before it runs. A page
#    built against a database that has not been migrated yet is served without its first screen
#    (measured: a rebuild that ran before the column existed produced a seeded page with 0 cards).
#  * Git is tried first. The upload is only a fallback for a host with no checkout, or one that
#    cannot reach the repository.
set -euo pipefail

HOST="${HOST:-root@72.62.64.195}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
SERVICE="${SERVICE:-teemo-live-news}"
PORT="${PORT:-8765}"
# The address list below is the whole public surface, including the dashboard itself, so there is
# no separate "the site URL" variable to keep in sync with it.
SECTIONS="https://teemobkk.io/ https://teemobkk.io/news/ https://teemobkk.io/news/ko/ https://teemobkk.io/thai/ https://teemobkk.io/thai/news/ https://teemobkk.io/thai/news/ko/ https://teemobkk.io/admin"

say() { printf '  %s\n' "$*"; }
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

say "local commit: $(git log -1 --format=%h)"

# The page checks run before anything touches the host. They are the only thing standing between a
# broken page and the public URL, so a failure stops the deploy where it is. SKIP_TESTS=1 bypasses
# them for an emergency and prints that it did, so the log never looks like they ran.
if [ "${SKIP_TESTS:-0}" = "1" ]; then
  say "page checks: SKIPPED (SKIP_TESTS=1) - nothing was verified before this deploy"
else
  # Shell redirection, not `curl -o /dev/null`: in this MSYS shell curl exits 23 (write error) even
  # on a 200 because it cannot write to the /dev/null it resolves, so the exit code cannot be used
  # as the health signal there.
  if ! curl -s --max-time 5 "http://127.0.0.1:$PORT/" >/dev/null; then
    say "the local dashboard is not answering on 127.0.0.1:$PORT"
    say "start it with start_dashboard_bg.bat, or set SKIP_TESTS=1 to deploy without checks"
    exit 1
  fi
  say "page checks (${PYTHON:-python} tests/run.py --local)"
  if ! "${PYTHON:-python}" tests/run.py --local; then
    say "page checks FAILED - nothing was deployed"
    exit 1
  fi
fi

pulled=0
if remote "test -d $APP_DIR/.git" 2>/dev/null; then
  say "host has a checkout: restoring ownership, then pulling"
  if remote "chown -R $APP_USER:$APP_USER $APP_DIR &&
             runuser -u $APP_USER -- git -C $APP_DIR fetch -q origin main &&
             runuser -u $APP_USER -- git -C $APP_DIR reset --hard -q origin/main"; then
    pulled=1
    say "git: now at $(remote "runuser -u $APP_USER -- git -C $APP_DIR log -1 --format=%h" | tr -d '\r')"
  else
    say "pull failed, falling back to an upload"
  fi
fi

if [ "$pulled" -eq 0 ]; then
  say "uploading this commit"
  git archive --format=tar HEAD | remote "tar -x -C $APP_DIR"
  remote "chown -R $APP_USER:$APP_USER $APP_DIR"
fi

say "rebuilding the served page, then restarting"
remote "cd $APP_DIR &&
        chown -R $APP_USER:$APP_USER $APP_DIR &&
        runuser -u $APP_USER -- python3 -c 'import live_news_dashboard as core; core.init_db()' >/dev/null &&
        runuser -u $APP_USER -- python3 -c 'import page_build; page_build.build_server()' >/dev/null &&
        systemctl restart $SERVICE.service &&
        sleep 5 &&
        printf '    service: %s\n' \"\$(systemctl is-active $SERVICE.service)\" &&
        printf '    http:    %s\n' \"\$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/)\" &&
        python3 -c \"
import sqlite3
rows = sqlite3.connect('$APP_DIR/news.db').execute('SELECT COUNT(*) FROM articles').fetchone()[0]
print('    database: %d articles' % rows)
\""

missing=""
for url in $SECTIONS; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url" --max-time 15 || true)
  printf '  %-40s %s\n' "$url" "$code"
  [ "$code" = "200" ] || missing="$missing $url($code)"
done

# Every address is enforced, not just the dashboard: a page that answers 404 or 500 on a section
# path is a public failure even when the collector underneath is healthy.
if [ -n "$missing" ]; then
  say "these addresses did not answer 200:$missing"
  say "check: ssh $HOST journalctl -u $SERVICE -n 40"
  exit 1
fi