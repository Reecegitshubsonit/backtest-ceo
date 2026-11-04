"""Turn markets + hourly candles into a decision table.

One row per (market, h) where h = hours before close at which we decide. Features use only candles that ended
at or before the decision time. Entry is a taker buy at the ask of the chosen side; every exit is simulated in
advance on the later hourly quotes (still top-of-book only: no depth history exists):
  side 0 = YES (pay yes_ask, later sell at yes_bid), side 1 = NO (pay 1 - yes_bid, later sell at 1 - yes_ask)
  exits: hold to settlement, or take-profit / stop-loss on the side's bid, checked on each later hourly close
  sizes: 1, 10, 50 contracts (Kalshi taker fee is rounded up per order, so size changes cost)
Fees: ceil-to-cent(0.07 * C * P * (1-P)) on every taker fill; no fee at settlement.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

H = [1, 3, 6, 12, 24, 48, 96, 168]
EXITS = [(None, None), (0.10, 0.10), (0.20, 0.10), (0.05, 0.05)]  # (take profit, stop loss) in $ per contract
SIZES = [1, 10, 50]
STALE_S = 3 * 3600  # a quote older than this at decision time is not tradeable


def fee(c: int, p: float) -> float:
    return math.ceil(round(0.07 * c * p * (1 - p) * 100, 6)) / 100


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def quote_at(cs, t):
    """Last valid (bid, ask) at or before t, not older than STALE_S."""
    best = None
    for ts, b, a, _ in cs:
        if ts > t:
            break
        if b is not None and a is not None and 0 < b < a < 1:
            best = (ts, b, a)
    if best and t - best[0] <= STALE_S:
        return best[1], best[2]
    return None


def simulate(cs, t, close, side, entry, tp, sl, won) -> float:
    """Exit price per contract for one position (settlement payout if never stopped)."""
    if tp is not None:
        for ts, b, a, _ in cs:
            if ts <= t or ts >= close:
                continue
            if b is None or a is None or not 0 < b < a < 1:
                continue
            bid = b if side == 0 else 1 - a
            if bid <= entry - sl:  # stop first when both trigger in one hour (conservative)
                return -bid
            if bid >= entry + tp:
                return -bid
    return 1.0 if won else 0.0


def build(data_dir: Path, out: Path, log=print) -> dict:
    cats = json.loads((data_dir / "series.json").read_text())
    markets = {json.loads(l)["ticker"]: json.loads(l) for l in (data_dir / "markets.jsonl").open()}
    cat_names = sorted(set(cats.values()) | {"Other"})
    cat_idx = {c: i for i, c in enumerate(cat_names)}
    ev_idx: dict[str, int] = {}
    cols = {k: [] for k in ("h", "cat", "event", "close", "mid", "spread", "ask_yes", "ask_no", "vol24", "mom6", "mom24")}
    rets = []
    n_mk = 0
    for line in (data_dir / "candles.jsonl").open():
        rec = json.loads(line)
        m = markets.get(rec["t"])
        cs = [c for c in rec["c"] if c[0] is not None]
        if not m or len(cs) < 2:
            continue
        cs.sort(key=lambda c: c[0])
        close = _ts(m["close_time"])
        won_yes = m["result"] == "yes"
        cat = cat_idx.get(cats.get(m["ticker"].split("-")[0], "Other"), cat_idx["Other"])
        ev = ev_idx.setdefault(m["event_ticker"], len(ev_idx))
        used = False
        for hi, h in enumerate(H):
            t = close - h * 3600
            q = quote_at(cs, t)
            if not q:
                continue
            b, a = q
            mid = (b + a) / 2
            def mom(lag):
                q0 = quote_at(cs, t - lag * 3600)
                return mid - (q0[0] + q0[1]) / 2 if q0 else np.nan
            vol24 = sum(v for ts, _, _, v in cs if t - 86400 < ts <= t)
            r = np.full((2, len(EXITS), len(SIZES)), np.nan, dtype=np.float32)
            for side in (0, 1):
                entry = a if side == 0 else round(1 - b, 4)
                won = won_yes if side == 0 else not won_yes
                for ei, (tp, sl) in enumerate(EXITS):
                    x = simulate(cs, t, close, side, entry, tp, sl, won)
                    early, px = x < 0, abs(x)
                    for si, c in enumerate(SIZES):
                        cost = c * entry + fee(c, entry)
                        proceeds = c * px - (fee(c, px) if early else 0.0)
                        r[side, ei, si] = (proceeds - cost) / cost
            for k, v in (("h", hi), ("cat", cat), ("event", ev), ("close", close), ("mid", mid), ("spread", a - b),
                         ("ask_yes", a), ("ask_no", 1 - b), ("vol24", vol24), ("mom6", mom(6)), ("mom24", mom(24))):
                cols[k].append(v)
            rets.append(r)
            used = True
        n_mk += used
    arrays = {k: np.asarray(v) for k, v in cols.items()}
    arrays["ret"] = np.stack(rets) if rets else np.zeros((0, 2, len(EXITS), len(SIZES)), np.float32)
    np.savez_compressed(out, **arrays, cat_names=np.array(cat_names))
    log(f"decision rows: {len(rets)} from {n_mk} markets, {len(ev_idx)} events")
    return {"rows": len(rets), "markets": n_mk, "events": len(ev_idx)}
