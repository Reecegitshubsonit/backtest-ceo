"""ONE-TIME holdout test of the 10 selected combinations (2024-11-18 .. 2026-11-03). Refuses to run twice (HOLDOUT_LOCK.json).
Daily strategies are rerun on the exact drift engine (backtest.simulate, 3 bp/side, idle cash at T-bills); intraday on the
same per-trade engine as the search (0.5 bp/side). Benchmarks: SPY buy & hold, SPY vol-matched to each strategy, and the
10-ETF TSMOM strategy (round 2, original list). Pre-declared survival rule: Holm-adjusted bootstrap p < 0.05 for
Sharpe(strategy) > Sharpe(SPY), AND CAGR above vol-matched SPY.
Usage: python3 holdout.py --i-understand-this-runs-once"""
import hashlib, json, sys, datetime
import numpy as np
import pandas as pd
import common as cm
import families_daily as fd
import families_intraday as fi
import new_strategies as ns

LOCK = cm.ROOT / "HOLDOUT_LOCK.json"


def main():
    if LOCK.exists(): sys.exit(f"REFUSING: holdout already used ({LOCK.read_text().strip()})")
    if "--i-understand-this-runs-once" not in sys.argv: sys.exit("pass --i-understand-this-runs-once")
    sel_f = cm.ROOT / "selection_real.json"; sel = json.loads(sel_f.read_text())
    bt = cm.bt
    O, H, L, C = cm.panel(); D = cm.Daily(O, H, L, C)
    rf = pd.Series(D.rf, index=D.idx)
    h0, h1 = D.sp["holdout"]; hidx = D.idx[h0:h1]; pre = D.idx[h0 - 1]
    fams = {F.name: F for F in fd.FAMILIES + fi.FAMILIES}
    bars = {}
    res = {}
    for t in sel["top10"]:
        name, p = t["family"], t["params"]; F = fams[name]
        lab = f"#{len(res)+1} {name}: " + ", ".join(f"{k}={v}" for k, v in p.items())
        if name.startswith("F"):
            W = pd.DataFrame(F.weights(D, p), index=D.idx, columns=D.cols)
            ff = W.ffill().fillna(0.0)
            if "rebal" in F.PARAMS: tgt = W.copy()                     # rebalance on its own schedule (drift trims charged)
            else: tgt = ff.where(ff.ne(ff.shift(1)).any(axis=1))      # signal families: trade only when the target changes
            tgt = tgt.loc[pre:].copy(); tgt.iloc[0] = ff.loc[pre].values
            r, tr = bt.simulate(tgt, O.loc[pre:], C.loc[pre:], rf.loc[pre:], cm.COST_D)
            res[lab] = (r.loc[hidx], tr["round_trips"] + tr["open_at_end"])
        else:
            B = bars.setdefault(p["sym"], fi.Bars(p["sym"]))
            pnl, _ = F.pnl(B, p); x = pnl.reindex(hidx).fillna(0.0)
            res[lab] = (x + rf.loc[hidx], int((x != 0).sum()))
    spy = (C["SPY"] / C["SPY"].shift(1) - 1).loc[hidx]
    O2, C2 = bt.daily_panel(sorted(set(bt.TREND_SET + [bt.CASH])))
    rf2 = (C2[bt.CASH] / C2[bt.CASH].shift(1) - 1).fillna(0.0)
    t2 = bt.run_window([("T2", bt.make_tsmom(bt.TREND_SET))], O2, C2, rf2, hidx[0])["T2"]
    t2r = t2[0].reindex(hidx).fillna(0.0)
    r_f = rf.loc[hidx]
    L = [f"## Holdout (run once): {hidx[0].date()} .. {hidx[-1].date()}, {len(hidx)} sessions", "",
         "| Strategy | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Trades | Vol-matched SPY CAGR / DD | ΔSharpe vs SPY [95% CI] | Holm p | Survives |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    def row(name, x, n, extra=""):
        s = bt.stats(x, r_f)
        return s, f"| {name} | {s['CAGR']*100:.1f}% | {s['Vol']*100:.1f}% | {s['Sharpe']:.2f} | {s['MaxDD']*100:.1f}% | {s['LongestDD_days']} | {n} |{extra}"
    s_spy, line = row("SPY buy & hold", spy, 1, " | | | |"); L.append(line)
    s_t2, line = row("10-ETF TSMOM (round 2)", t2r, t2[1]["round_trips"] + t2[1]["open_at_end"])
    d, lo, hi, p_ = bt.boot_sharpe_diff(t2r, spy, r_f)
    m, k = bt.vol_matched_spy(spy, r_f, s_t2["Vol"]); ms = bt.stats(m, r_f)
    L.append(line + f" {ms['CAGR']*100:.1f}% / {ms['MaxDD']*100:.1f}% | {d:+.2f} [{lo:+.2f}, {hi:+.2f}] | | benchmark |")
    stats = []
    for name, (x, n) in res.items():
        s = bt.stats(x, r_f); d, lo, hi, p_ = bt.boot_sharpe_diff(x, spy, r_f)
        m, k = bt.vol_matched_spy(spy, r_f, s["Vol"]); ms = bt.stats(m, r_f)
        stats.append((name, x, n, s, d, lo, hi, p_, ms))
    adj = ns.holm(np.array([z[7] for z in stats]))
    surv = 0
    for (name, x, n, s, d, lo, hi, p_, ms), a in zip(stats, adj):
        ok = a < 0.05 and s["CAGR"] > ms["CAGR"]; surv += ok
        _, line = row(name, x, n)
        L.append(line + f" {ms['CAGR']*100:.1f}% / {ms['MaxDD']*100:.1f}% | {d:+.2f} [{lo:+.2f}, {hi:+.2f}] | {a:.3f} | {'YES' if ok else 'no'} |")
    beat_t2 = sum(1 for z in stats if z[3]["Sharpe"] > s_t2["Sharpe"])
    L += ["", f"**Survivors: {surv} of {len(stats)}.** Holdout Sharpe above SPY's ({s_spy['Sharpe']:.2f}): "
          f"{sum(1 for z in stats if z[3]['Sharpe'] > s_spy['Sharpe'])}; above 10-ETF TSMOM's ({s_t2['Sharpe']:.2f}): {beat_t2}."]
    text = "\n".join(L)
    LOCK.write_text(json.dumps({"run_at": datetime.datetime.utcnow().isoformat() + "Z",
                                "selection_sha256": hashlib.sha256(sel_f.read_bytes()).hexdigest()}) + "\n")
    print(text); (cm.ROOT / "holdout_results.md").write_text(text + "\n")
    pd.DataFrame({k: v[0] for k, v in res.items()} | {"SPY": spy, "T2": t2r}).to_csv(cm.ROOT / "holdout_returns.csv", float_format="%.8f")


if __name__ == "__main__":
    main()
