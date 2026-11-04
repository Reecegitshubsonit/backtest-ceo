"""Pick Kalshi traders worth copying, from Rivo's public Kalshi leaderboard and trader pages.

kalshi.com sits behind a bot checkpoint and Kalshi's API has no leaderboard endpoint, so the data comes
from rivo.markets. Rivo tracks public, opt-in Kalshi profiles; its robots.txt allows /trader/ pages for AI agents.

Ranking uses Rivo's per-trader "copied $100 per bet, last 90 days" simulation (flat stake, so a whale's
one big bet does not dominate), then charges what Rivo leaves out: the 7% x P x (1-P) taker fee and slippage
from arriving after the leader. Score = t-stat of the net return per bet:
    t = net_return * sqrt(n) / sqrt((1 - p) / p)       p = average entry price
Hard filters drop market makers (one leg of a hedge isn't a pick), inactive accounts, parlay-heavy accounts
(unique combos you can't fill at their price), small samples, and profit concentrated in one win.
"""
from __future__ import annotations

import html
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import requests

BASE = "https://rivo.markets"


def text_of(page: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))


def money(sign: str, s: str) -> float:
    s = s.replace(",", "")
    mult = {"K": 1e3, "M": 1e6}.get(s[-1], 1)
    v = float(s[:-1] if s[-1] in "KM" else s) * mult
    return -v if sign == "-" else v


def leaderboard_names(page: str) -> list[str]:
    return sorted(set(re.findall(r'href="/trader/kalshi/([^"/?#]+)"', page)))


@dataclass
class Trader:
    name: str
    as_of: str = ""
    profit: float = 0.0
    tracked: int = 0
    first_seen: str = ""
    last_trade: str = ""
    wins: int = 0
    losses: int = 0
    avg_entry: float | None = None
    money_traded: float = 0.0
    market_maker: bool = False
    closer: bool = False
    inactive_note: bool = False
    parlay_trades: int = 0
    top_categories: list = field(default_factory=list)
    months: dict = field(default_factory=dict)
    biggest_win: float = 0.0
    # 90-day $100/bet copy simulation (Rivo: no fees, no slippage)
    sim_n: int = 0
    sim_profit: float | None = None
    sim_staked: float = 0.0
    sim_return: float | None = None
    sim_avg_entry: float | None = None
    sim_edge_pts: float | None = None
    sim_profit_factor: float | None = None
    sim_max_losing_streak: int | None = None
    # derived
    net_return: float | None = None
    t_stat: float | None = None
    reasons: list = field(default_factory=list)


def _f(pat: str, t: str, conv=str, default=None):
    m = re.search(pat, t)
    return conv(m.group(1)) if m else default


