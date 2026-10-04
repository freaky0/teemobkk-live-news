#!/usr/bin/env bash
# Post the items the VPS agent queued, through the same renderer the timer uses.
#
# The agent runs in a container that has only its own data directory mounted, so it cannot call the
# pusher itself. It writes the JSON parts of a post into its data directory instead, the host sees
# that directory under the bind mount, and this script is the bridge:
#
#   1. stage every queued file into a directory owned by teemo, and take it out of the watched
#      directory in the same pass. A file left in the watched directory keeps the path unit firing
#      until systemd's start limit fails it (measured on this host: four starts in 34 seconds, both
#      units failed).
#   2. run `tg_push.py --drain-outbox` as teemo, which renders each item through the same render()
#      the timer uses, runs the same shape check, and moves the file to done/ or failed/. The
#      reason for a refusal lands in the log; a dry run (TG_DRY_RUN=1) moves nothing.
#
# Run as root from teemo-tg-outbox.service: the outbox belongs to the container's user, while the
# pusher itself runs as teemo (runuser) because news.db and its WAL files belong to that user.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
OUTBOX="${OUTBOX:-/docker/hermes-agent-hjzo/data/tg_outbox}"
STAGING="${STAGING:-/var/lib/teemo-tg-outbox}"
LOG="${LOG:-/var/log/teemo-tg-outbox.log}"

[ -d "$OUTBOX" ] || exit 0
shopt -s nullglob
files=("$OUTBOX"/*.json)
[ "${#files[@]}" -gt 0 ] || exit 0

mkdir -p "$STAGING"
chown "$APP_USER:$APP_USER" "$STAGING"
chmod 700 "$STAGING"

for file in "${files[@]}"; do
  name="$(basename "$file")"
  cp -f "$file" "$STAGING/$name"
  chown "$APP_USER:$APP_USER" "$STAGING/$name"
  rm -f "$file"
done

# The bot token and the thresholds live in the pusher's own environment file. Sourcing it here
# keeps this bridge from holding a second copy of the secret, and systemd's parser and the shell
# agree on the quoting because the file is written for both.
set -a
# shellcheck disable=SC1090
. "$APP_DIR/.env.push"
set +a

runuser -u "$APP_USER" --preserve-environment -- \
  python3 "$APP_DIR/deploy/tg_push.py" --drain-outbox "$STAGING" >>"$LOG" 2>&1
