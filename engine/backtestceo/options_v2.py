"""v2: fix fragile/failed options strategies; 3-month out-of-sample test with risk controls.

    python3 -m backtestceo.options_v2

Changes vs options_fix
  * Parameters are chosen on train under PESSIMISTIC execution (every leg must print in the entry bar,
    2x modelled half-spread). Penny-credit setups that only worked on cheap fills can no longer win.
  * New filters: minimum credit, overnight-gap filter, narrower wings, 15:30 entry.
  * Test = last 63 sessions (~3 months), never seen while tuning; reported at base, pessimistic and 3x cost.
  * Risk: max loss per trade (wing - credit), contracts sized so max loss <= RISK_PER_TRADE of the account,
    portfolio of all passing strategies with a daily loss stop.
"""
import itertools, json, math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date

from . import options60 as o, options_fix as f

TEST_DAYS = 63
OUT = o.ROOT / "docs/backtests/options-v2"
MIN_TRADES = 30
ACCOUNT = 25_000.0
RISK_PER_TRADE = 0.02          # max loss of one structure <= 2% of account
DAILY_STOP = 0.03              # portfolio: no new trades after -3% on the day (late entries -> applied per day)

KINDS = ["IC", "PUT", "CALL"] + [f"DIR:{s}" for s in f.SIDES]
OFFS = [0.0, 0.0025, 0.005, 0.0075]
WINGS = [0.0025, 0.005, 0.01]
ENTRIES = ["10:00", "11:00", "12:30", "14:00", "15:00", "15:30"]
STOPS = [None, 1.0, 2.0]
TGTS = [None, 0.5]
ORF = [None, 0.006, 0.010]
GAP = [None, 0.005]            # skip if |open/prev close - 1| > x
MINCR = [0.0, 0.10, 0.25]      # min net credit per share


def run(sym, d, bars, tape, kind, a, w, entry, stop, tgt, mincr, look, mult):
    hm = [b["hm"] for b in bars]
    if entry not in hm: return None
    i = hm.index(entry); spot = bars[i - 1]["c"]; e = date.fromisoformat(d)
    hs = lambda p: mult * max(0.01, 0.01 * p)
    lc = lambda p, q: abs(q) * (hs(p) * 100 + o.OPT_FEE)
    legs = []
    for right, off, q in f.LEGS[kind](a, w):
        k = round(spot * (1 + off)); s = o.occ(sym, e, right, k)
        p = tape.fill(s, entry, look)
        if p is None: return None
        legs.append((s, right, k, q, p))
    if len({(l[1], l[2]) for l in legs}) < len(legs): return None
    v0 = sum(q * p for *_, q, p in legs); credit = -v0
    if credit <= max(0.02, mincr): return None
    width = max(abs(l1[2] - l2[2]) for l1 in legs for l2 in legs if l1[1] == l2[1])
    maxloss = (width - credit) * 100
    cost = sum(lc(p, q) for *_, q, p in legs)
    if stop or tgt:
        mk = [tape.marks(s) for s, *_ in legs]; ti = f.Tape.HM.index(entry)
        for j in range(ti + 1, f.Tape.HM.index("15:45") + 1):
            vals = [m[j] for m in mk]
            if any(v is None for v in vals): continue
            pnl = (sum(q * v for v, (*_, q, _) in zip(vals, legs)) - v0) * 100
            if (stop and pnl <= -stop * credit * 100) or (tgt and pnl >= tgt * credit * 100):
                xi = j + 1; h = f.Tape.HM[xi]; gross = xc = 0.0
                for (s, _, _, q, p), m in zip(legs, mk):
                    x = tape.fill(s, h, 2)
                    if x is None: x = m[j]
                    gross += q * (x - p) * 100
                    if x >= 0.05: xc += lc(x, q)
                return gross - cost - xc, cost + xc, maxloss
    settle = bars[-1]["c"]; pnl = 0.0
    for s, r, k, q, p in legs:
        pnl += q * ((max(0.0, settle - k) if r == "C" else max(0.0, k - settle)) - p) * 100
    return pnl - cost, cost, maxloss


def evaluate(cfg, ctx, days, tapes, look, mult):
    kind, a, w, entry, stop, tgt, orf, gap, mincr = cfg
    out = []
    for (sym, d), c in ctx.items():
        if d not in days: continue
        bars = c["bars"]; hm = [b["hm"] for b in bars]
        if entry not in hm: continue
        i = hm.index(entry)
        if gap and abs(bars[0]["o"] / c["prev_close"] - 1) > gap: continue
        if orf:
            pre = bars[:i]
            if (max(b["h"] for b in pre) - min(b["l"] for b in pre)) / bars[0]["o"] > orf: continue
        k = kind
        if kind.startswith("DIR:"):
            s = f.SIDES[kind[4:]](bars[i - 1], c)
            if s == 0: continue
            k = "PUT" if s == 1 else "CALL"
        r = run(sym, d, bars, tapes[(sym, d)], k, a, w, entry, stop, tgt, mincr, look, mult)
        if r: out.append(dict(day=d, sym=sym, entry=entry, pnl=r[0], cost=r[1], maxloss=r[2]))
    return out


