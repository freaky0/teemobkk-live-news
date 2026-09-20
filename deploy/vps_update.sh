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
#  * Git is tried first. The upload is only a fallback for a host with no checkout, or one that
#    cannot reach the repository.
set -euo pipefail

HOST="${HOST:-root@72.62.64.195}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
SERVICE="${SERVICE:-teemo-live-news}"
PORT="${PORT:-8765}"
SITE="${SITE:-https://teemobkk.io/news/}"
SECTIONS="https://teemobkk.io/ https://teemobkk.io/news/ https://teemobkk.io/news/ko/ https://teemobkk.io/thai/ https://teemobkk.io/thai/news/ https://teemobkk.io/thai/news/ko/"

say() { printf '  %s\n' "$*"; }
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

say "local commit: $(git log -1 --format=%h)"

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

for url in $SECTIONS; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url" --max-time 15 || true)
  printf '  %-40s %s\n' "$url" "$code"
done

code=$(curl -s -o /dev/null -w '%{http_code}' "$SITE" --max-time 15 || true)
if [ "$code" != "200" ]; then
  say "the dashboard did not answer: check: ssh $HOST journalctl -u $SERVICE -n 40"
  exit 1
fi