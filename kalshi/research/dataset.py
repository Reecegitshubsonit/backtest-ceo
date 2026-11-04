"""Build the research dataset from Kalshi's public API (read-only), with checkpoints so it can resume.

What exists (checked against docs.kalshi.com, Nov 2026):
  * settled markets: GET /markets (live set, settled since the historical cutoff, ~60 days) and
    GET /historical/markets (archive, older)
  * hourly candlesticks with best YES bid/ask OHLC, trade price and volume:
    GET /markets/candlesticks (batch, live set) and GET /historical/markets/{t}/candlesticks (archive, one per call)
  * trades: GET /markets/trades and /historical/trades (candles already aggregate them; not downloaded separately)
  * order book HISTORY: does not exist. Only the current book (REST) and live deltas (websocket/FIX).
    Candles give top-of-book (best bid/ask) per hour, no depth; the research uses those.
Multivariate combos (KXMVE*) are excluded: they are bespoke parlays with no shared book.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from kalshibot.client import KalshiClient, KalshiError

KEEP = ("ticker", "event_ticker", "close_time", "open_time", "result", "volume_fp", "exchange_index", "strike_type")
WINDOW_H = 8 * 24  # candles kept per market: last 8 days before close (7d max horizon + 24h momentum lookback)


def patient(client: KalshiClient, endpoint: str, params: dict | None = None, tries: int = 8) -> dict:
    for i in range(tries):
        try:
            return client.get(endpoint, params)
        except KalshiError as e:
            if "-> 4" in str(e) and "429" not in str(e) and "too_many" not in str(e):
                raise
            time.sleep(min(120, 15 * (i + 1)))
    raise KalshiError(f"{endpoint}: gave up")


def close_ts(m: dict) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp())


def fetch_series(client: KalshiClient, out: Path) -> dict[str, str]:
    if out.exists():
        return json.loads(out.read_text())
    cats = {s["ticker"]: s.get("category") or "Other" for s in patient(client, "/series").get("series", [])}
    out.write_text(json.dumps(cats))
    return cats


def fetch_settled(client: KalshiClient, out: Path, min_ts: int, max_ts: int, max_pages: int = 3000, log=print) -> list[dict]:
    """All settled non-combo binary markets closing in [min_ts, max_ts], checkpointed page by page."""
    state = out.with_suffix(".cursor")
    cursor = state.read_text().strip() if state.exists() else None
    if out.exists() and not cursor and out.stat().st_size:
        return [json.loads(l) for l in out.open()]
    pages = 0
    with out.open("a") as f:
        while pages < max_pages:
            p = {"status": "settled", "limit": 1000, "min_close_ts": min_ts, "max_close_ts": max_ts, "mve_filter": "exclude"}
            if cursor:
                p["cursor"] = cursor
            d = patient(client, "/markets", p)
            for m in d.get("markets", []):
                if m["ticker"].startswith("KXMVE") or m.get("result") not in ("yes", "no"):
                    continue
                if m.get("market_type", "binary") != "binary":
                    continue
                f.write(json.dumps({k: m.get(k) for k in KEEP}) + "\n")
            cursor = d.get("cursor")
            pages += 1
            state.write_text(cursor or "")
            if pages % 25 == 0:
                log(f"  market pages: {pages}")
            if not cursor:
                break
    return [json.loads(l) for l in out.open()]


def sample(markets: list[dict], per_series: int, min_volume: float) -> list[dict]:
    """Cap each series (evenly through time) so 15-minute crypto ladders do not swamp everything else."""
    by = defaultdict(list)
    for m in markets:
        if float(m.get("volume_fp") or 0) >= min_volume:
            by[m["ticker"].split("-")[0]].append(m)
    out = []
    for ms in by.values():
        ms.sort(key=close_ts)
        step = max(1, len(ms) / per_series)
        out += [ms[int(i * step)] for i in range(min(per_series, len(ms)))]
    return out


def fetch_candles(client: KalshiClient, markets: list[dict], out: Path, log=print) -> None:
    """Hourly candles for the last WINDOW_H hours of each market, batched by close-time bucket; resumable."""
    done = set()
    if out.exists():
        for l in out.open():
            done.add(json.loads(l)["t"])
    todo = [m for m in markets if m["ticker"] not in done]
    buckets = defaultdict(list)
    for m in todo:
        buckets[close_ts(m) // (6 * 3600)].append(m)
    per_req = max(1, 10000 // (WINDOW_H + 7))
    n_req = 0
    with out.open("a") as f:
        for b, ms in sorted(buckets.items()):
            end = (b + 1) * 6 * 3600
            start = b * 6 * 3600 - WINDOW_H * 3600
            for i in range(0, len(ms), per_req):
                chunk = ms[i:i + per_req]
                d = patient(client, "/markets/candlesticks", {"market_tickers": ",".join(m["ticker"] for m in chunk),
                                                              "start_ts": start, "end_ts": end, "period_interval": 60})
                got = {x.get("market_ticker"): x.get("candlesticks", []) for x in d.get("markets", [])}
                for m in chunk:
                    f.write(json.dumps({"t": m["ticker"], "c": compact(got.get(m["ticker"], []))}) + "\n")
                n_req += 1
                if n_req % 50 == 0:
                    log(f"  candle requests: {n_req}, markets left ~{len(todo) - n_req * per_req}")


def compact(cs: list[dict]) -> list[list]:
    """[end_ts, yes_bid_close, yes_ask_close, volume] per hourly candle (None where the side was empty)."""
    out = []
    for c in cs:
        b = (c.get("yes_bid") or {}).get("close_dollars")
        a = (c.get("yes_ask") or {}).get("close_dollars")
        v = c.get("volume_fp")
        out.append([c.get("end_period_ts"), None if b is None else float(b), None if a is None else float(a),
                    float(v or 0)])
    return out


def build(data_dir: Path, per_series: int = 150, min_volume: float = 50, log=print) -> dict:
    client = KalshiClient(min_interval=0.4)
    data_dir.mkdir(parents=True, exist_ok=True)
    cats = fetch_series(client, data_dir / "series.json")
    cut = patient(client, "/historical/cutoff")
    from datetime import datetime

    cutoff = int(datetime.fromisoformat(cut["market_settled_ts"].replace("Z", "+00:00")).timestamp())
    now = int(time.time())
    log(f"live window: markets settled since {cut['market_settled_ts']} (older ones are archive-only)")
    markets = fetch_settled(client, data_dir / "markets.jsonl", cutoff, now, log=log)
    log(f"settled binary markets (no combos): {len(markets)}")
    chosen = sample(markets, per_series, min_volume)
    (data_dir / "sample.json").write_text(json.dumps([m["ticker"] for m in chosen]))
    log(f"sampled {len(chosen)} markets from {len({m['ticker'].split('-')[0] for m in chosen})} series "
        f"(<= {per_series}/series, volume >= {min_volume})")
    fetch_candles(client, chosen, data_dir / "candles.jsonl", log=log)
    return {"markets": len(markets), "sampled": len(chosen), "cutoff": cut["market_settled_ts"], "categories": cats}
