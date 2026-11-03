"""Scan (read-only) and paper-trading cycle."""
from __future__ import annotations

import time
from pathlib import Path

from .client import KalshiClient, KalshiError
from .model import (Config, Quote, count, hours_to_close, load_calibration, make_quote, now_utc,
                    parse_book, prefilter, price)
from .paper import Journal, State, apply_trades, cancel, place, settle


def candidates(client: KalshiClient, cfg: Config, max_books: int = 150):
    now = now_utc()
    ts = int(now.timestamp())
    markets = client.markets(status="open", mve_filter="exclude",
                             min_close_ts=ts + int(cfg.min_hours_to_close * 3600),
                             max_close_ts=ts + int(cfg.max_hours_to_close * 3600))
    picked = []
    for m in markets:
        side = prefilter(m, cfg, now)
        if side:
            picked.append((m, side))
    picked.sort(key=lambda ms: -count(ms[0], "volume_24h"))
    return picked[:max_books]


def scan(client: KalshiClient, cfg: Config, bankroll: float | None = None, max_books: int = 150) -> list[Quote]:
    table = load_calibration(cfg.calibration_path)
    bankroll = bankroll or cfg.starting_cash
    out = []
    for m, side in candidates(client, cfg, max_books):
        book = parse_book(client.orderbook(m["ticker"]))
        q = make_quote(m, book, side, cfg, table, bankroll, cfg.max_per_market, cfg.max_per_event, cfg.max_total_exposure)
        if q:
            out.append(q)
    return sorted(out, key=lambda q: -q.edge)


def paper_cycle(client: KalshiClient, cfg: Config, state_path: Path, journal_path: Path,
                max_books: int = 150, verbose: bool = True) -> State:
    cfg_table = load_calibration(cfg.calibration_path)
    state = State.load(state_path, cfg.starting_cash)
    log = Journal(journal_path)
    now = now_utc()
    now_ts = int(now.timestamp())

    # 1. fills from the public tape, then settlement / expiry of anything we hold or rest on
    for ticker in sorted({o.ticker for o in state.orders.values()}):
        trades = client.trades(ticker=ticker, min_ts=state.last_trade_ts.get(ticker))
        apply_trades(state, ticker, trades, cfg.maker_fee_rate, log)
    for ticker in sorted(set(state.positions) | {o.ticker for o in state.orders.values()}):
        try:
            m = client.market(ticker)
        except KalshiError as e:
            log("error", ts=now_ts, ticker=ticker, err=str(e))
            continue
        settle(state, m, now_ts, log)
        h = hours_to_close(m, now)
        if h is not None and h < cfg.min_hours_to_close:
            for oid in [k for k, o in state.orders.items() if o.ticker == ticker]:
                cancel(state, oid, now_ts, log, "near_close")

    # 2. requote: equity = cash + position cost (held to settlement, so marked at cost)
    bankroll = state.cash + sum(p.cost for p in state.positions.values())
    by_ticker = {o.ticker: o for o in state.orders.values()}
    wanted = set()
    for m, side in candidates(client, cfg, max_books):
        t = m["ticker"]
        book = parse_book(client.orderbook(t))
        existing = by_ticker.get(t)
        mine = existing.remaining * existing.price if existing else 0.0
        q = make_quote(
            m, book, side, cfg, cfg_table, bankroll,
            room_market=cfg.max_per_market - state.exposure(ticker=t) + mine,
            room_event=cfg.max_per_event - state.exposure(event=m.get("event_ticker")) + mine,
            room_total=cfg.max_total_exposure - state.exposure() + mine,
        )
        if q is None:
            continue
        wanted.add(t)
        if existing and existing.side == q.side and abs(existing.price - q.price) < 1e-9:
            continue  # keep queue priority
        if existing:  # paper orders are not in the real book, so book size at q.price is all ahead of us
            cancel(state, existing.id, now_ts, log, "requote")
        place(state, q, now_ts, log)
    for o in list(state.orders.values()):
        if o.ticker not in wanted and o.ticker in by_ticker:
            cancel(state, o.id, now_ts, log, "no_edge")

    state.save(state_path)
    if verbose:
        print(summary(state))
    return state


def summary(state: State) -> str:
    held = sum(p.cost for p in state.positions.values())
    return (f"cash ${state.cash:,.2f} | resting {len(state.orders)} orders (${state.reserved():,.2f}) | "
            f"{len(state.positions)} positions (cost ${held:,.2f}) | realized ${state.realized:+,.2f} "
            f"| W/L {state.wins}/{state.losses}")


def run_forever(client, cfg, state_path, journal_path, interval: int, max_books: int) -> None:
    while True:
        try:
            paper_cycle(client, cfg, state_path, journal_path, max_books)
        except Exception as e:  # keep the loop alive; the journal records the error
            Journal(journal_path)("error", ts=int(time.time()), err=repr(e))
            print("cycle error:", e)
        time.sleep(interval)


__all__ = ["scan", "paper_cycle", "run_forever", "summary", "price"]
