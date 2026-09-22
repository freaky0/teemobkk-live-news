#!/usr/bin/env bash
# Post the items the VPS agent queued, through the same renderer the timer uses.
#
# The agent runs in a container that has only its own data directory mounted, so it cannot call the
# pusher itself. It writes the JSON parts of a post into its data directory instead, the host sees
# that directory under the bind mount, and this script is the bridge: each file goes to
# `tg_push.py --agent-json`, which renders the post through the same render() the timer uses and
# runs the same shape check. A file that cannot be posted is left in place, so the next run retries
# it and the reason stays in the log.
#
# Run as root from teemo-tg-outbox.service: the outbox belongs to the container's user, while the
# pusher itself runs as teemo (runuser) because news.db and its WAL files belong to that user.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
OUTBOX="${OUTBOX:-/docker/hermes-agent-hjzo/data/tg_outbox}"
LOG="${LOG:-/var/log/teemo-tg-outbox.log}"

[ -d "$OUTBOX" ] || exit 0
shopt -s nullglob
files=("$OUTBOX"/*.json)
[ "${#files[@]}" -gt 0 ] || exit 0
mkdir -p "$OUTBOX/done"

# The bot token and the thresholds live in the pusher's own environment file. Sourcing it here
# keeps this bridge from holding a second copy of the secret, and systemd's parser and the shell
# agree on the quoting because the file is written for both.
set -a
# shellcheck disable=SC1090
. "$APP_DIR/.env.push"
set +a

for file in "${files[@]}"; do
  name="$(basename "$file")"
  staged="/tmp/teemo-tg-outbox-$name"
  cp -f "$file" "$staged"
  chown "$APP_USER:$APP_USER" "$staged"
  chmod 600 "$staged"
  if runuser -u "$APP_USER" --preserve-environment -- \
       python3 "$APP_DIR/deploy/tg_push.py" --agent-json "$staged" >>"$LOG" 2>&1; then
    mv -f "$file" "$OUTBOX/done/$name"
  fi
  rm -f "$staged"
done
