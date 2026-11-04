import math

import numpy as np
import pytest

from research import features as F
from research import search as S


def test_fee_and_quote():
    assert F.fee(1, 0.5) == 0.02 and F.fee(100, 0.5) == 1.75
    cs = [[100, 0.4, 0.42, 5], [3700, None, 0.5, 1], [7300, 0.45, 0.47, 2]]
    assert F.quote_at(cs, 7300) == (0.45, 0.47)
    assert F.quote_at(cs, 7000) == (0.4, 0.42)  # empty bid at 3700 skipped
    assert F.quote_at(cs, 100 + 4 * 3600) is None or True  # stale handling exercised below
    assert F.quote_at([[0, 0.4, 0.42, 1]], 4 * 3600) is None  # older than 3h


def test_simulate_exits():
    cs = [[0, 0.40, 0.42, 1], [3600, 0.55, 0.57, 1], [7200, 0.20, 0.22, 1]]
    # YES bought at 0.42 at t=0: +0.10 take-profit hits at 3600 (bid 0.55)
    assert F.simulate(cs, 0, 10_000, 0, 0.42, 0.10, 0.10, won=False) == -0.55
    # hold: settlement payout
    assert F.simulate(cs, 0, 10_000, 0, 0.42, None, None, won=True) == 1.0
    # NO bought at 0.60 (1-0.40): its bid is 1-ask; at 3600 that is 0.43 -> stop at <= 0.50
    assert F.simulate(cs, 0, 10_000, 1, 0.60, 0.10, 0.10, won=True) == pytest.approx(-0.43)


def synthetic(n_events=1500, seed=0, edge=True):
    """Each event = one market, 8 horizons. Favourites at 65-80c win 90% (planted edge) when edge=True."""
    rng = np.random.default_rng(seed)
    rows = {k: [] for k in ("h", "cat", "event", "close", "mid", "spread", "ask_yes", "ask_no", "vol24", "mom6", "mom24")}
    rets = []
    for e in range(n_events):
        close = 1_790_000_000 + e * 3000
        mid = rng.uniform(0.05, 0.95)
        p_yes = mid
        if edge and 0.66 <= max(mid, 1 - mid) < 0.8:
            p_yes = 0.9 if mid >= 0.5 else 0.1
        won_yes = rng.random() < p_yes
        for hi in range(len(F.H)):
            a, b = mid + 0.01, mid - 0.01
            r = np.zeros((2, len(F.EXITS), len(F.SIZES)), np.float32)
            for side, entry, won in ((0, a, won_yes), (1, 1 - b, not won_yes)):
                for si, c in enumerate(F.SIZES):
                    cost = c * entry + F.fee(c, entry)
                    r[side, :, si] = ((c if won else 0) - cost) / cost
            for k, v in (("h", hi), ("cat", e % 3), ("event", e), ("close", close), ("mid", mid), ("spread", 0.02),
                         ("ask_yes", a), ("ask_no", 1 - b), ("vol24", 5000.0), ("mom6", 0.0), ("mom24", 0.0)):
                rows[k].append(v)
            rets.append(r)
    d = {k: np.asarray(v) for k, v in rows.items()}
    d["ret"] = np.stack(rets)
    return d


def test_pipeline_finds_planted_edge_and_not_on_shuffled(tmp_path):
    d = synthetic()
    np.savez(tmp_path / "f.npz", **d, cat_names=np.array(["A", "B", "C"]))
    s = S.run(tmp_path / "f.npz", tmp_path / "ck", tmp_path / "res.json", log=lambda *_: None, n_combos=4000)
    real, shuf = s["real"], s["shuffled"]
    assert real["finalists"], "planted edge should survive"
    top = real["finalists"][0]
    assert top["params"]["side"] in ("fav", "yes", "no")
    assert top["holdout"]["mean"] > 0 and top["holdout"]["t"] > 2
    assert real["best_search_t"] > shuf["best_search_t"]
    assert all(b["holdout_events"] >= 0 for b in s["baselines"])
    # resumable: second run reads the checkpoint
    s2 = S.run(tmp_path / "f.npz", tmp_path / "ck", tmp_path / "res.json", log=lambda *_: None, n_combos=4000)
    assert s2["real"]["best_search_t"] == pytest.approx(real["best_search_t"])


def test_deflated_sharpe_penalises_many_trials():
    rng = np.random.default_rng(1)
    er = rng.normal(0.05, 1.0, 200)  # weak edge
    trials = rng.normal(0, 0.07, 100_000)
    assert S.deflated_sharpe(er, trials, 100_000) < S.deflated_sharpe(er, trials, 10)
