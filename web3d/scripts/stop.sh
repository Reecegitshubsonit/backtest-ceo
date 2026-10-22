#!/usr/bin/env bash
# Stops the view (5175) and the engine (8020).
for PORT in "${BACKTEST_CEO_VIEW_PORT:-5175}" "${BACKTEST_CEO_ENGINE_PORT:-8020}"; do
  pids=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u)
  [ -n "$pids" ] && kill $pids
done
exit 0
