"""Backtest: news-first universe -> per-minute scanner -> pullback setups -> simulated stop-limit fills on 1-min bars.

    python -m backtestceo.momentum backtest --days 60 [--set key=value ...] [--out DIR]
    python -m backtestceo.momentum sweep --days 60      # sensitivity table over a few documented variants
"""
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Config
from .data import ET, Data, parse_t
from .engine import is_catalyst, Bar, Position, SymbolState, hhmm, sim_bar, sim_entry, size, slip

SYMBOL_RE = re.compile(r"^[A-Z]{1,5}$")


def tradable_symbol(s: str) -> bool:
    # drop warrants / units / rights (5-letter ...W/U/R) and anything with a class suffix
    return bool(SYMBOL_RE.match(s)) and not (len(s) == 5 and s[-1] in "WUR")


def to_bars(rows) -> list[Bar]:
    return [Bar(parse_t(r["t"]).astimezone(ET), r["o"], r["h"], r["l"], r["c"], r["v"]) for r in rows]


# ------------------------------------------------------------------ universe
def build_universe(data: Data, days: list[date], prev: dict, cfg: Config, log=print):
    """Return {day: [(sym, prev_close, adv, news[(t, headline)])]} for symbols that pass necessary daily conditions.

    The day-D daily bar is only used to skip downloading minute bars for symbols that could not possibly qualify
    (high < prev close +gap%, or never inside the price band). Qualification itself is minute by minute, no lookahead.
    """
    news_by_day, syms = {}, set()
    for d in days:
        per = defaultdict(list)
        for n in data.news_for_day(d, prev[d], "11:30"):
            ok = not cfg.require_news or is_catalyst(n["headline"], n["symbols"], cfg)
            for s in n["symbols"]:
                if tradable_symbol(s):
                    syms.add(s)  # daily bars for every news symbol (one cache for all catalyst-filter settings)
                    if ok:
                        per[s].append((parse_t(n["t"]).astimezone(ET), n["headline"]))
        news_by_day[d] = per
    syms = sorted(syms)
    start, end = days[0] - timedelta(days=int(cfg.adv_days * 1.6) + 10), days[-1]
    tag = f"news{len(syms)}_" + hashlib.sha1(",".join(syms).encode()).hexdigest()[:10]
    log(f"universe: {len(syms)} news symbols; daily bars {start}..{end}")
    raw = data.daily_cached(syms, start, end, "raw", tag)
    adj = data.daily_cached(syms, start, end, "split", tag)
    out = {d: [] for d in days}
    for s in syms:
        r = {parse_t(b["t"]).astimezone(ET).date(): b for b in raw.get(s, [])}
        a = [(parse_t(b["t"]).astimezone(ET).date(), b) for b in adj.get(s, [])]
        idx = {dd: k for k, (dd, _) in enumerate(a)}
        for d in days:
            if s not in news_by_day[d] or d not in r or d not in idx:
                continue
            k = idx[d]
            hist = a[max(0, k - cfg.adv_days):k]
            if len(hist) < cfg.min_history_days or hist[-1][0] != prev[d]:
                continue
            f = r[d]["c"] / a[k][1]["c"] if a[k][1]["c"] else 1.0  # raw/adjusted price factor on d
            pc = hist[-1][1]["c"] * f
            adv = sum(b["v"] for _, b in hist) / len(hist) / f
            rd = r[d]
            if rd["h"] < pc * (1 + cfg.min_gap_pct / 100) or rd["h"] < cfg.min_price or rd["l"] > cfg.max_price:
                continue
            out[d].append((s, pc, adv, news_by_day[d][s]))
    return out


# ------------------------------------------------------------------ one day
class Risk:
    def __init__(self, cfg: Config):
        self.cfg, self.pnl, self.consec, self.cold, self.trades, self.halted = cfg, 0.0, 0, False, 0, ""

    def mult(self) -> float:
        return self.cfg.cold_size_mult if self.cold else 1.0

    def can_trade(self) -> bool:
        return not self.halted and self.trades < self.cfg.max_trades_per_day

    def closed(self, pnl: float) -> None:
        self.pnl += pnl
        if pnl < 0:
            self.consec, self.cold = self.consec + 1, True
        else:
            self.consec, self.cold = 0, False
        if self.pnl <= -self.cfg.daily_max_loss:
            self.halted = "daily_max_loss"
        elif self.consec >= self.cfg.max_consecutive_losses:
            self.halted = "consecutive_losses"


