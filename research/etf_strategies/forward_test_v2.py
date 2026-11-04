"""Forward test of the round-7 freeze (frozen_2026_11_04). Scores only sessions after the freeze date.
Refuses if any frozen file changed. Run: python3 research/etf_strategies/forward_test_v2.py -> forward_results_v2.md
(FORWARD_TEST_FREEZE=YYYY-MM-DD for a smoke test; output then marked and not written.)"""
import hashlib, importlib, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; FZ = HERE / "frozen_2026_11_04"; MAN = json.loads((FZ / "MANIFEST.json").read_text())


def main():
    for n, h in MAN["files"].items():
        if hashlib.sha256((FZ / n).read_bytes()).hexdigest() != h: sys.exit(f"REFUSING: {n} changed since the freeze")
    sys.path.insert(0, str(FZ))
    cm, fd, fi, moc = (importlib.import_module(m) for m in ("common", "families_daily", "families_intraday", "moc"))
    cm.END = "2099-12-31"; fi.END = cm.END
    smoke = "FORWARD_TEST_FREEZE" in os.environ
    fz = pd.Timestamp(os.environ.get("FORWARD_TEST_FREEZE", MAN["freeze_date"]))
    O, H, L, C = cm.panel(); D = cm.Daily(O, H, L, C); rf = pd.Series(D.rf, index=D.idx)
    now = pd.Timestamp.now(tz="America/New_York")
    done = D.idx[(D.idx.date < now.date()) | ((D.idx.date == now.date()) & (now.hour * 60 + now.minute >= 975))]
    after = done[done > fz]                          # completed sessions only (after 16:15 ET)
    title = ("SMOKE TEST (not evidence): " if smoke else "") + f"Forward test v2 since {fz.date()}"
    if len(after) == 0:
        t = f"# {title}\n\nNo sessions after the freeze yet (latest {D.idx[-1].date()}).\n"; print(t)
        if not smoke: (HERE / "forward_results_v2.md").write_text(t)
        return
    spy = (C["SPY"] / C["SPY"].shift(1) - 1).fillna(0)
    nb = fi.NoiseBand.pnl(fi.Bars("QQQ"), dict(look=14, mult=1.0, freq=6, stop="max", last=71, quiet=False, size="vol2", side="both", sym="QQQ"))[0]
    nbq = nb.reindex(D.idx).fillna(0) + rf
    W = fd.MeanRev.weights(D, dict(ind=27, exit="sma5", maxhold=10, trend="none", sizing="slot", univ="SPY"))
    ibs = pd.Series(moc.run_moc(D, W)[0], index=D.idx)
    S = pd.DataFrame({"SPY": spy, "NBQ": nbq, "IBS": ibs, "P1": 0.5 * spy + 0.5 * nbq, "P2": spy + 0.5 * (nbq - rf),
                      "P3": 0.4 * spy + 0.3 * nbq + 0.3 * ibs}).loc[after]
    r_f = rf.loc[after]; n = len(after)
    L = [f"# {title}", "", f"{n} sessions: {after[0].date()} .. {after[-1].date()}", "",
         "| Sleeve / portfolio | Return | Sharpe (xs T-bill) | Max DD | vs vol-matched SPY return |", "|---|---:|---:|---:|---:|"]
    for k in S:
        x = S[k]; eq = (1 + x).cumprod(); ex = x - r_f
        sh = ex.mean() / ex.std() * np.sqrt(252) if n > 1 and ex.std() > 0 else float("nan")
        kv = x.std() / S["SPY"].std() if n > 1 else 1.0; vm = (1 + r_f + kv * (S["SPY"] - r_f)).prod() - 1
        L.append(f"| {k} | {(eq.iloc[-1]-1)*100:+.2f}% | {sh:.2f} | {(eq/eq.cummax()-1).min()*100:.1f}% | {(eq.iloc[-1]-1-vm)*100:+.2f} pts |")
    L += ["", "Sleeves: " + "; ".join(f"**{k}** {v}" for k, v in MAN["sleeves"].items()),
          "Portfolios: " + "; ".join(f"**{k}** {v}" for k, v in MAN["portfolios"].items()), "", "Review rules: " + MAN["review"]]
    t = "\n".join(L); print(t)
    if not smoke:
        (HERE / "forward_results_v2.md").write_text(t + "\n"); S.to_csv(HERE / "forward_ledger_v2.csv", float_format="%.8f")


if __name__ == "__main__":
    main()