def configs():
    return list(itertools.product(KINDS, OFFS, WINGS, ENTRIES, STOPS, TGTS, ORF, GAP, MINCR))


_G = {}
def _init(ctx, days):
    f._init(ctx, days); _G.update(f._G)


def _work(cfgs):
    res = []
    for cfg in cfgs:
        t = evaluate(cfg, _G["ctx"], _G["days"], _G["tapes"], 1, 2)     # pessimistic
        m = o.metrics(t, sorted(_G["days"]))
        if m["trades"] >= MIN_TRADES and m["exp"] > 0:
            res.append((m["sharpe"], cfg, m))
    return res


def fmt(cfg):
    kind, a, w, entry, stop, tgt, orf, gap, mincr = cfg
    name = {"IC": "iron fly" if a == 0 else "iron condor", "PUT": "bull put spread",
            "CALL": "bear call spread"}.get(kind, f"{kind[4:]} -> put/call spread")
    bits = [f"short {a*100:.2f}% OTM", f"wing {w*100:.2f}%", f"enter {entry}"]
    if stop: bits.append(f"stop {stop:g}x credit")
    if tgt: bits.append(f"target {int(tgt*100)}%")
    if orf: bits.append(f"skip range>{orf*100:.1f}%")
    if gap: bits.append(f"skip gap>{gap*100:.1f}%")
    if mincr: bits.append(f"credit>=${mincr:.2f}")
    return f"0DTE {name}: " + ", ".join(bits)


