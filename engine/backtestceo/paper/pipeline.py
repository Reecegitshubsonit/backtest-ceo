"""The per-signal agent pipeline. Every agent here is RULE-BASED (fixed checks, no model calls), and says so in
its events: Scanner -> Regime Analyst -> Strategist -> Backtester -> Validation Auditor -> Risk Manager -> CEO."""
from dataclasses import dataclass, field

from .indicators import dmi

RB = "RULE-BASED"


@dataclass
class Review:
    id: str
    approved: bool = False
    blocking: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stage: str = "scanning"


def regime_label(bars):
    if len(bars) < 30:
        return "unknown (too few bars)", None
    h, l, c = [b["h"] for b in bars], [b["l"] for b in bars], [b["c"] for b in bars]
    _, _, adx = dmi(h, l, c, 14)
    a = adx[-1]
    return ("trending" if a > 25 else "ranging" if a < 20 else "transition") + f" (ADX14 {a:.1f})", a


class Pipeline:
    """ctx keys: id, name (family name), key, run, symbol, intent (entry|exit), side, reason, price, qty, notional, bar_ts,
    bar_age_s, max_bar_age_s, bars, broker, long_only, open_positions, entries_today, entries_today_total, caps,
    kill, session_ok, reference, require_positive_reference."""

    def __init__(self, feed):
        self.feed = feed

    def _act(self, slot, ctx, task, log, progress, level="info", state="working"):
        self.feed.emit(dict(kind="agent_activity", slot=slot, task=f"{RB} · {task}"[:200], state=state, strategy=ctx["name"],
                            symbol=ctx["symbol"], progress=progress, log=log[:300], level=level))

    def review(self, ctx) -> Review:
        r, entry = Review(ctx["id"]), ctx["intent"] == "entry"
        what = f"{ctx['intent']} {ctx['side']} {ctx['symbol']} ({ctx['run']})"
        # 1 Scanner: the strategy rule fired on a completed bar
        r.stage = "scanning"
        self._act("scanner", ctx, f"Signal: {what}", f"{ctx['reason']} on bar {ctx['bar_ts']}", 1 / 7)
        # 2 Regime Analyst: advisory label only (the ported rules already contain their own filters)
        label, _ = regime_label(ctx.get("bars") or [])
        self._act("regime", ctx, f"Regime for {ctx['symbol']}", f"advisory: {label}", 2 / 7)
        # 3 Strategist: turn the signal into an order plan
        r.stage = "strategist"
        if entry and ctx["side"] in ("short",) and ctx.get("long_only"):
            r.blocking.append(f"{ctx['broker']} {ctx['symbol']} is long-only: short signal not tradable")
        size = f"qty {ctx['qty']}" if ctx.get("qty") is not None else f"${ctx.get('notional', 0):,.0f} notional"
        self._act("strategist", ctx, f"Order plan: {what}", f"market {ctx['side']} {size} @~{ctx['price']:.2f}"
                  + (f", stop {ctx['stop']:.2f}" if ctx.get("stop") else ""), 3 / 7)
        # 4 Backtester: reference stats from results.json (no re-run; stats are as tested)
        r.stage = "backtest"
        ref = ctx.get("reference") or {}
        full = ref.get("full") or {}
        if not full:
            r.warnings.append("no reference backtest for this run")
        elif (full.get("net_return_pct") or 0) < 0 or (full.get("profit_factor") or 0) < 1:
            msg = f"reference backtest is losing (net {full.get('net_return_pct')}%, PF {full.get('profit_factor')})"
            (r.blocking if (entry and ctx.get("require_positive_reference")) else r.warnings).append(msg)
        self._act("backtester", ctx, f"Reference stats {ctx['run']}",
                  f"results.json: {full.get('trades')} trades, WR {full.get('win_rate')}%, PF {full.get('profit_factor')}, "
                  f"net {full.get('net_return_pct')}%, maxDD {full.get('max_drawdown_pct')}%", 4 / 7)
        # 5 Validation Auditor: data sanity on the bar that produced the signal
        r.stage = "validation"
        if ctx.get("bar_age_s") is not None and ctx["bar_age_s"] > ctx.get("max_bar_age_s", 1e18):
            r.blocking.append(f"signal bar is stale ({ctx['bar_age_s'] / 60:.0f} min old)")
        if not ctx.get("price") or ctx["price"] <= 0:
            r.blocking.append("no valid price")
        self._act("auditor", ctx, f"Validate data for {ctx['run']}",
                  "ok: fresh completed bar, valid price" if not r.blocking else "; ".join(r.blocking), 5 / 7,
                  level="warn" if r.blocking else "info")
        # 6 Risk Manager: kill switch, caps, session
        r.stage = "risk"
        caps = ctx["caps"]
        if ctx.get("kill"):
            r.blocking.append("PAPER_TRADING_KILL_SWITCH is on")
        if entry:
            if ctx["open_positions"] >= caps.max_open_positions:
                r.blocking.append(f"already {ctx['open_positions']} open position(s) (cap {caps.max_open_positions})")
            notional = ctx.get("notional") if ctx.get("notional") is not None else (ctx.get("qty") or 0) * ctx["price"]
            if notional > caps.max_notional_usd + 1e-6:
                r.blocking.append(f"notional ${notional:,.0f} over cap ${caps.max_notional_usd:,.0f}")
            if notional <= 0:
                r.blocking.append("order size is zero after caps")
            if ctx["entries_today"] >= caps.max_entries_per_day:
                r.blocking.append(f"daily entry cap reached ({caps.max_entries_per_day})")
            if ctx["entries_today_total"] >= caps.max_entries_per_day_total:
                r.blocking.append(f"runner daily entry cap reached ({caps.max_entries_per_day_total})")
        if not ctx.get("session_ok", True):
            r.blocking.append("market session closed")
        self._act("risk", ctx, f"Risk check {what}", "pass" if not r.blocking else "; ".join(r.blocking), 6 / 7,
                  level="warn" if r.blocking else "info")
        # CEO: approve iff nothing blocking. Pending first, then the verdict (same id = update in the ledger)
        r.stage = "ceo"
        base = f"{RB} CEO · {what} · {ctx['reason']}"
        self.feed.emit(dict(kind="ceo_decision", id=r.id, agent="risk", strategy=ctx["name"], outcome="pending", reason=base[:1000]))
        r.approved = not r.blocking
        reason = base + (" · APPROVED" if r.approved else " · REJECTED: " + "; ".join(r.blocking))
        if r.warnings:
            reason += " · warnings: " + "; ".join(r.warnings)
        self.feed.emit(dict(kind="ceo_decision", id=r.id, agent="risk", strategy=ctx["name"],
                            outcome="approved" if r.approved else "rejected", reason=reason[:1000]))
        for slot in ("scanner", "regime", "strategist", "backtester", "auditor", "risk"):
            self.feed.emit(dict(kind="agent_activity", slot=slot, task=f"{RB} · idle · last: {what} -> {'APPROVED' if r.approved else 'REJECTED'}"[:200], state="idle",
                                strategy=ctx["name"], symbol=ctx["symbol"], progress=None))
        return r
