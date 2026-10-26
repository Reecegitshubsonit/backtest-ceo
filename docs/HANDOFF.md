# Backtest CEO: handoff (2026-10-22)

Project: `~/backtest-ceo` (git). Visual backtesting app in the style of `~/scalp-city` (separate project; code was copied, not imported). Read `README.md`, `docs/superpowers/specs/2026-10-21-backtest-ceo-foundation-design.md`, `docs/superpowers/plans/2026-10-21-backtest-ceo-foundation.md`.

## What exists
- **Engine** `engine/` (Python 3.11, FastAPI, port 8020, routes under `/api`): read-only Alpaca data for stocks, ETFs, crypto, options (options history from 2024-02-01, bars only). `/api/health`, `/api/bars`, `/api/options/expirations`, `/api/options/chain`. Disk cache `~/.cache/backtest-ceo`. Keys from env, else the `ALPACA_` lines of `~/scalp-city/.env` (`engine/run.sh`). No futures (user decision). Nothing places orders.
- **View** `web3d/` (Vite, React 19, R3F, port 5175). Default room = the user's Grok picture (`web3d/public/room.jpg`, cleaned from `docs/reference/grok-room-wide.jpg`, 1280x720, baked text painted out), shown whole at true proportions, our labels drawn on top (`src/room/ImageRoom.tsx`, coordinates in `src/config/imageRoom.ts`). `?room=3d` = older procedural 3D room (user rejected its look).
- **Screens**: 17 wall + 9 desk screens, all clickable, invisible until hover (glow + name). Click zooms in, opens panel; Esc zooms out. Wall 1 = BACKTESTS, 5 = SCANNER, 10 = STRATEGIES; other wall screens and desk 7-9 open "not assigned yet". Desk screens 1-6 = each agent's console (placeholder).
- **Backtests panel**: Stocks / ETFs / Crypto / Options tabs; load Alpaca bars; canvas chart (candles, volume, zoom, pan); replay (play, pause, step, 1x-50x, scrubber; never shows future bars). Options: underlying + day + expiration -> strike ladder centred on ATM -> contract chart plus underlying chart. Indicator registry `src/model/indicators.ts` is EMPTY on purpose: indicators get added with each strategy.
- **Agents (6 seats)**: Scanner Agent, Strategist, Backtester, Validation Auditor, Regime Analyst, Risk Manager (`src/config/seats.ts`). Execution seat comes with the live version.
- **Dock**: `~/.local/share/applications/backtest-ceo.desktop`, pinned after Scalp City; `web3d/scripts/launch.sh` starts engine + view, opens Firefox; `stop.sh` stops both.
- Tests: `cd engine && .venv/bin/pytest -q` (25), `cd web3d && npx vitest run && npx tsc --noEmit` (35).

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
- Inspect each piece visually before moving on; the room must look exactly like their picture (no outlines or added decoration on it).
- No image generation available; images come from the user via Grok, saved to `~/Downloads`.

## 2026-10-22: 3D attempt reverted (read before trying 3D again)
The user wants the exact Grok picture (`docs/reference/grok-room-wide.jpg`) in true 3D: free 360 spin like Scalp City,
every screen clickable (each agent's whole screen), sharp when zoomed in. The picture view is grainy when zoomed
because the room is a 1280x720 image.
- Tried: procedural 3D room built from `src/scene/*` primitives (box chairs, particle figures). Rejected twice
  (2026-10-21 and 2026-10-22) because it looks nothing like the picture. Do not reuse those parts for the look.
- The user wants every object to match the picture: CEO hologram, six seated agents, chairs, round desk with
  built-in screens, wall monitors, the dark silhouette in the foreground.
- Parts of the attempt that worked and can be reused (see the reverted commits 53afa46, e471b31, 8206e7c, and
  `docs/superpowers/specs|plans/2026-10-22-3d-room-orbit*`): 3D layout of all 26 screens, camera fly-in that
  squares up to a screen, live DOM preview on the focused screen via drei `<Html transform>` at 1:1 scale (sharp),
  expand to a full panel that keeps state by moving the DOM node, Esc stepping back one level.
- Not tried: real 3D models (GLB) of each object, or image-to-3D models made from crops of the picture.
  This machine has no NVIDIA GPU.

## CEO model review started (2026-10-22)
- `?review=ceo` opens a side-by-side comparison of the original reference and a real human GLB with hologram shading. Default room stays unchanged.
- Source: Blender Studio Human Base Meshes v1.4.1 (CC0), realistic male body and eyes. Provenance and reproduction: `docs/ceo-model-source.md`, `web3d/scripts/export-ceo.py`.
- Only the CEO is under review. Get the user's visual approval before moving to another object or replacing the default room. No approval has been received yet. The full 3D room and sharp screen integration remain unfinished.

## CEO likeness revision (2026-10-22)
- User rejected the first stock GLB: it looked unlike the original CEO, and the comparison was too small. The user wants us to do the work, not ask them to run cloud tools.
- Revised `?review=ceo`: portrait detail comparison by default, reference-fitted GLB silhouette, original cleaned artwork projected as front UV texture, inferred sides/back with cyan rim/network shading. Normal blending and depth writes replace additive anatomy that exposed eye sockets and mouth edges.
- `web3d/scripts/fit-ceo-reference.mjs` is the second reproducible export stage; see `docs/ceo-model-source.md`. Original front appearance is preserved with image-based texturing; unseen-side likeness remains inferred. This is not a complete image-to-3D reconstruction.
- Still only the CEO. Projector beam, room, table, chairs and screens have not been rebuilt. User approval has not yet been received.

## Full 3D room implemented (2026-10-26; supersedes the review-only status above)
- The user explicitly requested completing the whole room without further interim responses/checkpoints.
- Default route now renders `src/room3d/FullRoomApp.tsx`, a complete 72-object GLB scene,
  including CEO, six posed agents, seven real office chairs, operator silhouette, recessed
  round command desk/projector insert, architectural shell and all 26 physical screens.
  None of the rejected `src/scene` furniture or particle anatomy is used.
- Reference-camera projection preserves the supplied artwork at home. Away from home,
  depth/semantic masks remove projected foreground ghosts; physical mesh materials,
  high-resolution chart textures and desk texture fill unseen areas. This is a reference-
  fitted reconstruction, not recovered ground-truth geometry of the unseen room.
- Full 360 orbit has floor/ceiling/wall camera bounds; reset returns to the calibrated view.
  Wall 1/5/10 and all six agent console mappings retain their canonical ids. Entire screen
  faces receive clicks; labels/glow appear on hover. The Screens menu also exposes all 26.
- Screen flight squares the camera to the face, shows sharp live DOM at approximately 1:1,
  expands by moving the same DOM host, and retains input state on Esc back to focused mode.
- `?room=image` is the former flat room; `?review=ceo` remains for historical comparison.
- Tests: engine 25, frontend 45, TypeScript and production build pass.
- Firefox headless was also checked: full WebGL scene loaded, 26 screen entries and sharp
  live focused BACKTESTS DOM verified; screenshot inspected. Expand/return retained a changed
  symbol in the in-app browser. A regression test checks desk faces are above the furniture.
- Sources/build recipe/limitations: `docs/reference-room-3d.md`.
