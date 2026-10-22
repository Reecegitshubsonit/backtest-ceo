# Backtest CEO

Visual backtesting system. A CEO AI hologram stands on a strategy table with six agents around it; the
computers behind it open the Backtests, Scanner and Strategies views. Read-only: nothing here places orders.

Asset classes: Stocks, ETFs, Crypto, Options (all data from Alpaca; options history starts 2024-02-01 and is
bars only, so options fills priced from bars are optimistic). No futures.

## Run

    engine/run.sh                    # engine on 127.0.0.1:8020 (keys from .env, else ~/scalp-city/.env)
    cd web3d && npm run dev          # view on http://localhost:5175
    cd web3d && npm run mock         # fake engine on 8020 for work without keys

Or use the dock launcher (Backtest CEO). Add `?fx=high` to the URL for bloom.

## Test

    cd engine && .venv/bin/pytest -q
    cd web3d && npx vitest run && npx tsc --noEmit

## Layout

- `engine/backtestceo`: Alpaca client (bars, options expirations and chains, disk cache in
  `~/.cache/backtest-ceo`), FastAPI server under `/api`.
- `web3d/src/scene`: the 3D room. `config/seats.ts` and `config/computers.ts` hold the agents and computers.
- `web3d/src/panels`: computer panel, backtest tab, options picker, canvas chart, replay bar.
- `web3d/src/model`: pure logic with unit tests. `model/indicators.ts` is the (empty) indicator registry.
- Specs and plans: `docs/superpowers/`.
