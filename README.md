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

The default view is the full 3D reference room: drag to orbit, scroll to zoom, click any
of the 26 screens to fly to a sharp live panel. Expand keeps the panel state; Esc returns
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
