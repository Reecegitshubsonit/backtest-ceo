# Backtest CEO: foundation design spec

Date: 2026-10-21. Status: draft for user review.

Backtest CEO is a visual backtesting system built the same way as Scalp City: a Python engine with a FastAPI
server, and a 3D React front end with HTML panels that carry every exact number. A CEO AI hologram stands on a
round strategy table; six agents sit around it; three computers behind the CEO open the Backtests, Scanner and
Strategies views. A live-trading version comes later, once strategies are chosen.

Visual reference: `docs/reference/grok-base.png` (layout) and `docs/reference/ceo-command.html` (look prototype).

## 1. Whole-project roadmap (each piece gets its own spec and plan)

1. Foundation (this spec): repo, engine skeleton, Alpaca data fetch, 3D room, computer panels, Backtests
   chart viewer with bar replay, dock launcher.
2. Strategies: rule definitions (discussed 2026-10-22), backtest runner, trades drawn on the chart.
3. Strategies computer: per asset class, every strategy tried with P&L, win rate, drawdown, trade count.
4. Scanner computer: scans per asset class.
5. Agents and CEO: talk to each agent, rules for what they do, reports routed to the CEO.
6. Live version.

## 2. Scope and hard rules (foundation)

- Asset classes: Stocks, ETFs, Crypto, Options. Futures are out (Alpaca has no futures data; user decision
  2026-10-21).
- All market data comes from Alpaca. Options history starts February 2024 and is bars only (no historical
  bid/ask), so any options result priced from bars is optimistic. The Options tab says so.
- Read-only. No code places orders. Keys come from `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` in the environment,
  never from the repo. No `.env` committed.
- Procedural geometry only. No downloaded models or textures.
- Separate project from Scalp City (`~/backtest-ceo`). Code from Scalp City is copied and adapted, not
  imported.
- Out of scope today: strategy rules, trade markers, scanner logic, strategy results, agent chat.

## 3. Repository layout

```
engine/                 Python 3.11
  backtestceo/
    config.py           ports, cache dir, asset-class definitions
    alpaca.py           bar fetcher for stocks, ETFs, crypto, options; disk cache; paging
    bars.py             Bar dataclass and response parsing
    server.py           FastAPI app
  tests/                pytest; HTTP mocked, no real Alpaca calls
  pyproject.toml
web3d/                  Vite, React 19, @react-three/fiber 9, drei 10, three 0.186 (Scalp City versions)
  src/
    config/seats.ts     six agent seats (data, not code)
    config/computers.ts three computers and their asset tabs
    scene/              Room, Table, Ceo, AgentSeat, Operator, ComputerWall, CameraRig
    panels/             ComputerPanel, AssetTabs, ChartView (ported drawChart + ZoomChart), ReplayBar
    model/              bars, indicators, replay clock, camera targets (pure, unit tested)
    net/api.ts          engine client
  scripts/mock_engine.mjs, launch.sh, stop.sh
backtest-ceo.desktop    dock launcher; icon in web3d/public
docs/
```

Ports: view 5175, engine 8020 (Scalp City uses 5174 and 8010).

## 4. Engine

`GET /health` returns `{ok, alpaca_keys_present}`.

`GET /bars?asset=stocks|etfs|crypto|options&symbol=&tf=1Min|5Min|15Min|1Hour|1Day&start=&end=` returns
`{symbol, asset, tf, bars: [{t, o, h, l, c, v}]}` with `t` in UTC ISO 8601.

- Stocks and ETFs: `/v2/stocks/{symbol}/bars` (same endpoint; the asset class only groups symbols in the UI).
- Crypto: `/v1beta3/crypto/us/bars`, symbols like `BTC/USD`; trades 24/7.
- Options: `/v1beta1/options/bars`, OCC contract symbol (for example `SPY261120C00600000`). Requests before
  2024-02-01 return a 400 with a plain message.
- Every response is cached on disk by (asset, symbol, tf, start, end); completed past days are never
  refetched. Paging follows `next_page_token`.
- Errors: missing keys, 4xx from Alpaca, empty result and network failure each map to a distinct error
  `code` with a plain-words `message`. The front end shows the message, never a blank chart.

