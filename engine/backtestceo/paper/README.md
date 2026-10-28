# Paper runner (Alpaca paper + Webull sandbox only)

New package; no existing engine file changed. Rules are ported from `/workspace/backtests/backtest.py` (parity tests
in `engine/tests/test_paper_parity.py`); reference stats are `reference_results.json` (a copy of its results.json).

| Runner key | Strategy (results.json run) | Broker | Notes |
|---|---|---|---|
| sip_pltr, sip_tsla, sip_arkk | Stocks-in-Play 5-min ORB (backtest_alpaca.py `sip`) | Webull sandbox | open > $5, 14d avg vol > 1M, ATR14 > $0.50, first-5m rel vol >= 1.0; stop entry at the OR high/low in the first candle's direction (long & short); stop 10% ATR14 (entry bar: close through); exit 15:58 ET |
| rsi2_smh, rsi2_amd | RSI(2) pullback (Connors) | Webull sandbox | 15:55 ET: close > SMA200 and RSI(2) < 10 -> buy; exit at the first close > SMA5. Long only |
| overnight_nvda, overnight_mstr, overnight_lly | Overnight hold | Webull sandbox | buy 15:55 ET, sell at the next session's open |
| first5m_qqq | First 5-min RTH candle, QQQ | none | removed from the paper set 2026-10-28 (failed out of sample on Alpaca data); backtest-only |
| supertrend_eth4h / _btc4h | Adaptive SuperTrend Confluence 4h | Alpaca paper | long side only (Alpaca crypto cannot short) |
| ai_ema_adx_eth4h / _btc4h | EMA200 + ADX25 4h | Alpaca paper | long side only |
| ema9_21_btc1h | EMA 9/21 cross, 2% stop, 1h | Alpaca paper | long only (as tested) |
| first5m_nq, aex_first_hour, *_tuned | | none | backtest-only, listed on the wall, never traded |

Run (from `engine/`):

    ./paper.sh up --dry-run        # live-events feed on 8030 + DRY RUN runner (fake brokers, replayed sample bars)
    ./paper.sh up --paper          # feed + PAPER runner (refuses unless the safety checks pass)
    ./paper.sh down                # stop runner, and the feed if paper.sh started it
    ./paper.sh check | status | kill | unkill
    ./paper.sh smoke-test [--broker alpaca|webull|both] [--extended-hours]            # prints the plan only
    ./paper.sh smoke-test --confirm [--extended-hours]                                # sends the tiny paper orders

Webull needs the official SDK in the engine venv: `.venv/bin/pip install webull-openapi-python-sdk` (paper mode only).

Safety: refuses to start unless `WEBULL_ENV=sandbox`, `ALPACA_PAPER_TRADING_ONLY=true` and any Alpaca/Webull URL variable
points at `paper-api.alpaca.markets` / `api.sandbox.webull.com`. Orders can only go to those two hosts (allowlist in
`safety.py`); bars come from `data.alpaca.markets` (read-only). `PAPER_TRADING_KILL_SWITCH` (process env or re-read from
`.env` every loop) or a `KILL` file (`paper.sh kill`) is checked before every order and in the main loop; it halts the
runner and leaves open paper positions alone. Caps (`config.py`, tighten with `--config file.json`): 1 open position and
$2,000 notional per strategy, 4 entries per strategy per day, 16 per runner per day. Exits are never capped.

Pipeline per signal (all RULE-BASED, labelled so in every event): Scanner (rule fired on a completed bar) -> Regime
Analyst (advisory ADX label) -> Strategist (order plan; shorts on Alpaca blocked) -> Backtester (results.json stats; losing
reference = warning) -> Validation Auditor (fresh bar, valid price) -> Risk Manager (kill switch, caps) -> CEO
(`ceo_decision` pending, then approved/rejected, same id). Wall screens get `strategy_result` per strategy family with the
reference stats plus a `paper` object (positions, fills, P&L, status); see services/live-events/README.md.

Known differences from the backtest: live fills are market orders after the bar closes (backtest: next bar open, stops
filled at the stop price); crypto uses $2,000 fixed notional instead of compounding equity; indicators warm up on 4,800
1h bars (200 4h-days) instead of the full 2018+ history; crypto bars come from Alpaca, not Bitstamp; first5m only enters
between 09:35 and 09:45 ET and is capped to floor($2,000 / price) shares (backtest: $200 risk, 4x leverage); the
position book is the runner's own (state.json), not reconciled with the broker on restart.

Stocks (2026-10-28): whole shares within the $2,000 cap (the backtests size by % of equity). Regular-session orders are market
orders; any stock order outside 09:30-16:00 ET is a whole-share LIMIT with extended hours, cancelled if it does not fill.
5m bars and quotes come from ALPACA_DATA_FEED (default iex; relative volume compares IEX with IEX), daily bars from sip
(completed days only). NYSE holidays / early closes are listed in strategies.py through 2027. Wall: one screen per active leg.
