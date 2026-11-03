"""Stress the walk-forward picks: strict same-bar fills, doubled spread cost, worst trade. Test window only.

    python3 -m backtestceo.options_fix_audit
"""
import json
from . import options60 as o, options_fix as f

PICKS = {
    "Bear call spread 14:00": ("credit", "CALL", None, 0.0025, 0.01, "14:00", None, None, 0.01),
    "Iron fly 15:00, 2x stop": ("credit", "IC", None, 0.0, 0.01, "15:00", 2.0, None, 0.01),
    "Iron condor 15:00": ("credit", "IC", None, 0.0025, 0.005, "15:00", None, None, 0.01),
    "Bull put spread 15:00": ("credit", "PUT", None, 0.0025, 0.01, "15:00", None, None, 0.01),
    "VWAP side spread 11:00": ("signal", "DIR", "VWAP side", 0.0075, 0.01, "11:00", None, None, 0.006),
    "RSI14 momentum spread 12:30": ("signal", "DIR", "RSI14 momentum", 0.0075, 0.01, "12:30", None, None, 0.01),
    "EMA+VWAP trend spread 11:00": ("signal", "DIR", "EMA+VWAP trend", 0.0075, 0.01, "11:00", None, None, 0.006),
    "EMA9>21 spread 14:00, 50% tgt": ("signal", "DIR", "EMA9>21", 0.0075, 0.01, "14:00", None, 0.5, None),
}


def main():
    und, days = f.load()
    test = days[f.TRAIN_DAYS:]
    ctx = f.day_ctx(und, days)
    ctx = {k: v for k, v in ctx.items() if (o.CACHE / f"opt/{k[0]}-{k[1]}.json").exists() and len(v["bars"]) >= 70}
    f._init(ctx, test)
    base_fill, base_spread = f.Tape.fill, o.opt_half_spread
    scen = {"base": (3, 1), "strict fill": (1, 1), "2x spread": (3, 2), "strict + 2x": (1, 2), "strict + 3x": (1, 3)}
    L = ["| Strategy | " + " | ".join(f"{s} exp $ / Sharpe" for s in scen) + " | Trades (base/strict) | Worst trade $ |",
         "|---|" + "---:|" * (len(scen) + 2)]
    out = {}
    for name, cfg in PICKS.items():
        cells, n = [], []
        for s, (look, mult) in scen.items():
            f.Tape.fill = lambda self, sym, hm, lk=3, _l=look: base_fill(self, sym, hm, min(lk, _l))
            o.opt_half_spread = lambda p, _m=mult: _m * max(0.01, 0.01 * p)
            for t in f._G["tapes"].values(): t._marks.clear()
            tr = f.eval_config(cfg, f._G["ctx"], f._G["days"], f._G["tapes"])
            m = o.metrics(tr, test)
            cells.append(f"{m.get('exp', 0):.2f} / {m.get('sharpe', 0):.2f}"); n.append(m["trades"])
            if s == "base": worst = min(t["pnl"] for t in tr)
            out[(name, s)] = m
        L.append(f"| {name} | " + " | ".join(cells) + f" | {n[0]}/{n[1]} | {worst:.0f} |")
    f.Tape.fill, o.opt_half_spread = base_fill, base_spread
    txt = "\n".join(L)
    (f.OUT / "audit.md").write_text("# Stress test of picks (test window)\n\n" + txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
