#!/usr/bin/env bash
# Starts the engine on 8020. Alpaca keys come from ~/backtest-ceo/.env, else the ALPACA_ lines of ~/scalp-city/.env.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
for f in "$DIR/../.env" "$HOME/scalp-city/.env"; do
  if [ -f "$f" ]; then
    set -a; eval "$(grep -E '^ALPACA_(API_KEY|SECRET_KEY)=' "$f")"; set +a
    break
  fi
done
cd "$DIR" && exec .venv/bin/uvicorn backtestceo.server:app --host 127.0.0.1 --port "${BACKTEST_CEO_ENGINE_PORT:-8020}"