def trade_row(d: date, p: Position, st: SymbolState) -> dict:
    news = st.catalyst(p.t_entry)
    pnl = p.pnl()
    return {"date": str(d), "symbol": p.sym, "pattern": p.setup.pattern, "entry_time": p.t_entry.strftime("%H:%M"),
            "entry": round(p.entry, 4), "stop": p.init_stop, "shares": p.shares, "risk_usd": round(p.r * p.shares, 2),
            "exit_time": p.fills[-1][0].strftime("%H:%M") if p.fills else "",
            "avg_exit": round(sum(px * q for _, px, q, _ in p.fills) / max(1, sum(q for *_, q, _ in p.fills)), 4),
            "exit_reasons": "+".join(f[3] for f in p.fills), "pnl": round(pnl, 2),
            "r_multiple": round(pnl / (p.r * p.shares), 2) if p.r * p.shares else 0.0,
            "gap_pct": round(p.setup.gap_pct, 1), "rvol": round(p.setup.rvol, 1),
            "in_play_at": st.in_play_at.strftime("%H:%M") if st.in_play_at else "",
            "catalyst": (news[1][:120] if news else "")}


def run_day(d: date, cands, minute: dict, cfg: Config):
    states = {s: SymbolState(s, pc, adv, news, cfg) for s, pc, adv, news in cands}
    events = []
    for s in states:
        for b in to_bars(minute.get(s, [])):
            events.append((b.t, s, b))
    events.sort(key=lambda e: (e[0], e[1]))
    risk, pending, open_pos, trades = Risk(cfg), {}, {}, []
    e_from, e_until, flat = hhmm(cfg.entry_from), hhmm(cfg.entry_until), hhmm(cfg.flatten_at)

    def finish(s):
        p = open_pos.pop(s)
        risk.closed(p.pnl())
        trades.append(trade_row(d, p, states[s]))

    k = 0
    while k < len(events):
        t = events[k][0]
        group = []
        while k < len(events) and events[k][0] == t:
            group.append(events[k])
            k += 1
        # 1) manage open positions intrabar
        for _, s, b in group:
            if s in open_pos:
                p = open_pos[s]
                if t.time() >= flat:
                    p.exit(t, b.o - slip(b.o, cfg), p.remaining, "flatten")
                else:
                    sim_bar(p, b, cfg, entry_bar=False)
        # 2) entries from setups armed at the previous close (strongest rvol first)
        for _, s, b in sorted(group, key=lambda e: -states[e[1]].rvol_now):
            st, su = states[s], pending.pop(s, None)
            if su is None or s in open_pos or not (e_from <= t.time() <= e_until):
                continue
            if not risk.can_trade() or len(open_pos) >= cfg.max_positions or st.entries >= cfg.max_entries_per_symbol:
                continue
            fill = sim_entry(su, b, cfg)
            if fill is None or fill <= su.stop:
                continue
            q = size(su, st, cfg, risk.mult())
            if q < 1:
                continue
            p = Position(s, su.pattern, fill, su.stop, q, t, su)
            st.entries += 1
            risk.trades += 1
            open_pos[s] = p
            sim_bar(p, b, cfg, entry_bar=True)
        # 3) bar close: indicators, bar-close exits, next setups
        for _, s, b in group:
            st = states[s]
            st.update(b)
            p = open_pos.get(s)
            if p and p.remaining > 0:
                why = p.on_close(b, st, cfg)
                if why:
                    p.exit(t, b.c - slip(b.c, cfg), p.remaining, why)
            if p and p.remaining <= 0:
                finish(s)
            pending.pop(s, None)
            if s not in open_pos:
                su = st.setup()
                if su:
                    pending[s] = su
    for s in list(open_pos):
        p = open_pos[s]
        last = states[s].bars[-1]
        p.exit(last.t, last.c - slip(last.c, cfg), p.remaining, "eod")
        finish(s)
    scanned = [{"date": str(d), "symbol": s, "in_play_at": st.in_play_at.strftime("%H:%M"),
                "gap_open_pct": round(next((st.gap_pct(b.o) for b in st.bars if b.t.time() >= hhmm("09:30")), 0), 1)}
               for s, st in states.items() if st.in_play_at]
    return trades, scanned, risk.halted


# ------------------------------------------------------------------ driver
def sessions(data: Data, n: int, end: date | None = None):
    end = end or date.today()
    all_days = data.trading_days(end - timedelta(days=int(n * 1.6) + 15), end)
    if all_days and all_days[-1] == datetime.now(ET).date() and datetime.now(ET).time() < hhmm("12:20"):
        all_days = all_days[:-1]  # today's morning window not finished yet
    days = all_days[-n:]
    prev = {all_days[i]: all_days[i - 1] for i in range(1, len(all_days))}
    return days, prev