def parse_trader(name: str, page: str) -> Trader:
    t = text_of(page)
    tr = Trader(name)
    tr.as_of = _f(r"Stats as of ([A-Z][a-z]{2} \d{1,2}, \d{4})", t, default="")
    m = re.search(r"([+-])\$([\d.,]+[KM]?) Tracked Trades ([\d,]+)", t)
    if m:
        tr.profit, tr.tracked = money(m[1], m[2]), int(m[3].replace(",", ""))
    tr.first_seen = _f(r"First Seen ([A-Z][a-z]{2} \d{1,2}, \d{4})", t, default="")
    tr.last_trade = _f(r"Last Trade ([A-Z][a-z]{2} \d{1,2}, \d{4})", t, default="")
    m = re.search(r"([\d,]+) wins and ([\d,]+) losses", t)
    if m:
        tr.wins, tr.losses = int(m[1].replace(",", "")), int(m[2].replace(",", ""))
    tr.avg_entry = _f(r"Avg entry (\d+)¢", t, lambda x: int(x) / 100)
    m = re.search(r"Money traded \$([\d.,]+[KM]?)", t)
    tr.money_traded = money("+", m[1]) if m else 0.0
    tr.market_maker = "Market makers buy both sides" in t
    tr.closer = "This trader is a closer" in t
    tr.inactive_note = bool(re.search(r"No trade since", t))
    cat = re.search(r"Categories Trades Won Profit (.*?) Side taken", t)
    if cat:
        rows = re.findall(r"([A-Za-z][\w &.'/-]*?) (\d+) (?:(\d+)% )?([+-])\$([\d.,]+[KM]?)", cat[1])
        tr.top_categories = [[c.strip(), int(n), money(s, p)] for c, n, _, s, p in rows]
        tr.parlay_trades = sum(n for c, n, _ in tr.top_categories if "parlay" in c.lower())
    mon = re.search(r"Profit by month (.*?)(?: Kalshi leaderboards|$)", t)
    if mon:
        tr.months = {f"{a} {b}": money(s, v) for a, b, s, v in
                     re.findall(r"([A-Z][a-z]{2}) (\d{4}) ([+-])\$([\d.,]+[KM]?)", mon[1])}
    bw = re.search(r"Biggest wins 1 .*? ([+-])\$([\d.,]+[KM]?) ", t)
    tr.biggest_win = money(bw[1], bw[2]) if bw else 0.0
    sim = re.search(r"If you had copied .*?(?:Tracked entries|$)", t)
    if sim and "Nothing to simulate" not in sim[0]:
        s = sim[0]
        m = re.search(r"([+-]?)\$([\d.,]+) Profit on \$([\d.,]+) staked", s)
        if m:
            tr.sim_profit, tr.sim_staked = money(m[1] or "+", m[2]), money("+", m[3])
        tr.sim_return = _f(r"([+-]\d+)% Return", s, lambda x: int(x) / 100)
        tr.sim_n = _f(r"(\d+) settled trades", s, int, 0)
        m = re.search(r"([+-][\d.]+) pts Edge vs implied (\d+)% won at (\d+)¢ avg", s)
        if m:
            tr.sim_edge_pts, tr.sim_avg_entry = float(m[1]), int(m[3]) / 100
        tr.sim_profit_factor = _f(r"([\d.]+)× Profit factor", s, float)
        tr.sim_max_losing_streak = _f(r"Longest losing streak (\d+)", s, int)
        if tr.sim_profit is not None and tr.sim_staked:
            tr.sim_return = tr.sim_profit / tr.sim_staked  # exact, not the rounded %
    return tr


@dataclass
class Rules:
    slippage: float = 0.02          # $ per contract lost to arriving after the leader
    taker_fee_rate: float = 0.07
    min_sim_trades: int = 40
    max_avg_entry: float = 0.93     # above this, 2c slippage eats the edge
    max_parlay_share: float = 0.15
    min_avg_entry: float = 0.15     # lottery tickets: a few hits make the sim, slippage kills the copy
    max_sim_return: float = 1.0     # >100% per $ staked in 90 days = driven by a handful of longshots
    max_top_win_share: float = 0.40
    max_days_idle: int = 14
    min_t: float = 1.0
    min_green_months: float = 0.6   # share of months with positive profit
    max_month_share: float = 0.70   # best month's share of lifetime profit


def _date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%b %d, %Y")
    except (TypeError, ValueError):
        return None