def sized(trades):
    """Contracts so that max loss <= RISK_PER_TRADE * ACCOUNT (at least 1)."""
    out = []
    for t in trades:
        n = max(1, int(RISK_PER_TRADE * ACCOUNT // max(t["maxloss"], 1)))
        out.append(dict(t, pnl=t["pnl"] * n, cost=t["cost"] * n, n=n, risk=t["maxloss"] * n))
    return out


def portfolio(per_strategy, days):
    """All strategies together; daily stop: once realised day P&L <= -DAILY_STOP*ACCOUNT, later entries skipped."""
    byday = defaultdict(list)
    for name, tr in per_strategy.items():
        for t in tr: byday[t["day"]].append(t)
    kept = []
    for d in days:
        pnl = 0.0
        for t in sorted(byday.get(d, []), key=lambda t: t["entry"]):
            if pnl <= -DAILY_STOP * ACCOUNT: continue
            kept.append(t); pnl += t["pnl"]
    return kept


def acct_metrics(trades, days):
    m = o.metrics(trades, days)
    if not m["trades"]: return m
    daily = defaultdict(float)
    for t in trades: daily[t["day"]] += t["pnl"]
    r = [daily.get(d, 0) / ACCOUNT for d in days]; mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    m["sharpe"] = mu / sd * math.sqrt(252) if sd else 0
    m["ret"] = sum(r); m["mdd_pct"] = m["mdd"] / ACCOUNT
    m["worst"] = min(t["pnl"] for t in trades); m["maxrisk"] = max(t.get("risk", t.get("maxloss", 0)) for t in trades)
    return m


def main():
    und, days = f.load()
    test, train = days[-TEST_DAYS:], days[:-TEST_DAYS]
    ctx = f.day_ctx(und, days)
    ctx = {k: v for k, v in ctx.items() if (o.CACHE / f"opt/{k[0]}-{k[1]}.json").exists() and len(v["bars"]) >= 70}
    cfgs = configs()
    print(f"{len(cfgs)} configs; train {train[0]}..{train[-1]} ({len(train)}), test {test[0]}..{test[-1]} ({len(test)})",
          flush=True)
    with ProcessPoolExecutor(4, initializer=_init, initargs=(ctx, train)) as ex:
        scored = [r for part in ex.map(_work, [cfgs[i::64] for i in range(64)]) for r in part]
    scored.sort(key=lambda x: -x[0])
    print(f"{len(scored)} configs profitable on train under pessimistic costs", flush=True)
    best = {}
    for sh, cfg, m in scored:
        best.setdefault(cfg[0], (cfg, m))
    _init(ctx, test)
    rows, picks = [], {}
    for kind, (cfg, mtr) in best.items():
        res = {}
        for lab, look, mult in (("base", 3, 1), ("pess", 1, 2), ("3x", 1, 3)):
            tr = evaluate(cfg, _G["ctx"], _G["days"], _G["tapes"], look, mult)
            res[lab] = (tr, acct_metrics(sized(tr), test))
        b, p, x = res["base"][1], res["pess"][1], res["3x"][1]
        ok = b.get("trades", 0) >= MIN_TRADES and p.get("exp", -1) > 0 and p.get("sharpe", 0) > 1 and x.get("exp", -1) > 0
        rows.append(dict(name=fmt(cfg), kind=kind, train=mtr, base=b, pess=p, x3=x, ok=ok))
        if ok: picks[fmt(cfg)] = sized(res["pess"][0])
    # top-50 robustness under pessimistic costs
    top = []
    for sh, cfg, m in scored[:50]:
        top.append(acct_metrics(sized(evaluate(cfg, _G["ctx"], _G["days"], _G["tapes"], 1, 2)), test))
    port = acct_metrics(portfolio(picks, test), test) if picks else {}
    report(rows, top, port, picks, len(cfgs), len(scored), train, test)


def report(rows, top, port, picks, ncfg, nprof, train, test):
    OUT.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (not r["ok"], -r["pess"].get("sharpe", -9)))
    c = lambda m, k, fmt_="{:.2f}": fmt_.format(m.get(k, 0)) if m.get("trades") else "-"
    L = ["# Options v2: 3-month out-of-sample, pessimistic selection, risk-sized", "",
         f"Train {train[0]}..{train[-1]} ({len(train)} sessions); test {test[0]}..{test[-1]} ({len(test)} sessions, "
         f"~3 months, untouched while tuning). SPY + QQQ 0DTE. {ncfg:,} configs; {nprof:,} profitable on train under "
         "pessimistic execution (all legs print in the entry bar, 2x half-spread). Best per family by train Sharpe.", "",
         f"Sizing: contracts = floor(2% x ${ACCOUNT:,.0f} / max loss per structure), min 1. Metrics below are on that "
         "sized P&L. PASS = test >= 30 trades, pessimistic exp > 0 and Sharpe > 1, and still profitable at 3x cost.", "",
         "| Strategy | Test trades | Win % | Exp $/trade | Total $ | Max DD $ | Sharpe | Worst trade $ | Max risk/trade $ | "
         "Base-cost exp $ | 3x-cost exp $ | Verdict |", "|---|" + "---:|" * 10 + "---|"]
    for r in rows:
        p = r["pess"]
        L.append(f"| {r['name']} | {p.get('trades',0)} | {c(p,'win','{:.1%}')} | {c(p,'exp')} | {c(p,'total','{:.0f}')} | "
                 f"{c(p,'mdd','{:.0f}')} | {c(p,'sharpe')} | {c(p,'worst','{:.0f}')} | {c(p,'maxrisk','{:.0f}')} | "
                 f"{c(r['base'],'exp')} | {c(r['x3'],'exp')} | {'PASS' if r['ok'] else 'FAIL'} |")
    L += ["", "Table metrics use pessimistic execution (strict fills, 2x half-spread).", ""]
    if port:
        L += ["## Portfolio of passing strategies (pessimistic costs, 3% daily loss stop)", "",
              f"Trades {port['trades']}, win {port['win']:.1%}, expectancy ${port['exp']:.2f}, total ${port['total']:.0f} "
              f"({port['ret']:.1%} on ${ACCOUNT:,.0f}), max drawdown ${port['mdd']:.0f} ({port['mdd_pct']:.1%}), "
              f"Sharpe {port['sharpe']:.2f}, worst trade ${port['worst']:.0f}.", ""]
    prof = sum(t.get("exp", 0) > 0 for t in top); sh = sorted(t.get("sharpe", 0) for t in top)
    L += ["## Robustness", "", f"Top 50 train configs (pessimistic) on test: {prof}/50 profitable, median Sharpe "
          f"{sh[len(sh)//2]:.2f}, worst {sh[0]:.2f}.", ""]
    (OUT / "README.md").write_text("\n".join(L) + "\n")
    (OUT / "results.json").write_text(json.dumps([dict(r) for r in rows], indent=1, default=str))
    with open(OUT / "trades.csv", "w") as fh:
        fh.write("strategy,day,symbol,entry,contracts,pnl,cost,max_risk\n")
        for n, tr in picks.items():
            for t in tr: fh.write(f"\"{n}\",{t['day']},{t['sym']},{t['entry']},{t['n']},{t['pnl']:.2f},{t['cost']:.2f},{t['risk']:.0f}\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
