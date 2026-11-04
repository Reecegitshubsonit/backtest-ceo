"""Summary tables from results.json."""
from __future__ import annotations

from pathlib import Path


def _fin(rows):
    out = ["| # | strategy | search t | validate t | holdout events | holdout mean/event | holdout t | DSR |", "|---|---|---|---|---|---|---|---|"]
    for i, f in enumerate(rows, 1):
        p = f["params"]
        desc = (f"{p['side']} {p['price']}, {p['hours_before_close']}h, {p['category']}, vol>={p['min_vol24']}, "
                f"spread<={p['max_spread']}, mom {p['momentum']}, {p['exit']}, size {p['size']}")
        out.append(f"| {i} | {desc} | {f['search']['t']:.2f} | {f['validate']['t']:.2f} | {f['holdout']['events']} | "
                   f"{f['holdout']['mean']:+.1%} | {f['holdout']['t']:.2f} | {f['deflated_sharpe_search']:.2f} |")
    return "\n".join(out)


def write(s: dict, path: Path) -> None:
    r, sh = s["real"], s["shuffled"]
    surv = [f for f in r["finalists"] if f["holdout"]["events"] >= 10 and f["holdout"]["mean"] > 0 and f["holdout"]["t"] >= 2
            and f["deflated_sharpe_search"] >= 0.95]
    lines = [
        "# Strategy search results", "",
        f"Decision rows: {s['rows']:,}. Parameter space: {s['space']:,}; combinations searched: {r['combos']:,}.", "",
        "| split | from | to | events |", "|---|---|---|---|",
        *[f"| {k} | {v['from']} | {v['to']} | {v['events']} |" for k, v in s["splits"].items()], "",
        "| | real data | shuffled outcomes (luck) |", "|---|---|---|",
        f"| combos with >= 30 events and positive mean (search) | {r['eligible_search']:,} | {sh['eligible_search']:,} |",
        f"| best search t | {r['best_search_t']:.2f} | {sh['best_search_t']:.2f} |",
        f"| combos with search t > 3 | {r['search_t_gt_3']:,} | {sh['search_t_gt_3']:,} |",
        f"| top-200 that stayed profitable on validation | {r['passed_validation']} | {sh['passed_validation']} |",
        f"| rejected by neighbour check | {r['rejected_by_neighbours']} | {sh['rejected_by_neighbours']} |",
        f"| finalists sent to holdout | {len(r['finalists'])} | {len(sh['finalists'])} |", "",
        "## Finalists on the holdout (tested once)", "", _fin(r["finalists"]) if r["finalists"] else "None.", "",
        "## Same pipeline on shuffled outcomes", "", _fin(sh["finalists"]) if sh["finalists"] else "None.", "",
        "## Earlier strategies on the same holdout", "", "| strategy | events | mean/event | t |", "|---|---|---|---|",
        *[f"| {b['strategy']} | {b['holdout_events']} | {b['holdout_mean']:+.1%} | {b['holdout_t']:.2f} |" for b in s["baselines"]],
        "| copy trading (Rivo picks) | not testable: Kalshi data has no trader identities | | |",
        "| weather forecast models (GFS/ECMWF, NBM) | separate backtests: -15% to -24% ROI, model Brier worse than market | | |", "",
        "## Verdict", "",
        (f"{len(surv)} finalist(s) are profitable on the holdout with t >= 2 and deflated Sharpe >= 0.95."
         if surv else "Nothing survives: no finalist is profitable on the holdout with t >= 2 and a deflated Sharpe >= 0.95."),
    ]
    path.write_text("\n".join(lines) + "\n")
