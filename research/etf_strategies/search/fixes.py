"""How the round-5 fixes (H1-H4, plus faster trend re-entry) did inside the search, on search + validate splits only.
Usage: python3 fixes.py -> fixes.md"""
import json
import numpy as np
import common as cm
import select_top as st

SPLIT = "real"
N1 = dict(tgt=0.15, est="sd21", cap=2.0, band=0.10, trend="none", rebal="daily")
I1 = dict(look=14, mult=1.0, freq=6, stop="max", last=71, quiet=False, size="vol2", side="both", sym="SPY")
I2 = dict(orbars=1, dir="both", entry="candle", stop="opp", target=10, quiet=False, gapf="none", size="risk1", sym="QQQ")
T1 = dict(signal="sma", L=200, weight="equal", rebal="daily", vt=None, univ="SPY")
CASES = [
    ("N1 vol target (original)", "F5_voltarget", N1, {}),
    ("H1a N1 cap 1.5x", "F5_voltarget", N1, {"cap": 1.5}),
    ("H1b N1 slower re-lever (63d vol)", "F5_voltarget", N1, {"est": "sd63"}),
    ("H1c N1 wider band (20 pts)", "F5_voltarget", N1, {"band": 0.20}),
    ("H1 all three", "F5_voltarget", N1, {"cap": 1.5, "est": "sd63", "band": 0.20}),
    ("I1b noise band (original)", "I2_noiseband", I1, {}),
    ("H2 skip quiet regime", "I2_noiseband", I1, {"quiet": True}),
    ("H3 no entries after 12:30", "I2_noiseband", I1, {"last": 35}),
    ("H2+H3", "I2_noiseband", I1, {"quiet": True, "last": 35}),
    ("I2b ORB QQQ (original)", "I1_orb", I2, {}),
    ("H4a ORB short-only", "I1_orb", I2, {"dir": "short"}),
    ("H4b ORB with gap direction", "I1_orb", I2, {"gapf": "with"}),
    ("H2 ORB skip quiet regime", "I1_orb", I2, {"quiet": True}),
    ("SMA200 (original)", "F1_trend", T1, {}),
    ("Trend: faster re-entry, 50/200 cross", "F1_trend", T1, {"signal": "cross50"}),
    ("Trend: SMA100", "F1_trend", T1, {"L": 100}),
]


def main():
    combos = json.loads((cm.CKPT / "combos.json").read_text())
    key = {(c[0], tuple(c[1].items())): i for i, c in enumerate(combos)}
    st.MODE = SPLIT; st.OUT = cm.CKPT / SPLIT
    ids, R, s = st.load(); o = np.argsort(ids); s = s[o]
    spy, m = st.spy_ex(); ss, sv = cm.sharpe(spy[:m]), cm.sharpe(spy[m:])
    names = np.array([c[0] for c in combos])
    L = ["## Round-5 fixes inside the search (search + validate splits only)", "",
         f"SPY Sharpe: search {ss:.2f}, validate {sv:.2f}. Percentile = rank of search Sharpe within its family.", "",
         "| Variant | Search Sharpe | Validate Sharpe | Family percentile (search) | Beats SPY on both |", "|---|---:|---:|---:|---|"]
    for lab, fam, base, ch in CASES:
        p = dict(base); p.update(ch); i = key[(fam, tuple(p.items()))]
        fam_s = s[names == fam, 0]
        pct = (fam_s < s[i, 0]).mean() * 100
        L.append(f"| {lab} | {s[i,0]:.2f} | {s[i,1]:.2f} | {pct:.0f} | {'yes' if s[i,0] > ss and s[i,1] > sv else 'no'} |")
    t = "\n".join(L); print(t); (cm.ROOT / "fixes.md").write_text(t + "\n")


if __name__ == "__main__":
    main()