def score(tr: Trader, r: Rules) -> Trader:
    why = tr.reasons
    if tr.market_maker:
        why.append("market maker")
    a, b = _date(tr.as_of), _date(tr.last_trade)
    if tr.inactive_note or (a and b and (a - b).days > r.max_days_idle):
        why.append(f"idle since {tr.last_trade}")
    if tr.tracked and tr.parlay_trades / tr.tracked > r.max_parlay_share:
        why.append(f"parlays {tr.parlay_trades}/{tr.tracked}")
    if tr.profit > 0 and tr.biggest_win / tr.profit > r.max_top_win_share:
        why.append(f"one win = {tr.biggest_win / tr.profit:.0%} of profit")
    if tr.months:
        vals = list(tr.months.values())
        if sum(v > 0 for v in vals) / len(vals) < r.min_green_months:
            why.append(f"green months {sum(v > 0 for v in vals)}/{len(vals)}")
        if tr.profit > 0 and max(vals) / tr.profit > r.max_month_share:
            why.append(f"best month = {max(vals) / tr.profit:.0%} of profit")
    if tr.sim_return is None or not tr.sim_avg_entry:
        why.append("no 90d copy sim")
        return tr
    p = tr.sim_avg_entry
    if tr.sim_n < r.min_sim_trades:
        why.append(f"only {tr.sim_n} sim trades")
    if not r.min_avg_entry <= p <= r.max_avg_entry:
        why.append(f"avg entry {p:.2f}")
    if tr.sim_return > r.max_sim_return:
        why.append(f"sim {tr.sim_return:+.0%} is longshot-driven")
    fee_pct = r.taker_fee_rate * (1 - p)  # fee per $ staked
    tr.net_return = tr.sim_return - fee_pct - r.slippage / p
    if tr.sim_n:
        tr.t_stat = tr.net_return * math.sqrt(tr.sim_n) / math.sqrt((1 - p) / p)
    if tr.net_return <= 0:
        why.append(f"net copy return {tr.net_return:+.1%}")
    elif tr.t_stat is not None and tr.t_stat < r.min_t:
        why.append(f"t={tr.t_stat:.2f} (noise)")
    return tr


def fetch(names: list[str] | None, cache: Path, delay: float = 1.5, refresh: bool = False) -> dict[str, str]:
    cache.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    lb = cache / "_leaderboard.html"
    if refresh or not lb.exists():
        lb.write_text(s.get(f"{BASE}/kalshi-leaderboard", timeout=30).text)
    names = names or leaderboard_names(lb.read_text())
    pages = {}
    for n in names:
        f = cache / f"{n}.html"
        if refresh or not f.exists():
            r = s.get(f"{BASE}/trader/kalshi/{n}", timeout=30)
            if r.status_code != 200:
                continue
            f.write_text(r.text)
            time.sleep(delay)
        pages[n] = f.read_text()
    return pages


def rank(pages: dict[str, str], rules: Rules) -> tuple[list[Trader], list[Trader]]:
    scored = [score(parse_trader(n, p), rules) for n, p in pages.items()]
    keep = sorted((t for t in scored if not t.reasons), key=lambda t: -(t.t_stat or 0))
    drop = [t for t in scored if t.reasons]
    return keep, drop


def write_config(keep: list[Trader], path: Path, top: int, example: Path | None = None) -> dict:
    base = json.loads(example.read_text()) if example and example.exists() else {}
    if path.exists():
        base = json.loads(path.read_text())
    base["traders"] = {t.name.lower(): 1.0 for t in keep[:top]}
    path.write_text(json.dumps(base, indent=1))
    return base


def report(keep: list[Trader], drop: list[Trader], top: int) -> str:
    out = [f"{len(keep)} pass / {len(drop)} filtered\n",
           f"{'trader':26} {'n90':>4} {'entry':>5} {'sim':>6} {'net':>6} {'t':>5} {'PF':>5} {'lifetime':>9}  top category"]
    for t in keep[:top]:
        cat = t.top_categories[0][0] if t.top_categories else ""
        out.append(f"{t.name[:26]:26} {t.sim_n:4d} {t.sim_avg_entry:5.2f} {t.sim_return:+6.1%} {t.net_return:+6.1%} "
                   f"{t.t_stat:5.2f} {t.sim_profit_factor or 0:5.2f} {t.profit:+9,.0f}  {cat}")
    return "\n".join(out)


def dump(keep: list[Trader], drop: list[Trader], path: Path) -> None:
    path.write_text(json.dumps({"keep": [asdict(t) for t in keep], "drop": [asdict(t) for t in drop]}, indent=1))


# -- re-score on the trades the Rivo feed actually carries ($1,000+) ----------------------------
API = "https://api.rivo.markets/v2"


