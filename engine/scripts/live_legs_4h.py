"""Paper runner's 4h crypto legs (SuperTrend confluence, EMA200+ADX25) on all Alpaca 1h history since 2021, 4h built
exactly as the runner does. Live runs long side only (Alpaca cannot short); L/S shown for reference.
Cost 0.30%/side, next-bar-open fills (replay_bars). Run: python engine/scripts/live_legs_4h.py [--out file.md]"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from crypto_edge_backtest import fetch  # noqa: E402
from crypto_edge_round2 import metrics, to_bars, trade_daily  # noqa: E402
from backtestceo.paper.strategies import SIGNALS, replay_bars, resample  # noqa: E402

SIDE = 0.003


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--end", default=None, help="last full UTC day YYYY-MM-DD (default: yesterday)")
    a = ap.parse_args()
    cache = HERE.parent / ".cache" / "crypto_edge"
    cache.mkdir(parents=True, exist_ok=True)
    end = (datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) + timedelta(days=1) if a.end else
           datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)) - timedelta(seconds=1)
    rows = []
    for sym in ("BTC/USD", "ETH/USD", "SOL/USD"):
        h1 = fetch(sym, "1Hour", datetime(2021, 1, 1, tzinfo=timezone.utc), end, cache)
        bars = resample(to_bars(h1), 4)
        dd = pd.Series([b["c"] for b in bars], index=pd.DatetimeIndex([b["ts"] for b in bars]))
        # data holes > 2 days (Alpaca SOL/USD 2023-06 -> 2024-08): drop trades held across them
        ts = dd.index.to_series()
        holes = [(a, b) for a, b in zip(ts.shift().dropna(), ts.iloc[1:]) if b - a > pd.Timedelta(days=2)]
        for rule in ("supertrend", "alphainsider"):
            for mode in ("long only (live)", "L/S"):
                sig = SIGNALS[rule](bars)
                if mode.startswith("long"):
                    sig = dict(sig, se=[False] * len(bars))
                tl = [x for x in replay_bars(bars, sig)
                      if not any(x["entry_time"] <= ha and x["exit_time"] >= hb for ha, hb in holes)]
                for per, st in (("2021+", pd.Timestamp("2021-03-01", tz="UTC")), ("last 2y", pd.Timestamp(end) - pd.Timedelta(days=730))):
                    t = [x for x in tl if x["entry_time"] >= st]
                    net = [((x["exit"] / x["entry"] - 1) if x["side"] == "long" else (1 - x["exit"] / x["entry"])) - 2 * SIDE for x in t]
                    daily = trade_daily(t, [b for b in bars if b["ts"] >= st - timedelta(hours=4)], SIDE, st)
                    b = dd[dd.index >= st]
                    bh = (b.resample("1D").last().pct_change().dropna())
                    m = metrics(net, daily)
                    rows.append({"leg": f"{rule} 4h", "mode": mode, "symbol": sym, "period": per, **m,
                                 "gross exp%": m["exp%"] + 200 * SIDE if len(net) else np.nan,
                                 "B&H sharpe": bh.mean() / bh.std() * np.sqrt(365), "B&H maxDD%": 100 * ((1 + bh).cumprod() / (1 + bh).cumprod().cummax() - 1).min(),
                                 "status": "ok" if m["trades"] >= 30 else "REJECT (<30)"})
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(R.round(2).to_string(index=False))
    if a.out:
        r = R.round(2).astype(object).where(R.notna(), "")
        cols = list(R.columns)
        Path(a.out).write_text("\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] +
                                         ["| " + " | ".join(str(v) for v in x) + " |" for x in r.values]) + "\n")


if __name__ == "__main__":
    main()
