#!/usr/bin/env bash
# Dock launcher: starts the engine (8020) and the view (5175) if they are down, then opens Firefox.
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VIEW="${BACKTEST_CEO_VIEW_PORT:-5175}"
ENGINE="${BACKTEST_CEO_ENGINE_PORT:-8020}"
LOGDIR="${XDG_CACHE_HOME:-$HOME/.cache}"
up() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
mkdir -p "$LOGDIR"
if ! up "$ENGINE"; then
  nohup "$ROOT/engine/run.sh" >"$LOGDIR/backtest-ceo-engine.log" 2>&1 &
fi
if ! up "$VIEW"; then
  (cd "$DIR" && VITE_ENGINE_URL="http://127.0.0.1:$ENGINE" nohup npx vite --port "$VIEW" --strictPort >"$LOGDIR/backtest-ceo-view.log" 2>&1 &)
fi
for _ in $(seq 1 40); do up "$VIEW" && break; sleep 0.5; done
exec firefox --new-window "http://localhost:$VIEW/"