def api_trades(key: str, trader: str, since_iso: str, max_rows: int = 120, session=None) -> list[dict]:
    """A trader's Kalshi buys from Rivo's API (only $1,000+ trades exist there), newest first."""
    s = session or requests.Session()
    rows, cursor = [], None
    while len(rows) < max_rows:
        p = {"venue": "kalshi", "trader": f"kalshi:{trader}", "action": "buy", "since": since_iso,
             "limit": min(200, max_rows - len(rows))}
        if cursor:
            p["cursor"] = cursor
        r = s.get(f"{API}/trades", params=p, headers={"Authorization": f"Bearer {key}"}, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after", 10)))
            continue
        r.raise_for_status()
        body = r.json()
        rows += body.get("data") or []
        cursor = body.get("nextCursor")
        if not cursor:
            break
    return rows


@dataclass
class FeedScore:
    name: str
    bets: int = 0            # settled market+side groups in the price band
    open_bets: int = 0
    avg_price: float = 0.0
    win_rate: float = 0.0
    gross: float = 0.0       # mean return per $1 staked per bet, before costs
    net: float = 0.0         # after taker fee and slippage
    t: float = 0.0
    usd: float = 0.0
    reasons: list = field(default_factory=list)


def score_feed(name: str, rows: list[dict], rules: Rules, price_band=(0.10, 0.95), min_bets: int = 12) -> FeedScore:
    """One bet per (market, side): usd-weighted entry, held to settlement, $1 flat stake per bet."""
    groups: dict[tuple, dict] = {}
    for x in rows:
        m = x.get("market") or {}
        tick, p, usd = m.get("venueId"), x.get("price"), x.get("usd") or 0
        if not tick or p is None or m.get("kind") == "parlay" or tick.startswith("KXMVE"):
            continue
        g = groups.setdefault((tick, x.get("outcome")), {"usd": 0.0, "pw": 0.0, "result": x.get("result")})
        g["usd"] += usd
        g["pw"] += p * usd
        if x.get("result") in ("win", "loss", "void"):
            g["result"] = x["result"]
    fs = FeedScore(name)
    rets, prices, wins = [], [], 0
    for g in groups.values():
        if not g["usd"]:
            continue
        p = g["pw"] / g["usd"]
        if not price_band[0] <= p <= price_band[1]:
            continue
        if g["result"] not in ("win", "loss"):
            fs.open_bets += g["result"] == "open"
            continue
        gross = (1 - p) / p if g["result"] == "win" else -1.0
        rets.append((gross, p))
        prices.append(p)
        wins += g["result"] == "win"
        fs.usd += g["usd"]
    fs.bets = len(rets)
    if fs.bets < min_bets:
        fs.reasons.append(f"only {fs.bets} settled $1K+ bets")
        return fs
    net = [r - rules.taker_fee_rate * (1 - p) - rules.slippage / p for r, p in rets]
    fs.avg_price = sum(prices) / fs.bets
    fs.win_rate = wins / fs.bets
    fs.gross = sum(r for r, _ in rets) / fs.bets
    fs.net = sum(net) / fs.bets
    sd = math.sqrt(sum((v - fs.net) ** 2 for v in net) / (fs.bets - 1)) or 1e-9
    fs.t = fs.net / sd * math.sqrt(fs.bets)
    if fs.net <= 0:
        fs.reasons.append(f"net {fs.net:+.1%}")
    elif fs.t < rules.min_t:
        fs.reasons.append(f"t={fs.t:.2f} (noise)")
    return fs


def feed_report(scores: list[FeedScore], top: int) -> str:
    keep = sorted((s for s in scores if not s.reasons), key=lambda s: -s.t)
    out = [f"{len(keep)} pass / {len(scores) - len(keep)} filtered (only $1,000+ trades, last 30 days)\n",
           f"{'trader':26} {'bets':>4} {'open':>4} {'price':>5} {'win%':>5} {'gross':>7} {'net':>7} {'t':>5} {'$ staked':>10}"]
    for s in keep[:top]:
        out.append(f"{s.name[:26]:26} {s.bets:4d} {s.open_bets:4d} {s.avg_price:5.2f} {s.win_rate:5.0%} "
                   f"{s.gross:+7.1%} {s.net:+7.1%} {s.t:5.2f} {s.usd:10,.0f}")
    return "\n".join(out)