## 5. The room (3D)

Matches the prototype look in the Grok layout:

- Dark circular room, blue palette, a few violet accents.
- Round table; the CEO, a blue particle hologram, stands full-body on top of it, with a light column and
  data rising through it. Label: CEO AI.
- Six agent seats around the table. Each agent is a blue particle figure seated in a chair, head tilted up
  toward the CEO, with a label and status line. Data streams arc from each agent to the CEO.

  | Seat | Job | Hands off to |
  |---|---|---|
  | Scanner | runs scans, surfaces candidate symbols | Strategist |
  | Strategist | writes and tunes strategy rules | Backtester |
  | Backtester | runs tests, produces results | Validation Auditor |
  | Validation Auditor | rejects overfit, lookahead, thin or optimistic results | CEO |
  | Regime Analyst | labels market conditions so results split by regime | Strategist, CEO |
  | Risk Manager | sizing, drawdown and kill rules; can veto | CEO |

  Seats live in `config/seats.ts`; an Execution seat is added for the live version.
- Behind the CEO, a curved wall of chart screens. Three of them are the computers, larger and labelled
  BACKTESTS, SCANNER, STRATEGIES; they glow on hover and are clickable. The rest are decorative.
- Foreground: a dark operator silhouette in a chair, back to the camera.
- Orbit camera with limits. Bloom off by default (additive glow instead), on with `?fx=high`, as in Scalp
  City.

### Click flow

1. Click a computer: the camera flies to face that screen (about 0.8 s, eased).
2. The computer's panel slides in over the canvas: tabs Stocks, ETFs, Crypto, Options.
3. Esc or the close button closes the panel and flies the camera back to the room view.
4. Reduced motion: no flight; the camera cuts and the panel opens.

Scanner and Strategies panels show the four tabs with a plain "comes next" state today.

## 6. Backtests computer: chart viewer

Per tab: symbol input (with a short default list: SPY, QQQ, IWM for ETFs; AAPL, NVDA, TSLA for stocks;
BTC/USD, ETH/USD for crypto; options take an OCC contract symbol), timeframe, date range, Load.

Chart, ported from Scalp City's canvas chart (`drawChart.ts`, `ZoomChart.tsx`):

- Candles, volume bars under the price, crosshair with the hovered bar's time, OHLC and volume.
- Zoom and pan as in Scalp City.
- Indicators as a list of switchable overlays: VWAP, EMA 9, EMA 21, EMA 50, ATR panel. The user expects to
  change indicators, so each indicator is one entry in a registry (name, colour, compute function); adding one
  touches only that registry.
- Scalp City's session-rule lines (RANGE arms, OR set, and so on) are removed; they belong to its bots.

Replay ("live backtest" view, no strategy yet): play, pause, step, speed 1x to 50x, and a scrubber. The chart
reveals bars one at a time up to the replay clock; indicators are computed only from revealed bars, so the
replay never shows the future. Trade markers arrive with piece 2.

## 7. Dock launcher

`backtest-ceo.desktop` in `~/.local/share/applications`, copied from Scalp City's pattern: `launch.sh` starts
the Vite server on 5175 if it is down, starts the engine on 8020 if it is down, opens Firefox. A Stop action
runs `stop.sh`. Icon: a simple CEO-hologram glyph SVG.

## 8. Testing

- Engine (pytest): parsing for each asset class, paging, cache hit and miss, the options date guard, each
  error code, `/bars` and `/health` through FastAPI's test client.
- Front end (vitest): indicator functions, replay clock (never reveals bars past the clock), camera targets,
  panel state machine (closed, flying, open, closing).
- Visual: screenshots in the browser pane at 1366 wide and at phone width; 60 fps check as in Scalp City.
- One manual end-to-end: launcher opens the app, click BACKTESTS, load SPY 5Min for one day from real Alpaca,
  play the replay.

## 9. Open items (not blocking this build)

- Strategy rules: 2026-10-22 session.
- Options contract picker (chain browser) instead of typing an OCC symbol: later piece.
- Agent behaviour and chat: piece 5.
