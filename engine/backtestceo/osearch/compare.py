"""Earlier best strategies on the same holdout window as the search, plus the final report.

    python3 -m backtestceo.osearch.compare

Caveat printed in the report: the earlier strategies were tuned on data that overlaps this holdout window
(their train/test ran through 2026-11-02), so their holdout numbers are in-sample-contaminated.
"""
import json, math
from datetime import date

import numpy as np

from .. import options60 as o, options_fix as f, options_v2 as v, shares_daily as sd
from . import data as D, search as S

EARLIER_OPTIONS = {
    "v2 (3m): 0DTE iron condor 15:00": ("IC", 0.0025, 0.005, "15:00", None, None, 0.01, None, 0.10),
    "v2 (3m): 0DTE bull put 15:00": ("PUT", 0.0025, 0.01, "15:00", None, None, 0.01, None, 0.10),
    "v2 (3m): EMA+VWAP trend spread 11:00": ("DIR:EMA+VWAP trend", 0.0075, 0.01, "11:00", None, None, 0.006, None, 0.0),
    "v2 (6m): RSI14 reversion spread 15:00": ("DIR:RSI14 reversion", 0.0025, 0.01, "15:00", None, None, None, None, 0.10),
    "v2 (6m): 0DTE bear call 10:00": ("CALL", 0.0075, 0.005, "10:00", None, None, 0.006, None, 0.25),
}


def earlier(h0, h1):
    rows = []
    und, days = f.load()
    hd = [d for d in days if str(h0) <= str(d) <= str(h1)]
    ctx = f.day_ctx(und, days)
    ctx = {k: x for k, x in ctx.items() if k[1] in hd and (o.CACHE / f"opt/{k[0]}-{k[1]}.json").exists()
           and len(x["bars"]) >= 70}
    v._init(ctx, hd)
    for name, cfg in EARLIER_OPTIONS.items():
        tr = v.evaluate(cfg, v._G["ctx"], v._G["days"], v._G["tapes"], 1, 2)
        m = o.metrics(tr, hd)
        rows.append(dict(name=name + " (SPY+QQQ, 1 contract, strict fill, 2x spread)", **m))
    data = {s: sd.add_ind(r) for s, r in sd.daily().items()}
    for name, (_, _, ks) in sd.STRATS.items():
        k = {"RSI(2) pullback in uptrend (Connors)": 10, "EMA200 trend + close below EMA5 by k% (EMA snap-back)": 1.0,
             "IBS < k in uptrend, 1-3 day hold": 0.1, "k down closes above EMA200": 3,
             "RSI(2) < k AND IBS < 0.25 in uptrend": 10, "RSI(14) < k above EMA50 (trend pullback)": 45}[name]
        tr, ds = sd.backtest(data, name, k, str(h0), str(h1))
        m = o.metrics(tr, ds)
        rows.append(dict(name=f"shares daily: {name} (k={k}), $5k/trade", **m))
    return rows


def fmt_m(m):
    if not m.get("trades") and not m.get("n"): return "0 | - | - | - | - | -"
    n = m.get("trades", m.get("n"))
    return f"{n} | {m['win']*100:.1f} | {m['exp']:.2f} | {m.get('total', 0):.0f} | {m['mdd']:.0f} | {m['sharpe']:.2f}"


