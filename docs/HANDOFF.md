# Backtest CEO: handoff (2026-10-22)

Project: `~/backtest-ceo` (git). Visual backtesting app in the style of `~/scalp-city` (separate project; code was copied, not imported). Read `README.md`, `docs/superpowers/specs/2026-10-21-backtest-ceo-foundation-design.md`, `docs/superpowers/plans/2026-10-21-backtest-ceo-foundation.md`.

## What exists
- **Engine** `engine/` (Python 3.11, FastAPI, port 8020, routes under `/api`): read-only Alpaca data for stocks, ETFs, crypto, options (options history from 2024-02-01, bars only). `/api/health`, `/api/bars`, `/api/options/expirations`, `/api/options/chain`. Disk cache `~/.cache/backtest-ceo`. Keys from env, else the `ALPACA_` lines of `~/scalp-city/.env` (`engine/run.sh`). No futures (user decision). Nothing places orders.
- **View** `web3d/` (Vite, React 19, R3F, port 5175). The room is real 3D (since 2026-10-22; the flat Grok picture view is gone, the cleaned picture is `docs/reference/grok-room-clean.jpg`). OrbitControls: full 360 spin, zoom to cursor, auto-rotate after 6 s idle, camera kept inside the room (`Scene.tsx`, `Orbiting`). ⟲ Reset view in the hint bar. Spec `docs/superpowers/specs/2026-10-22-3d-room-orbit-design.md`, plan `docs/superpowers/plans/2026-10-22-3d-room-orbit.md`.
- **Screens**: 17 wall + 9 table screens, all clickable, layout in `src/config/screens3d.ts` (wall positions derived from the picture's layout). Hover = glow + name tag. Click flies the camera square to the screen (`flyPose` in `src/model/camera.ts`) and the screen's view runs there as real DOM through drei `<Html transform>` at about 1:1 scale, so it is sharp. ⤢ Expand or double-click the title bar opens the full panel; the same DOM node moves (`panels/Slot.tsx`), so a loaded chart survives. Esc steps back: panel -> screen -> room. States: `closed -> flying -> focused -> expanded`, `closing` (`src/model/panel.ts`). Wall 1 = BACKTESTS, 5 = SCANNER, 10 = STRATEGIES; other wall screens and desk 7-9 show "not assigned yet". Table screens 1-6 = each agent's console (placeholder), tilted 35 degrees toward the agent; desk 8 shows the executive summary at rest.
- **Backtests panel**: Stocks / ETFs / Crypto / Options tabs; load Alpaca bars; canvas chart (candles, volume, zoom, pan); replay (play, pause, step, 1x-50x, scrubber; never shows future bars). Options: underlying + day + expiration -> strike ladder centred on ATM -> contract chart plus underlying chart. Indicator registry `src/model/indicators.ts` is EMPTY on purpose: indicators get added with each strategy.
- **Agents (6 seats)**: Scanner Agent, Strategist, Backtester, Validation Auditor, Regime Analyst, Risk Manager (`src/config/seats.ts`). Execution seat comes with the live version.
- **Dock**: `~/.local/share/applications/backtest-ceo.desktop`, pinned after Scalp City; `web3d/scripts/launch.sh` starts engine + view, opens Firefox; `stop.sh` stops both.
- Tests: `cd engine && .venv/bin/pytest -q` (25), `cd web3d && npx vitest run && npx tsc --noEmit` (39).

## Roadmap
1. Foundation: done.
2. **Strategies (next)**: user gives the rules (entry, exit, stop, timeframe, asset classes); build a backtest runner, trades drawn on the chart, each strategy's own indicators in the registry.
3. Strategies computer: per asset class, every strategy tried with P&L, win rate, drawdown, trade count.
4. Scanner computer.
5. Agents + CEO: talk to each agent from its desk console, rules, reports routed to the CEO.
6. Live version.
Open: what each unassigned screen shows; stock charts include extended hours (offer a regular-hours toggle).

## How the user works
- Wants to be challenged, not agreed with; give confidence on contested points.
- Batch several questions per message to save tokens.
- Inspect each piece visually before moving on. The room should resemble their Grok picture (accepted: a 3D room cannot copy it pixel for pixel); no outlines or tags on screens at rest.
- Open: room look still needs review rounds against the picture.
- No image generation available; images come from the user via Grok, saved to `~/Downloads`.
