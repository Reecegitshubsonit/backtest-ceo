"""Bid/ask half-spread model from Alpaca option snapshots (latest quotes, 'indicative' feed - the only feed this
account can read; OPRA agreement not signed). Historical option quotes do not exist on Alpaca, so this current
cross-section is applied to all history. Uses the 75th percentile half-spread per (symbol, DTE bucket, price bin):
conservative on purpose.

    python3 -m backtestceo.osearch.calibrate      -> data/osearch/spread.json + docs table
"""
import json
from collections import defaultdict
from datetime import date

import numpy as np

from . import data as D

BINS = [0, 0.10, 0.25, 0.50, 1, 2, 5, 10, 25, 1e9]


def bucket(dte): return 0 if dte <= 0 else 1 if dte <= 3 else 7 if dte <= 14 else 30


def main():
    today = date(2026, 11, 3)
    spot = {s: D.load_json(D.DIR / f"und/{s}-1d-raw.json")[-1]["c"] for s in D.SYMBOLS}
    obs = defaultdict(list)
    for s in D.SYMBOLS:
        tok = None; n = 0
        while True:
            p = dict(feed="indicative", limit=1000, expiration_date_lte="2026-12-31",
                     strike_price_gte=round(spot[s] * 0.85, 2), strike_price_lte=round(spot[s] * 1.15, 2))
            if tok: p["page_token"] = tok
            b = D.get(f"{D.DATA}/v1beta1/options/snapshots/{s}", p)
            for sym, snap in (b.get("snapshots") or {}).items():
                q = snap.get("latestQuote") or {}
                ap, bp = q.get("ap", 0), q.get("bp", 0)
                if ap <= 0 or bp <= 0 or ap < bp: continue
                e = date(2000 + int(sym[len(s):len(s) + 2]), int(sym[len(s) + 2:len(s) + 4]), int(sym[len(s) + 4:len(s) + 6]))
                obs[(s, bucket((e - today).days))].append(((ap + bp) / 2, (ap - bp) / 2)); n += 1
            tok = b.get("next_page_token")
            if not tok: break
        print(f"{s}: {n} quotes", flush=True)
    model, lines = {}, ["| Symbol | DTE bucket | Quotes | 75th pct half-spread by mid: <0.10 / 0.25 / 0.50 / 1 / 2 / 5 / 10 / 25 / >25 |",
                        "|---|---:|---:|---|"]
    for (s, bk), xs in sorted(obs.items()):
        m = np.array(xs); mids, halves = [], []
        for lo, hi in zip(BINS[:-1], BINS[1:]):
            sel = m[(m[:, 0] >= lo) & (m[:, 0] < hi)]
            if len(sel) >= 5: mids.append(float(np.median(sel[:, 0]))); halves.append(float(np.percentile(sel[:, 1], 75)))
        if len(mids) < 2: continue
        big = m[m[:, 0] > 2]; ratio = float(np.percentile(big[:, 1] / big[:, 0], 75)) if len(big) > 5 else 0.02
        model[f"{s}:{bk}"] = dict(mid=mids, half=halves, ratio=ratio)
        lines.append(f"| {s} | {bk} | {len(m)} | " + " / ".join(f"{h:.3f}@{x:.2f}" for x, h in zip(mids, halves)) + " |")
    (D.DIR / "spread-indicative.json").write_text(json.dumps(model, indent=1))
    out = D.ROOT / "docs/backtests/options-search"; out.mkdir(parents=True, exist_ok=True)
    (out / "spread_model.md").write_text("# Bid/ask model\n\nREJECTED as a fill model: every snapshot quote is stamped 16:14 ET (closing rotation) and comes from "
        "Alpaca's 'indicative' feed (modified quotes; OPRA not signed), e.g. QQQ 1DTE half-spread $0.53 on a $1.45 "
        "option. Fills use the fixed rule in outcomes.spread_model instead: index ETFs max($0.01, 1%), single stocks "
        "max($0.02, 2%); finalists are re-run at 2x.\n\nIndicative snapshot (75th percentile half-spread):\n\n"
                                          + "\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
