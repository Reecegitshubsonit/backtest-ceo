#!/usr/bin/env bash
# Paper runner + live-events feed.
#   engine/paper.sh up --dry-run     feed on 8030 (if not already up) + DRY RUN runner (fake brokers, replayed bars)
#   engine/paper.sh up --paper       feed + PAPER runner (Alpaca paper + Webull sandbox; refuses unless the safety flags pass)
#   engine/paper.sh down             stop the runner, then the feed if this script started it
#   engine/paper.sh <cmd> [...]      anything else goes to: python -m backtestceo.paper <cmd>  (check, status, kill, unkill, smoke-test)
# Keys are read by the runner itself from ../.env (names only, never printed); this script never reads that file.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$DIR/.." && pwd)"
PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
STATE="${BACKTEST_CEO_CACHE:-$HOME/.cache/backtest-ceo}/paper"; mkdir -p "$STATE"
FEED_PID="$STATE/live-events.pid"; FEED_URL="${LIVE_EVENTS_URL:-http://127.0.0.1:8030}"
run() { cd "$DIR" && "$PY" -m backtestceo.paper "$@"; }

feed_up() {
  if curl -fs -m 2 "$FEED_URL/v1/health" >/dev/null 2>&1; then echo "live-events already answering at $FEED_URL"; return 0; fi
  command -v node >/dev/null || { echo "node not found: cannot start live-events"; return 1; }
  PORT="${FEED_URL##*:}"; PORT="${PORT%%/*}"
  # no --seed: the runner publishes one strategy_result per ACTIVE paper leg on its first tick (seeding would bring back
  # backtest-only strategies such as AEX / EMA150 on the wall)
  nohup node "$REPO/services/live-events/server.mjs" --port "$PORT" \
    --log "$STATE/live-events.jsonl" >>"$STATE/live-events.log" 2>&1 &
  echo $! >"$FEED_PID"
  for _ in $(seq 1 20); do curl -fs -m 1 "$FEED_URL/v1/health" >/dev/null 2>&1 && { echo "live-events started (pid $(cat "$FEED_PID")) at $FEED_URL"; return 0; }; sleep 0.25; done
  echo "live-events did not come up; see $STATE/live-events.log"; return 1
}

case "${1:-}" in
  up)
    shift; MODE="${1:---dry-run}"; shift || true
    feed_up || exit 1
    case "$MODE" in
      --dry-run) run start --dry-run --live-events "$FEED_URL" "$@" ;;
      --paper)   run start --live-events "$FEED_URL" "$@" ;;
      *) echo "usage: paper.sh up [--dry-run|--paper] [runner options]"; exit 2 ;;
    esac ;;
  down)
    run stop
    if [ -f "$FEED_PID" ]; then kill "$(cat "$FEED_PID")" 2>/dev/null && echo "live-events stopped"; rm -f "$FEED_PID"
    else echo "live-events was not started by paper.sh; left running"; fi ;;
  ""|-h|--help) sed -n 2,8p "$0" ;;
  *) run "$@" ;;
esac
