"""Push feed of followed traders' Kalshi trades via Rivo's server-sent-events stream.

GET https://api.rivo.markets/v2/stream?channels=trades&venue=kalshi&action=all&trader=kalshi:<name>...
Rivo pushes each trade as it lands; a connection lasts at most 15 minutes, so we reconnect with
Last-Event-ID and Rivo replays what we missed (last hour, up to 200). Needs RIVO_API_KEY (read scope).
Each frame becomes a copy Signal; the copy engine still applies every guard (age, slippage, caps).
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Iterable, Iterator

import requests

from .copy import CopyEngine, Signal
from .model import parse_time

URL = "https://api.rivo.markets/v2/stream"


def sse_frames(lines: Iterable[str]) -> Iterator[tuple[str | None, str | None, str]]:
    """Yield (event, id, data) from SSE lines; comments (': ping') are skipped."""
    event = eid = None
    data: list[str] = []
    for line in lines:
        if line is None:
            continue
        if line == "":
            if data:
                yield event, eid, "\n".join(data)
            event, eid, data = None, None, []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("id:"):
            eid = line[3:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def frame_to_signals(f: dict) -> list[Signal]:
    """Map one Rivo trade row to copy signals. Trims are ignored; a flip closes then opens."""
    m = f.get("market") or {}
    if m.get("venue") != "kalshi" or not m.get("venueId"):
        return []
    trader = ((f.get("trader") or {}).get("name") or (f.get("trader") or {}).get("ref", "").split(":", 1)[-1]).lower()
    side = (f.get("outcome") or "").lower()
    if not trader or side not in ("yes", "no"):
        return []
    dt = parse_time(f.get("time"))
    ts = int(dt.timestamp()) if dt else int(time.time())
    base = dict(trader=trader, ticker=m["venueId"], price=f.get("price"), contracts=f.get("contracts"), ts=ts)
    action, entry = f.get("action"), f.get("entry")
    if action == "sell":
        return [] if entry == "trim" else [Signal(side=side, action="sell", **base)]
    if action == "buy":
        if entry == "flip":  # they exited the other side and bought this one
            other = "no" if side == "yes" else "yes"
            return [Signal(side=other, action="sell", **base), Signal(side=side, action="buy", **base)]
        return [Signal(side=side, action="buy", **base)]
    return []


class StreamState:
    def __init__(self, path: Path):
        self.path = path
        d = json.loads(path.read_text()) if path.exists() else {}
        self.last_id: str | None = d.get("last_id")
        self.seen = deque(d.get("seen", []), maxlen=2000)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"last_id": self.last_id, "seen": list(self.seen)}))


def handle_frame(engine: CopyEngine, st: StreamState, eid: str | None, data: str) -> list[dict]:
    f = json.loads(data)
    tid = f.get("id") or eid
    if tid in st.seen:  # replays after reconnect can repeat a trade
        return []
    out = [engine.handle(s) for s in frame_to_signals(f)]
    st.seen.append(tid)
    st.last_id = eid or st.last_id
    st.save()
    engine.log("rivo_trade", ts=int(time.time()), rivo_id=tid, trader=(f.get("trader") or {}).get("ref"),
               ticker=(f.get("market") or {}).get("venueId"), outcome=f.get("outcome"), action=f.get("action"),
               entry=f.get("entry"), price=f.get("price"), usd=f.get("usd"), results=[o.get("result") for o in out])
    return out


def run(engine: CopyEngine, state_path: Path, api_key: str | None = None, settle_every: int = 300) -> None:
    key = api_key or os.environ.get("RIVO_API_KEY")
    if not key:
        raise SystemExit("Set RIVO_API_KEY (rivo.markets > Settings > API keys, read scope)")
    traders = sorted(engine.cfg.traders)
    if not traders:
        raise SystemExit("No traders in the copy config")
    params = [("channels", "trades"), ("venue", "kalshi"), ("action", "all")] + [("trader", f"kalshi:{t}") for t in traders]
    st = StreamState(state_path)
    backoff, last_settle = 1.0, 0.0
    mode = "LIVE copy" if engine.live else "paper copy"
    print(f"streaming {len(traders)} traders from Rivo ({mode}): {', '.join(traders)}")
    while True:
        headers = {"Authorization": f"Bearer {key}", "Accept": "text/event-stream"}
        if st.last_id:
            headers["Last-Event-ID"] = st.last_id
        try:
            with requests.get(URL, params=params, headers=headers, stream=True, timeout=(10, 90)) as r:
                if r.status_code in (401, 403):
                    raise SystemExit(f"Rivo refused the key ({r.status_code}): {r.text[:200]}")
                if r.status_code == 429:
                    time.sleep(float(r.headers.get("retry-after", 30)))
                    continue
                r.raise_for_status()
                backoff = 1.0
                for event, eid, data in sse_frames(r.iter_lines(decode_unicode=True)):
                    if event == "error":
                        print("rivo stream error:", data)
                        break
                    if event == "trade":
                        for out in handle_frame(engine, st, eid, data):
                            print(json.dumps(out))
                    if time.time() - last_settle > settle_every:
                        engine.settle_all()
                        last_settle = time.time()
        except requests.RequestException as e:
            # Rivo ends every stream within 15 minutes; resuming from Last-Event-ID loses nothing
            print(time.strftime("%H:%M"), "stream closed, reconnecting" + ("" if "prematurely" in str(e) else f" ({e})"))
        # 90s read timeout > 25s pings, so a silent socket is caught; normal 15-min closes land here too
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)
