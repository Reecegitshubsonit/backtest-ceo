# Round 6: 100,176-combination ETF strategy search

Run order (from this folder):

    python3 check_engines.py        # fast engines reproduce the exact engines (SMA200 0.72 vs 0.71, N1 0.77 vs 0.76, I1b 0.69 vs 0.69, I2b 0.55 vs 0.57)
    python3 search.py real          # checkpointed in data/search_ckpt/real (gitignored); resumes; prints progress only
    python3 search.py shuffled      # same 100,176 combos on shuffled data (luck benchmark)
    python3 select_top.py real      # + shuffled: shortlist, neighbors, top 10, Deflated Sharpe, White's Reality Check
    python3 fixes.py                # round-5 fixes, read from the search (search + validate splits only)
    python3 holdout.py --i-understand-this-runs-once   # ran once on 2026-11-04; HOLDOUT_LOCK.json blocks reruns

Outputs: `selection_real.md`, `selection_shuffled.md`, `fixes.md`, `holdout_results.md` (+ JSON/CSV).
Families: `families_daily.py`, `families_intraday.py`; shared data, splits and fast engine: `common.py`.
