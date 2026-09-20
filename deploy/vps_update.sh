#!/usr/bin/env bash
# Update the host from this repository and restart the collector. Run from the repository root.
#
# Order matters. The collector reads index.html from disk on every request, and this repository
# also holds a committed index.html - the operator's page, which shows collection state. So a
# checkout that is not immediately followed by a rebuild would briefly serve that page. The
# rebuild therefore happens between the update and the restart.
#
# Two transports: a git pull when the host has a checkout that can reach the repository (it is
# public, so no credential is needed), otherwise an upload of this commit. Either way the files
# are handed back to the service user, because a root-owned index.html makes the rebuild fail.
set -euo pipefail

HOST="${HOST:-root@72.62.64.195}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
SERVICE="${SERVICE:-teemo-live-news}"
PORT="${PORT:-8765}"
SITE="${SITE:-https://teemobkk.io/}"

say() { printf '  %s\n' "$*"; }

say "local commit: $(git log -1 --format=%h)"
say "uploading as the fallback for a host without a reachable checkout"
git archive --format=tar HEAD | ssh -o BatchMode=yes "$HOST" "tar -x -C $APP_DIR"

say "updating on the host"
ssh -o BatchMode=yes "$HOST" "
  set -e
  cd $APP_DIR
  if [ -d .git ] && runuser -u $APP_USER -- git fetch -q origin main 2>/dev/null; then
    runuser -u $APP_USER -- git reset --hard -q origin/main
    echo \"    git: now at \$(runuser -u $APP_USER -- git log -1 --format=%h)\"
  else
    echo '    git: no checkout or no remote access, keeping the uploaded files'
  fi
  chown -R $APP_USER:$APP_USER $APP_DIR
  runuser -u $APP_USER -- python3 -c 'import page_build; page_build.build_server()' >/dev/null
  systemctl restart $SERVICE.service
  sleep 5
  echo \"    service: \$(systemctl is-active $SERVICE.service)\"
  echo \"    http:    \$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/)\"
  python3 - <<PY
import sqlite3
rows = sqlite3.connect('$APP_DIR/news.db').execute('SELECT COUNT(*) FROM articles').fetchone()[0]
print('    database: %d articles' % rows)
PY
"

code=$(curl -s -o /dev/null -w '%{http_code}' "$SITE" --max-time 15 || true)
say "$SITE -> $code"
if [ "$code" != "200" ]; then
  say "check: ssh $HOST journalctl -u $SERVICE -n 40"
  exit 1
fi