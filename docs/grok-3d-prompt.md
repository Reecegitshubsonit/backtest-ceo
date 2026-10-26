# Prompt for Grok: Backtest CEO 3D room, strategies and agents

Copy everything below the line into Grok.

---

You are helping build **Backtest CEO**, a visual backtesting app. I need you to build (or improve) the **3D room**
and to design how **strategies** and the **agent bots** plug into it. Read the whole brief before answering.
Ask me questions in one batch before writing code if anything is unclear. Challenge my decisions if you see a
better way; give a confidence level on contested points.

## 1. What the app is

A dark, circular "command room". A **CEO AI hologram** stands in a light beam on a round strategy desk. **Six AI
agents** sit in office chairs around the desk, each with its own console screen built into the desk. A curved wall
of **17 monitors** stands behind the CEO. A dark **operator silhouette** (me) sits in a chair in the foreground,
back to the camera. The look must match my reference picture (the Grok render I made: blue/navy palette,
purple and cyan light strips on floor and ceiling, glossy floor, cyan hologram glow, chart screens everywhere).

The app is **read-only**: it never places orders. A live-trading version comes later.

Asset classes: **Stocks, ETFs, Crypto, Options.** No futures. All data comes from **Alpaca**. Options history
starts 2024-02-01 and is bars only (no historical bid/ask), so options fills priced from bars are optimistic and
the UI must say so.

## 2. Existing stack (build on it, do not replace it)

- Engine: Python 3.11, FastAPI on `127.0.0.1:8020`, routes under `/api`:
  - `GET /api/health` -> `{ok, alpaca_keys_present}`
  - `GET /api/bars?asset=stocks|etfs|crypto|options&symbol=&tf=1Min|5Min|15Min|1Hour|1Day&start=&end=`
    -> `{symbol, asset, tf, bars: [{t, o, h, l, c, v}]}`
  - `GET /api/options/expirations?underlying=&on=YYYY-MM-DD`
  - `GET /api/options/chain?underlying=&expiration=&on=`
  - Disk cache in `~/.cache/backtest-ceo`. A bulk collector also writes gzipped CSV history to
    `data/{stocks,etfs,crypto,options}` (equities from 2016, crypto from 2021, intraday for SPY, QQQ, IWM, DIA,
    AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AMD, BTC/USD, ETH/USD, SOL/USD; options for the big underlyings).
- Front end: Vite, React 19, `@react-three/fiber` 9, `@react-three/drei` 10, `three` 0.186, TypeScript, port 5175.
- Tests: vitest for the front end, pytest for the engine. Keep pure logic in testable modules.

## 3. The 3D room: requirements

1. **Real 3D, not a flat picture.** Full 360-degree orbit (drag), scroll zoom toward the mouse pointer,
   right-drag pan. Camera and target stay inside the room (above the floor, below the ceiling, inside the walls).
   A "Reset view" button returns to the home framing that matches the reference picture
   (camera `[0, 3.844, 7.04]`, target `[0, 3.3, 0]`, FOV 48).
2. **Every object matches the reference**: CEO hologram (realistic human body, cyan glow, front likeness of the
   reference, lower body fades), six seated agents in real office chairs, palms on the desk, heads tilted toward
   the CEO; genuinely circular desk with a central projector ring and beam; curved monitor wall; operator
   silhouette in a chair. Use real meshes (GLB) with correct proportions. No primitive box chairs, no particle
   bodies, no stretched or warped figures. Materials must stay the same at every camera angle (no fading
   between a photo and a different surface as the camera moves).
3. **26 clickable screens**, all with stable ids:
   - Wall (left to right, top to bottom): `s1`..`s17`. `s1` = **BACKTESTS**, `s5` = **SCANNER**,
     `s10` = **STRATEGIES**. The rest are unassigned for now (show "not assigned yet").
   - Desk: `d-scanner`, `d-strategist`, `d-backtester`, `d-auditor`, `d-regime`, `d-risk` (one landscape
     console in front of each agent, tilted up toward it) and `d7`, `d8`, `d9` on the front edge (unassigned).
   - At rest: no outlines, tags or decoration drawn over the screens. On hover: the screen glows and shows its name.
     The whole screen face is the click target.
4. **Screen flight and sharpness**: clicking a screen flies the camera (about 0.8 s, eased) square to the screen,
   upright, matching the screen's up direction (desk consoles are rotated). The focused screen then shows a
   **live, sharp HTML panel** at about 1:1 pixel scale (drei `<Html transform>`), never a magnified texture.
   An Expand button (or double-click) opens the same panel full-screen by moving the same DOM node, so state is
   kept. **Esc** steps back one level: full-screen -> focused screen -> room, restoring the saved camera.
   With reduced motion, cut instead of fly.