def main():
    real = json.loads((S.RUN / "real" / "finalists.json").read_text())
    shuf = json.loads((S.RUN / "shuffled" / "finalists.json").read_text())
    hr = json.loads((S.RUN / "real" / "holdout.json").read_text())
    hs = json.loads((S.RUN / "shuffled" / "holdout.json").read_text())
    p2 = S.RUN / "real" / "holdout_2x_spread.json"
    x2 = {r["desc"]: r["holdout_2x"] for r in json.loads(p2.read_text())} if p2.exists() else {}
    seg = real["segments"]
    h0, h1 = date.fromisoformat(seg[2]), date.fromisoformat(seg[3])
    L = ["# Options strategy search: 100,000 combinations, walk-forward, multiple-testing corrected", "",
         f"Data: all Alpaca options history usable here ({seg[0]} .. {seg[3]}), SPY QQQ IWM NVDA TSLA AAPL, 30-min "
         "option trade bars + SIP underlying bars. Split by time: search "
         f"{seg[0]}..{seg[1]} (60%), validate {seg[1]}..{seg[2]} (20%), holdout {seg[2]}..{seg[3]} (20%).", "",
         f"Space {real['total_space']:,} combinations; {real['sampled']:,} sampled (same list for the shuffled run). "
         f"{real['eligible']:,} had >= {S.MIN_SEARCH_TRADES} search trades. Top {S.TOP_TO_VALIDATE} by search Sharpe went to "
         f"validation; finalists = best validation Sharpe that pass the neighbour test (>= 2/3 of one-step neighbours "
         f"profitable in search and validation). Top {S.N_FINAL} were run on the holdout once.", "",
         "Bug found and fixed before the holdout was touched: the first run picked strikes using the entry bar's own "
         "VWAP (the next 30 minutes), which let 0DTE 15:30 condors 'see' the close (validation Sharpe 12.8, same in the "
         "shuffled run). Now strikes are picked from the last print of a bar that closed before entry, and entry fills at "
         "the worse of that print and the entry-bar VWAP, then +- half-spread. All numbers below are after the fix.", "",
         "## Luck benchmark (same search, signals shuffled in time)", "",
         "| Run | Eligible | Best search Sharpe | 95th pct search Sharpe | Passed validation | Best validation Sharpe | Neighbour rejects | Finalists |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in (real, shuf):
        L.append(f"| {r['label']} | {r['eligible']:,} | {r['best_search_sharpe']:.2f} | {r['p95_search_sharpe']:.2f} | "
                 f"{r['validated']} | {r['best_validate_sharpe']:.2f} | {r['neighbour_rejects']} | {len(r['finals'])} |")
    for lab, H in (("Real", hr), ("Shuffled (luck benchmark)", hs)):
        L += ["", f"## {lab}: finalists on the holdout (run once)", "",
              "| # | Strategy | Search n / Sharpe / DSR | Validate n / Sharpe / DSR | Neighbours | Holdout trades | Win % | Exp $ | Total $ | Max DD $ | Sharpe | p (1-sided) | 2x spread exp $ / Sharpe | Survives |",
              "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
        for i, r in enumerate(H):
            h = r["holdout"]
            surv = (h["n"] >= 30 and h["exp"] > 0 and r["p_one_sided"] < 0.05 / max(len(H), 1)
                    and r["dsr_validate"] >= 0.95)
            r["survives"] = surv
            z = x2.get(r["desc"]) if lab == "Real" else None
            stress = f"{z['exp']:.2f} / {z['sharpe']:.2f}" if z else "-"
            L.append(f"| {i+1} | {r['desc']} | {r['search']['n']} / {r['search']['sharpe']:.2f} / {r['dsr_search']:.2f} | "
                     f"{r['validate']['n']} / {r['validate']['sharpe']:.2f} / {r['dsr_validate']:.2f} | {r['nb_pass']} | "
                     f"{h['n']} | {h['win']*100:.1f} | {h['exp']:.2f} | {h['total']:.0f} | {h['mdd']:.0f} | {h['sharpe']:.2f} | "
                     f"{r['p_one_sided']:.4f} | {stress} | {'YES' if surv else 'no'} |")
    n_surv = sum(r["survives"] for r in hr)
    L += ["", "Survives = holdout >= 30 trades, positive expectancy, one-sided p < 0.05/10 (Bonferroni over the 10 "
          "holdout tests) and validation Deflated Sharpe >= 0.95.", "",
          f"**Survivors: {n_surv} of {len(hr)}.**" + ("" if n_surv else " Nothing survives."), ""]
    E = earlier(h0, h1)
    L += ["## Earlier best strategies on the same holdout window", "",
          "In-sample warning: these were tuned on data that overlaps this window, so they had an advantage here.", "",
          "| Strategy | Trades | Win % | Exp $ | Total $ | Max DD $ | Sharpe |", "|---|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {r['name']} | {fmt_m(r)} |" for r in E]
    L += ["", "## Data limits (stated plainly)", "",
          "* No historical option quotes on Alpaca (endpoint 404), so fills cannot use real bid/ask. Fills are trade-bar "
          "VWAP +- a modelled half-spread (index ETFs max($0.01, 1%), single stocks max($0.02, 2%)); buys at the "
          "modelled ask, sells at the modelled bid, never the midpoint. A live-quote calibration was attempted and "
          "rejected (`spread_model.md`).",
          "* No Level 2 / depth history anywhere on Alpaca. Option trade prints exist but cannot be signed without "
          "quotes; stock L1 quote/trade history exists but was not pulled (tick volume for 2.7 years x 6 symbols). "
          "So no order-flow features were used.",
          "* Contract lists are not reachable here; OCC symbols were constructed. Expiries that did not exist "
          "(e.g. early-2024 IWM Tue/Thu) simply have no trades.",
          "* Delta from Black-Scholes implied vol of each contract's own price (r = 4.5%).",
          "* Settlement at intrinsic on the expiry close; no assignment/pin modelling; daily P&L booked on exit day."]
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "README.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


DOC = S.DOC

if __name__ == "__main__":
    main()
