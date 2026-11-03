"""Option 2: forward test of the frozen rules. Scores ONLY sessions after the freeze date, using the frozen code copy.
Refuses to run if any frozen file's hash changed. Simulated fills with the frozen cost model (not broker paper orders).
Run: python3 research/etf_strategies/forward_test.py   -> forward_results.md, forward_ledger.csv
(FORWARD_TEST_FREEZE=YYYY-MM-DD overrides the start date for a smoke test only; output is then marked SMOKE TEST.)"""
import hashlib, importlib.util, json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FROZEN = HERE / "frozen_2026_11_03"
MAN = json.loads((FROZEN / "MANIFEST.json").read_text())
KILL_DD = {"N1": -0.194, "T2": -0.084, "T2r": -0.080, "I1b": -0.312, "I2b": -0.300}


def load_frozen():
    for name, h in MAN["files"].items():
        got = hashlib.sha256((FROZEN / name).read_bytes()).hexdigest()
        if got != h:
            sys.exit(f"REFUSING: {name} changed since the freeze (sha256 {got[:12]} != {h[:12]}). Make a new freeze folder instead.")
    sys.path.insert(0, str(FROZEN))
    mods = {}
    for m in ["backtest", "new_strategies", "intraday"]:
        spec = importlib.util.spec_from_file_location(m, FROZEN / f"{m}.py")
        mods[m] = importlib.util.module_from_spec(spec); sys.modules[m] = mods[m]; spec.loader.exec_module(mods[m])
    return mods["backtest"], mods["new_strategies"], mods["intraday"]


def main():
    bt, ns, it = load_frozen()
    smoke = "FORWARD_TEST_FREEZE" in os.environ
    freeze = pd.Timestamp(os.environ.get("FORWARD_TEST_FREEZE", MAN["freeze_date"]))
    O, C = bt.daily_panel(sorted(set(["SPY", "SSO", "UPRO", bt.CASH] + bt.TREND_SET + bt.GTAA5)))
    rf = (C[bt.CASH] / C[bt.CASH].shift(1) - 1).fillna(0.0)
    after = C.index[C.index > freeze]
    title = ("SMOKE TEST (not forward evidence): " if smoke else "") + f"Forward test since {freeze.date()} (frozen rules, {MAN['freeze_date']})"
    if len(after) == 0:
        text = f"# {title}\n\nNo sessions after the freeze yet (latest data {C.index[-1].date()}).\n"
        print(text); (HERE / "forward_results.md").write_text(text); return
    daily = bt.run_window([("SPY", bt.s_spy_bh), ("N1", ns.s_voltarget), ("T2", bt.make_tsmom(bt.TREND_SET)),
                           ("T2r", bt.make_tsmom(bt.GTAA5))], O, C, rf, after[0])
    rets = {k: v[0] for k, v in daily.items()}
    trades = {k: v[1]["pos_changes"] for k, v in daily.items()}
    spy_d, qqq_d = it.load("SPY"), it.load("QQQ")
    for key, (pnl, tr) in {"I1b": it.i1(spy_d, True), "I2b": it.i2(qqq_d, True)}.items():
        p = pnl.reindex(after).fillna(0.0)
        rets[key] = p + rf.reindex(after).fillna(0.0)
        trades[key] = sum(1 for d, *_ in tr if d > freeze)
    df = pd.DataFrame(rets).loc[after]
    n = len(df)
    lines = [f"# {title}", "", f"{n} sessions: {after[0].date()} .. {after[-1].date()}. Next checkpoint: "
             f"{next((c for c in MAN['review_rules']['checkpoints_sessions'] if c > n), 'done')} sessions.", "",
             "| Strategy | Return | Sharpe (xs T-bill) | Max DD | Kill level | Trades / position changes | Status |", "|---|---:|---:|---:|---:|---:|---|"]
    r_f = rf.reindex(after).fillna(0.0)
    for k in df:
        x = df[k]; eq = (1 + x).cumprod(); dd = (eq / eq.cummax() - 1).min()
        ex = x - r_f; sh = ex.mean() / ex.std() * np.sqrt(252) if n > 1 and ex.std() > 0 else float("nan")
        kill = KILL_DD.get(k)
        status = "—" if kill is None else ("KILL: forward DD beyond 1.5x backtest" if dd < 1.5 * kill else "running")
        lines.append(f"| {k} | {(eq.iloc[-1]-1)*100:+.2f}% | {sh:.2f} | {dd*100:.1f}% | {'' if kill is None else f'{1.5*kill*100:.0f}%'} | {trades[k]} | {status} |")
    lines += ["", "Strategies: " + "; ".join(f"**{k}** {v}" for k, v in MAN["strategies"].items()), "",
              "Rules: " + MAN["review_rules"]["kill"] + ". " + MAN["review_rules"]["graduate"]]
    text = "\n".join(lines); print(text)
    if not smoke:
        (HERE / "forward_results.md").write_text(text + "\n")
        df.to_csv(HERE / "forward_ledger.csv", float_format="%.8f")


if __name__ == "__main__":
    main()