5. Idle screens show crisp chart textures (2048 px canvas, mipmaps, anisotropic filtering).
6. Performance: 60 fps target on a machine with **no NVIDIA GPU**. Bloom off by default (`?fx=low`
   disables it), additive glow instead.
7. Agent status: each agent shows its name and a one-line status (for example "Running tests"). Data streams arc
   from each agent's chest to the CEO when that agent reports.

## 4. What each bot does

| Agent | Job | Hands work to | Desk console shows |
|---|---|---|---|
| **Scanner Agent** | Runs scans per asset class, surfaces candidate symbols | Strategist | Current scan, hit list, why each symbol passed |
| **Strategist** | Writes and tunes strategy rules (entry, exit, stop, timeframe, asset classes) | Backtester | Strategy being edited, its rules and parameters |
| **Backtester** | Runs the tests, produces trades and results | Validation Auditor | Run progress, trades, P&L curve |
| **Validation Auditor** | Rejects overfit, lookahead, thin samples and optimistic fills (for example options priced from bars) | CEO | Pass/fail checklist with the reason for each fail |
| **Regime Analyst** | Labels market conditions (trend, range, high/low volatility) so results split by regime | Strategist, CEO | Current regime and results per regime |
| **Risk Manager** | Position sizing, drawdown limits, kill rules; **can veto** any strategy | CEO | Limits, current exposure, vetoes |
| **CEO AI** | Takes the reports, ranks strategies, decides which go forward; answers my questions | Me | The table summary in the centre |

The pipeline is: Scanner -> Strategist -> Backtester -> Validation Auditor -> CEO, with the Regime Analyst feeding
the Strategist and CEO, and the Risk Manager able to veto at the CEO. An **Execution** seat is added only in the
live version. Seats are data (`config/seats.ts`: id, name, job, angle), not hard-coded scenes.

Later, I will talk to each agent from its desk console; reports route to the CEO. For now the consoles can show
placeholders, but design the panel so a chat box and a report feed fit.

## 5. How strategies plug in

The strategy rules are not final yet. Design the plug-in point so adding a strategy touches one place:

- A **strategy definition** is data plus pure functions: name, asset classes, timeframe, its own indicators,
  entry rule, exit rule, stop rule, sizing hook (from the Risk Manager).
- **Indicators belong to strategies.** There is a chart indicator registry (name, colour, compute function,
  overlay or lower pane) that ships empty. Each strategy registers the indicators it needs.
- **No lookahead**: indicators and rules see only bars up to the current replay clock. The Backtests chart already
  has a replay (play, pause, step, 1x to 50x, scrubber) that never reveals future bars; strategy signals and trade
  markers (entry, exit, stop) must be drawn on that same chart in step with the replay.
- **Backtest runner** (engine side, Python): takes a strategy and a symbol/date range, returns trades and stats
  (P&L, win rate, max drawdown, trade count, results per regime). Options fills priced from bars are flagged
  optimistic.
- **STRATEGIES computer** (`s10`): per asset class tab, a table of every strategy tried with P&L, win rate,
  drawdown, trade count, the Auditor's verdict and the Risk Manager's veto state. Clicking a row opens the
  trades on the Backtests chart.
- **SCANNER computer** (`s5`): per asset class tab, scan definitions and today's hits; hits can be sent to the
  Strategist.
- **BACKTESTS computer** (`s1`): already exists. Stocks / ETFs / Crypto / Options tabs, candle chart with volume,
  zoom, pan, replay; Options tab has a chain picker (underlying, day, expiration, strike ladder centred on ATM).

## 6. Hard rules

- Never place orders. No API keys in the repo; keys come from the environment.
- Keep the 26 screen ids and the three computer assignments exactly as listed.
- Do not add outlines, labels or decoration over the room at rest.
- Every number shown comes from the engine; the 3D scene is for navigation, the HTML panels carry the exact numbers.
- Show a plain-words message on errors, never a blank chart.

## 7. What I want back from you

1. Questions, in one batch, if anything blocks you.
2. Your critique of this plan: the weakest part and what you would change.
3. The 3D room architecture: file list, scene graph, how you get each model (source, licence, how you fit it to
   the reference), camera rig, screen focus/expand state machine.
4. The strategy plug-in interface (TypeScript types and the Python runner signature) and how trades reach the chart.
5. The agent data model and how reports flow to the CEO and to each desk console.
6. Code, in small pieces I can test one at a time, starting with the room.
