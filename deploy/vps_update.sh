#!/usr/bin/env bash
# Update the host from this repository and restart the collector. Run from the repository root.
#
# Four things the order here protects against:
#
#  * The collector reads index.html from disk on every request, and that file is not in this
#    repository any more: each machine builds its own (the host's copy carries landing.py's live post
#    list, a developer's copy is the operator page built from their own database). A `git reset
#    --hard` therefore deletes it on the way in, so it is staged before the update and put back when
#    the update removed it. Without that, "/" would answer nothing for the seconds between the reset
#    and the rebuild below. The rebuild still happens between the update and the restart.
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
# Where the served page is kept across an update. Outside the checkout on purpose (see below): a copy
# left inside it would be untracked clutter in every later `git status` there. Same home as the
# pusher's staging directory, /var/lib/teemo-tg-outbox.
STAGING_DIR="${STAGING_DIR:-/var/lib/teemo-live-news}"
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
  # No listener is required beforehand any more: the local page is not something the operator keeps
  # running, and the check suite starts its own collector (and stops it again). A server that will
  # not come up fails the suite, which stops this deploy the same way a missing one used to.
  say "page checks (${PYTHON:-python} tests/run.py --local)"
  if ! "${PYTHON:-python}" tests/run.py --local; then
    say "page checks FAILED - nothing was deployed"
    exit 1
  fi
fi

pulled=0
# The served page is not in the repository, so an update can delete the running one (reset --hard
# drops a file the target commit no longer tracks). It is staged here, before anything is fetched or
# unpacked, and put back below when the update took it. The copy is kept outside the checkout: a file
# left inside would be untracked clutter in every later `git status` on that host.
STAGED="$STAGING_DIR/index.html"
remote "mkdir -p $STAGING_DIR && chown $APP_USER:$APP_USER $STAGING_DIR"
remote "cd $APP_DIR && [ -s index.html ] && runuser -u $APP_USER -- cp -p index.html $STAGED" \
  || say "no served page to stage (a host that has never built one)"
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

# Put the staged page back only when the update removed it: a page that is still there is the newer of
# the two (this host's own builder wrote it), and the rebuild below replaces whichever one is here.
if remote "cd $APP_DIR && [ ! -s index.html ] && [ -s $STAGED ]"; then
  say "the update left no served page: putting the staged one back before the rebuild"
  remote "cd $APP_DIR && runuser -u $APP_USER -- cp -p $STAGED index.html"
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
# What the sources answer *from this host*, printed on every deploy. Several feeds answer a home
# connection 200 and this host 403 or 429 (measured: FXStreet 403, FinancialJuice 429), so a feed
# that looks alive while it is being added can be dead in production, and the missing rows are the
# only symptom. A dead source does not stop the deploy - a feed can be down for an hour - but it is
# never allowed to pass silently.
say "source check (from the host, not fatal)"
remote "cd $APP_DIR && runuser -u $APP_USER -- python3 tools/probe_sources.py --listed 2>/dev/null |
        grep -vE '^  (ok|dead) ' | tail -6" || true

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