"""python -m research {data,features,search,all}  (from kalshi/). Read-only: never places orders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

D = Path("data/research")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="research")
    ap.add_argument("step", choices=["data", "features", "search", "all"])
    ap.add_argument("--per-series", type=int, default=150)
    ap.add_argument("--combos", type=int, default=100_000)
    a = ap.parse_args(argv)
    log = lambda s: print(s, flush=True)
    if a.step in ("data", "all"):
        from .dataset import build
        r = build(D, per_series=a.per_series, log=log)
        log(f"data: {r['markets']} settled markets, sampled {r['sampled']}")
    if a.step in ("features", "all"):
        from .features import build as fb
        fb(D, D / "features.npz", log=log)
    if a.step in ("search", "all"):
        from .search import run
        from .report import write
        s = run(D / "features.npz", D / "ckpt", D / "results.json", log=log, n_combos=a.combos)
        write(s, Path("research/RESULTS.md"))
        log(open("research/RESULTS.md").read())


if __name__ == "__main__":
    main()
