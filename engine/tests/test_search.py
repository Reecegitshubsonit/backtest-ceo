import math

import numpy as np

from backtestceo.momentum.search import GRID, SEL_KEYS, deflated_sharpe, neighbours, select, white_rc


def test_select_first_per_symbol_day_and_daily_cap():
    E = {"day": np.array([0, 0, 0, 0, 0, 0, 0, 1]), "sd": np.array([1, 1, 2, 3, 4, 5, 6, 1])}
    sel = select(np.ones(8, bool), E, cap=5)
    assert list(sel) == [0, 2, 3, 4, 5, 7]  # second event of symbol 1 dropped, 6th symbol over the cap of 5


def test_neighbours_one_notch():
    leaf = tuple(0 for _ in SEL_KEYS)
    nb = neighbours(leaf, 0)
    assert all(sum(a != b for a, b in zip(l2, leaf)) + (t2 != 0) == 1 for l2, t2 in nb)
    assert all(l2[SEL_KEYS.index("pattern")] == 0 for l2, _ in nb)


def test_grid_size():
    assert math.prod(len(v) for v in GRID.values()) == 124_416


def test_white_rc_and_dsr_detect_noise_vs_signal():
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 1, (500, 50))
    _, p_noise = white_rc(noise, B=300)
    sig = noise.copy(); sig[:, 0] += 0.5
    _, p_sig = white_rc(sig, B=300)
    assert p_noise > 0.05 and p_sig < 0.01
    srs = noise.mean(0) / noise.std(0)
    dsr_noise, _ = deflated_sharpe(noise[:, np.argmax(srs)], srs, 50)
    dsr_sig, _ = deflated_sharpe(sig[:, 0], srs, 50)
    assert dsr_noise < 0.9 and dsr_sig > 0.99
