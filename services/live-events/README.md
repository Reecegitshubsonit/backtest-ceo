# live-events

Repo copy of the live-events prototype (built on the box at /workspace/live-events). Test data and the test driver are not included.
Start it together with the paper runner: `engine/paper.sh up --dry-run` (or `--paper`); stop both with `engine/paper.sh down`.

Separate service the agents and the backtest runner POST to, and the 3D room reads. Not the engine; nothing in the engine or the repo changes.

Run:  node services/live-events/server.mjs --seed engine/backtestceo/paper/reference_results.json   (port 8030; --port, --log, --origin a,b)
Room: http://127.0.0.1:5175/  (reads http://127.0.0.1:8030 by default; ?live=<url> to override; ?demo=1 = labelled simulation)
Snapshot module for the room: node make_snapshot.mjs > <repo>/web3d/src/room3d/resultsSnapshot.ts

Endpoints
  POST /v1/events            one event or an array -> 202 {accepted, seq}; 400 {error} on a bad event
  GET  /v1/events?since=N    {boot, seq, head, events[]}  (room polls this every 1 s; new boot = restart, start over)
  GET  /v1/stream            SSE, one event per message (id = seq)
  GET  /v1/state             materialised {agents, decisions, strategies}
  GET  /v1/health            {ok, boot, seq, retained}
CORS: http://localhost:5175, http://127.0.0.1:5175 (+ --origin). Storage: in memory + JSONL append log (events.jsonl), replayed at start.
Retention: every ceo_decision (latest per id), the latest strategy_result per strategy, the last 50 agent_activity per slot.

Events (server adds seq; `at` defaults to now)
  agent_activity  {kind, slot: scanner|strategist|backtester|auditor|regime|risk, task, state: idle|working|waiting|error,
                   strategy?, symbol?, progress?: 0..1, log?, level?: info|warn|error, source?}
  ceo_decision    {kind, id, agent: <slot>, strategy, reason, outcome: approved|rejected|pending, time?, source?}   same id again = update
  strategy_result {kind, strategy, name, market?, stage: scanning|strategist|backtest|validation|risk|ceo,
                   stats{trades, win_rate(%), profit_factor, net_return_pct, max_drawdown_pct, sharpe?},
                   in_sample?, out_of_sample?, equity: number[] (multiple of start), trades[{entry_time, exit_time, side, entry, exit, ret}], runs?, source?}

Example
  curl -X POST http://127.0.0.1:8030/v1/events -H 'content-type: application/json' \
    -d '{"kind":"agent_activity","slot":"backtester","task":"Backtesting EMA 9/21","strategy":"EMA 9/21 Cross, 2% Stop","symbol":"BTC/USD","progress":0.4,"log":"bar 40k/100k"}'

Paper runner (engine/backtestceo/paper) posts all three kinds. Its strategy_result events carry the reference fields
above plus an extra `paper` object (the server keeps unknown fields):
  paper {mode: paper|dry-run, label, status, pnl{realized_usd, unrealized_usd, total_usd}, caps{...}, backtest_only_runs[],
         legs[{key, run, symbol, broker, status, stage, position{side, qty, entry, stop, mark, unrealized_usd}|null,
               fills[{time, side, qty, price, client_order_id, reason, broker}], closed[...], realized_usd, unrealized_usd,
               entries_today, last_error}], updated}
