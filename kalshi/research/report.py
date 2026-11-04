"""Summary tables from results.json."""
from __future__ import annotations

from pathlib import Path


def _fin(rows):
    out = ["| # | strategy | search t | validate t | holdout events | holdout mean/event | holdout t | DSR | tail check (all splits) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for i, f in enumerate(rows, 1):
        p = f["params"]
        desc = (f"{p['side']} {p['price']}, {p['hours_before_close']}h, {p['category']}, vol>={p['min_vol24']}, "
                f"spread<={p['max_spread']}, mom {p['momentum']}, {p['exit']}, size {p['size']}")
        out.append(f"| {i} | {desc} | {f['search']['t']:.2f} | {f['validate']['t']:.2f} | {f['holdout']['events']} | "
                   f"{f['holdout']['mean']:+.1%} | {f['holdout']['t']:.2f} | {f['deflated_sharpe_search']:.2f} | {_tail(f)} |")
    return "\n".join(out)


def _tail(f):
    tc = f.get("tail") or {}
    if not tc.get("applies"):
        return "n/a (early exit)"
    if not tc["events"]:
        return "no events"
    return f"{tc['losses']}/{tc['events']} lost vs {tc['breakeven_loss_rate']:.1%} break-even, p={tc['p']:.2f}"


def _tail_ok(f, n_final=10):
    tc = f.get("tail") or {}
    return not tc.get("applies") or tc.get("p", 1.0) < 0.05 / n_final  # Bonferroni over the finalists


def write(s: dict, path: Path) -> None:
    r, sh = s["real"], s["shuffled"]
    surv = [f for f in r["finalists"] if f["holdout"]["events"] >= 10 and f["holdout"]["mean"] > 0 and f["holdout"]["t"] >= 2
            and f["deflated_sharpe_search"] >= 0.95]
    nf = max(1, len(r["finalists"]))
    tail_fail = [f for f in surv if not _tail_ok(f, nf)]
    surv = [f for f in surv if _tail_ok(f, nf)]
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
        *([f"{len(tail_fail)} finalist(s) passed holdout t >= 2 and DSR >= 0.95 but failed the tail check: they buy "
           "near-certain sides, have too few events for a loss to be expected, and their loss count is not "
           f"significantly below break-even (needs p < {0.05 / nf:.3f}: 0.05 Bonferroni-split over {nf} finalists). Their t-stats come from the lack of losses so far, not from an edge."]
          if tail_fail else []),
        (f"{len(surv)} finalist(s) survive (holdout t >= 2, DSR >= 0.95, corrected tail check)."
         if surv else "Nothing survives."),
    ]
    lines += ["", "## Notes", "",
        "- Order book history: Kalshi has none (only the current book and live websocket/FIX deltas). Spread and "
        "fills come from hourly candlestick bid/ask; entries pay the ask plus the taker fee (rounded up per order).",
        "- Data: the live window only (markets settled since the 2026-09-05 historical cutoff, ~2 months). Older markets "
        "sit in the archive endpoint at one request per market and were not downloaded, so the holdout is one week.",
        "- The tail check was added after the holdout was seen, because finalists 1, 2 and 4 had zero losses. It does "
        "not change any holdout number; it only stops a no-loss streak on 96c favourites from counting as proof.",
        "- Broad 95-98c favourites (all categories, spread <= 5c) lose 0.4-1.7% per trade after fees: their loss "
        "rate (4-5%) is at or above break-even (~4%).",
        "- The old favourite 80-95c strategy is not stable: search -0.1% (t -0.1), validate -4.2% (t -2.5), "
        "holdout +3.7% (t 3.3).",
        "- The bot stays read-only/paper for these strategies; nothing here places orders."]
    path.write_text("\n".join(lines) + "\n")
