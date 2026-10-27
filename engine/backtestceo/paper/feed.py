"""Client for the live-events service (/workspace/live-events, port 8030): POST /v1/events with
agent_activity, ceo_decision and strategy_result events. The feed is best effort: if it is down, events are
kept (bounded) and retried; trading never waits on it. Every event is also appended to a local JSONL log."""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .safety import LOCAL_HOSTS, assert_host

SLOTS = ("scanner", "strategist", "backtester", "auditor", "regime", "risk")
STAGES = ("scanning", "strategist", "backtest", "validation", "risk", "ceo")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LiveEvents:
    def __init__(self, url="http://127.0.0.1:8030", source="paper-runner", log_path=None, enabled=True, timeout=2.0):
        assert_host(url, LOCAL_HOSTS)  # the feed is local only
        self.url, self.source, self.enabled, self.timeout = url.rstrip("/"), source[:80], enabled, timeout
        self.log_path = Path(log_path) if log_path else None
        self.pending, self.sent, self.failed = [], 0, 0
        self.last_error = None

    def emit(self, ev: dict):
        ev = {"source": self.source, "at": now_iso(), **ev}
        if ev["kind"] == "agent_activity":
            assert ev["slot"] in SLOTS, ev["slot"]
        if ev["kind"] == "ceo_decision":
            assert ev["agent"] in SLOTS and ev["outcome"] in ("approved", "rejected", "pending")
        if ev["kind"] == "strategy_result":
            assert ev.get("stage", "backtest") in STAGES
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(ev, default=str) + "\n")
        self.pending.append(ev)
        self.pending = self.pending[-1000:]
        return ev

    def flush(self):
        if not self.enabled or not self.pending:
            return True
        batch, self.pending = self.pending, []
        try:
            req = urllib.request.Request(self.url + "/v1/events", data=json.dumps(batch, default=str).encode(),
                                         headers={"content-type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                r.read()
            self.sent += len(batch)
            self.last_error = None
            return True
        except urllib.error.HTTPError as e:  # the service rejected the batch (bad event): drop it, do not retry forever
            self.failed += 1
            self.last_error = f"rejected {e.code}: {e.read()[:160].decode(errors='replace')}"
            return False
        except Exception as e:  # feed down or rejected: keep the events for the next flush
            self.failed += 1
            self.last_error = f"{e.__class__.__name__}: {str(e)[:120]}"
            self.pending = (batch + self.pending)[-1000:]
            return False


class MemoryFeed(LiveEvents):
    """Test double: records events instead of posting."""

    def __init__(self):
        self.url, self.source, self.enabled, self.log_path = "memory", "paper-runner (test)", False, None
        self.pending, self.sent, self.failed, self.last_error = [], 0, 0, None
        self.events = []

    def emit(self, ev):
        ev = super().emit(ev)
        self.events.append(ev)
        return ev

    def kinds(self, kind):
        return [e for e in self.events if e["kind"] == kind]
