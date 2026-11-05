# Backtest CEO

Visual backtesting system. A CEO AI hologram stands on a strategy table with six agents around it; the
computers behind it open the Backtests, Scanner and Strategies views. Read-only: nothing here places orders.

Asset classes: Stocks, ETFs, Crypto, Options (all data from Alpaca; options history starts 2024-02-01 and is
bars only, so options fills priced from bars are optimistic). No futures.

## Run

    engine/run.sh                    # engine on 127.0.0.1:8020 (keys from .env, else ~/scalp-city/.env)
    cd web3d && npm run dev          # view on http://localhost:5175
    cd web3d && npm run mock         # fake engine on 8020 for work without keys

Or use `web3d/scripts/launch.sh` or the dock launcher (Backtest CEO).

The default view is the full 3D reference room: drag to orbit, scroll toward the pointer, right-drag to pan, click any
of the 26 logical screens (also mirrored on the rear monitor bank) to fly to a sharp live panel. Expand keeps the panel state; Esc returns
one level. Reset view restores the reference framing. `?fx=low` disables bloom.
`?room=image` keeps the previous flat image for comparison; `?review=ceo` is the earlier
isolated CEO review. Model sources and reproduction: [3D room](docs/reference-room-3d.md).

## Test

    cd engine && .venv/bin/pytest -q
    cd web3d && npx vitest run && npx tsc --noEmit

## Layout

- `engine/backtestceo`: Alpaca client (bars, options expirations and chains, disk cache in
  `~/.cache/backtest-ceo`), FastAPI server under `/api`.
- `web3d/src/room3d`: current GLB room, reference projection, hologram/beam materials,
  bounded orbit, camera flights and live screen previews. `config/imageRoom.ts` remains
  the canonical screen mapping; generated geometry lives in `config/roomScreens.ts`.
- `web3d/public/models/reference-room.glb`: detailed furniture, posed figures, architecture
  and screen meshes. `src/scene` is the rejected older procedural scene, no longer routed.
- `web3d/src/panels`: computer panel, backtest tab, options picker, canvas chart, replay bar.
- `web3d/src/model`: pure logic with unit tests. `model/indicators.ts` is the (empty) indicator registry.
- Specs and plans: `docs/superpowers/`.

## Small-cap momentum (Cameron-style)

Gap / relative-volume / news scanner, bull flag / micro pullback / first pullback entries on 1-minute bars, 60-day
backtest and an Alpaca paper trading loop: [engine/backtestceo/momentum/README.md](engine/backtestceo/momentum/README.md).
Backtest outputs in `docs/momentum-backtest/`. Result: no edge on 1- or 5-minute bars, confirmed on a separate 60-session holdout.

**10-year parameter search** (124,416 long momentum variants, 2016–2026, spread model, 60/20/20 time split,
Reality Check, deflated Sharpe, shuffled benchmark): nothing survived; all 10 finalists lost on the holdout.
[engine/backtestceo/momentum/SEARCH.md](engine/backtestceo/momentum/SEARCH.md).

**Gapper Fade** (the strategy that tests well): short gappers ≥30% at 09:35, +50% disaster stop, cover 15:55.
Positive in 3 of 3 separate 60-session periods of 2026 (+$5.7k / +$8.7k / +$3.9k at $1k per position, 5 max).
Alpaca paper trader included. Read the borrow caveat first:
[engine/backtestceo/momentum/FADE.md](engine/backtestceo/momentum/FADE.md).

## Options execution research

The three-month VWAP/EMA study has a separate quote-based options replay:

    cd engine
    .venv/bin/python -m backtestceo.options_backtest   # raw underlying + option trade-bar preparation/stress model
    .venv/bin/python -m backtestceo.databento_quotes   # estimates selected NBBO requests; refuses estimate > $5
    .venv/bin/python -m backtestceo.quote_backtest     # real one-second NBBO, simulated marketable fills

Outputs are under `data/backtests/options-vwap-ema-3m-20260724-20261023/`. No orders are placed.
Databento access uses an existing key; no subscription is created. See `docs/options-data-readiness.md`
for entitlements, data limitations and the difference between trade-bar models and quote replay.
