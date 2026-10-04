#!/usr/bin/env bash
# Install the Telegram channel push on the host, once. Run from the repository root.
#
# The pusher itself is code in this repository (`deploy/tg_push.py`), so it arrives with the normal
# deploy. This script only puts the two unit files in place, checks the secret file exists, and
# starts the timer - re-running it is safe and is also the way to pick up an edited unit file.
#
# The secret file is deliberately NOT created here: it holds the bot token, the channel id and the
# rewrite provider's key. Put it on the host by hand (0600, owned by the service user) before
# running this, e.g.
#
#   APP_USER=teemo APP_DIR=/opt/teemo-live-news bash deploy/vps_push_setup.sh
#
# Safe to re-run: it rewrites the units and restarts the timer.
set -euo pipefail

HOST="${HOST:-root@72.62.64.195}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
ENV_FILE="$APP_DIR/.env.push"
SERVICE="teemo-tg-push.service"
TIMER="teemo-tg-push.timer"

say() { printf '  %s\n' "$*"; }
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

say "local commit: $(git log -1 --format=%h)"

if ! remote "test -s $ENV_FILE"; then
  say "$HOST:$ENV_FILE is missing or empty - put the secrets there first:"
  say "  TELEGRAM_BOT_TOKEN=... / TELEGRAM_CHAT_ID=... / OPENAI_API_KEY=..."
  exit 1
fi
say "secret file present: $(remote "stat -c '%a %U:%G' $ENV_FILE" | tr -d '\r')"

say "installing units"
scp -q deploy/teemo-tg-push.service deploy/teemo-tg-push.timer "$HOST:/tmp/"
remote "mv /tmp/$SERVICE /tmp/$TIMER $UNIT_DIR/ && chown root:root $UNIT_DIR/$SERVICE $UNIT_DIR/$TIMER &&
        chmod 644 $UNIT_DIR/$SERVICE $UNIT_DIR/$TIMER &&
        systemctl daemon-reload &&
        systemctl enable --now $TIMER >/dev/null &&
        systemctl restart $TIMER"

say "timer state"
remote "systemctl is-enabled $TIMER; systemctl is-active $TIMER; systemctl list-timers $TIMER --no-pager | head -3"

# One tick by hand, so the first failure is visible here instead of in the channel. The dry run
# writes nothing and posts nothing; the real tick that follows is the one that reaches Telegram.
say "dry run on the host (no writes, no posts)"
remote "cd $APP_DIR && runuser -u $APP_USER -- env \$(grep -v '^#' $ENV_FILE | xargs) TG_DRY_RUN=1 \
        python3 deploy/tg_push.py --dry-run --limit 3 2>&1 | tail -20"

say "done. watch it with:"
say "  ssh $HOST journalctl -u $SERVICE -n 40 --no-pager"
say "  ssh $HOST 'systemctl stop $TIMER'   # pause the channel"