def prepare(data: Data, n_days: int, cfg: Config, end: date | None = None, log=print):
    days, prev = sessions(data, n_days, end)
    uni = build_universe(data, days, prev, cfg, log)
    minute = {}
    for d in days:
        syms = [c[0] for c in uni[d]]
        minute[d] = data.minute(syms, d, "04:00", "12:00") if syms else {}
    log(f"{len(days)} sessions {days[0]}..{days[-1]}; {sum(len(v) for v in uni.values())} candidate symbol-days")
    return days, uni, minute


def run(days, uni, minute, cfg: Config):
    trades, scanned, halts = [], [], {}
    for d in days:
        t, sc, h = run_day(d, uni[d], minute[d], cfg)
        trades += t
        scanned += sc
        if h:
            halts[str(d)] = h
    return trades, scanned, halts


def stats(trades: list[dict], days, cfg: Config) -> dict:
    pnl = [t["pnl"] for t in trades]
    wins, losses = [x for x in pnl if x > 0], [x for x in pnl if x <= 0]
    by_day = defaultdict(float)
    for t in trades:
        by_day[t["date"]] += t["pnl"]
    eq, peak, dd = 0.0, 0.0, 0.0
    for d in days:
        eq += by_day.get(str(d), 0.0)
        peak = max(peak, eq)
        dd = min(dd, eq - peak)

    def grp(key):
        g = defaultdict(list)
        for t in trades:
            g[key(t)].append(t)
        return {k: {"trades": len(v), "pnl": round(sum(x["pnl"] for x in v), 2),
                    "win_rate": round(sum(x["pnl"] > 0 for x in v) / len(v), 3),
                    "avg_r": round(sum(x["r_multiple"] for x in v) / len(v), 2)} for k, v in sorted(g.items())}

    def bucket(t):
        h = t["entry_time"]
        for lim, name in (("09:30", "07:00-09:30 pre"), ("10:00", "09:30-10:00"), ("10:30", "10:00-10:30"), ("23:59", "10:30-11:00")):
            if h < lim:
                return name

    green = [v for v in by_day.values() if v > 0]
    return {"sessions": len(days), "first": str(days[0]), "last": str(days[-1]), "trades": len(trades),
            "days_traded": len(by_day), "green_days": len(green), "net_pnl": round(sum(pnl), 2),
            "net_pnl_pct_equity": round(sum(pnl) / cfg.equity * 100, 2),
            "win_rate": round(len(wins) / len(pnl), 3) if pnl else 0.0,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
            "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
            "avg_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 3) if trades else 0.0,
            "expectancy_usd": round(sum(pnl) / len(pnl), 2) if pnl else 0.0,
            "max_drawdown_usd": round(dd, 2), "by_pattern": grp(lambda t: t["pattern"]), "by_time": grp(bucket),
            "by_exit": grp(lambda t: t["exit_reasons"].split("+")[-1])}


def write(out: Path, cfg: Config, trades, scanned, halts, st) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"stats": st, "halts": halts, "config": cfg.__dict__}, indent=2, default=list))
    for name, rows in (("trades.csv", trades), ("scanner_hits.csv", scanned)):
        with open(out / name, "w", newline="") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)


def fmt(st: dict) -> str:
    keys = ("sessions", "trades", "days_traded", "green_days", "net_pnl", "win_rate", "avg_win", "avg_loss",
            "profit_factor", "avg_r", "expectancy_usd", "max_drawdown_usd")
    lines = [" ".join(f"{k}={st[k]}" for k in keys)]
    for g in ("by_pattern", "by_time", "by_exit"):
        lines.append(f"  {g}: " + "; ".join(f"{k}: n={v['trades']} pnl={v['pnl']} wr={v['win_rate']} R={v['avg_r']}"
                                          for k, v in st[g].items()))
    return "\n".join(lines)


SWEEP = {
    "default": {},
    "premarket entries 07:00": {"entry_from": "07:00"},
    "micro_pullback only": {"patterns": ("micro_pullback",)},
    "bull_flag only": {"patterns": ("bull_flag",)},
    "first_pullback only": {"patterns": ("first_pullback",)},
    "slippage 0.5%/side": {"slippage_pct": 0.5},
    "slippage 0%": {"slippage_pct": 0.0},
    "entries until 10:00": {"entry_until": "10:00"},
    "target 3R": {"target_r": 3.0},
    "entries until 10:30": {"entry_until": "10:30"},
    "no bailout exit": {"bailout_bars": 0},
    "rvol >= 3": {"min_rvol": 3.0},
    "rvol >= 10": {"min_rvol": 10.0},
    "gap >= 20%": {"min_gap_pct": 20.0},
    "price $2-10": {"max_price": 10.0},
}
