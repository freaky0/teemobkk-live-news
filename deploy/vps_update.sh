#!/usr/bin/env bash
# Push this checkout to the host and restart the collector. Run from the repository root.
#
# The upload happens as root, so ownership has to be handed back to the service user afterwards:
# the page is rebuilt on every start, and a root-owned index.html makes that rebuild fail with a
# permission error, which stops the service. The repository is private, so this uploads a tar of
# the current commit instead of the host pulling; add a deploy key to the repository and the host
# can use git instead.
set -euo pipefail

HOST="${HOST:-root@72.62.64.195}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
SERVICE="${SERVICE:-teemo-live-news}"

say() { printf '  %s\n' "$*"; }

say "uploading $(git log -1 --format=%h) to $HOST"
git archive --format=tar HEAD | ssh -o BatchMode=yes "$HOST" "tar -x -C $APP_DIR"

say "restoring ownership and restarting"
ssh -o BatchMode=yes "$HOST" "chown -R $APP_USER:$APP_USER $APP_DIR && systemctl restart $SERVICE.service"

sleep 6
state=$(ssh -o BatchMode=yes "$HOST" "systemctl is-active $SERVICE.service")
code=$(ssh -o BatchMode=yes "$HOST" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/")
say "service: $state"
say "local HTTP: $code"
if [ "$state" != "active" ] || [ "$code" != "200" ]; then
  say "check the log: ssh $HOST journalctl -u $SERVICE -n 40"
  exit 1
fi