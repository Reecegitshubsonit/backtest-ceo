"""Scan Kalshi temperature markets against the forecast model and trade (paper or live)."""
from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from kalshibot.client import KalshiClient, KalshiError
from kalshibot.model import count, fee, parse_time, price, r2
from kalshibot.paper import Journal, Position, State, settle

from . import forecast as fc
from .model import WxConfig, bracket_prob, distribution
from .stations import DEFAULT_SERIES, STATIONS, kind_from_rules, station_from_rules

MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def event_date(event_ticker: str) -> date | None:
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker or "")
    if not m or m.group(2) not in MONTHS:
        return None
    return date(2000 + int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))


def local_std_today(std_utc: int, now: datetime) -> date:
    return (now + timedelta(hours=std_utc)).date()


@dataclass
class Opp:
    ticker: str
    event: str
    station: str
    measure: str  # "high" or "low"
    day: str
    lead: int
    label: str
    side: str
    ask: float
    p_model: float
    edge: float
    mu: float
    sd: float
    observed: float | None
    ask_size: float
    hours_left: float


def scan(client: KalshiClient, cfg: WxConfig, now: datetime | None = None, session=None, log=print) -> list[Opp]:
    now = now or datetime.now(timezone.utc)
    cal = cfg.calibration()
    nws_cache: dict = {}
    out: list[Opp] = []
    for series in cfg.series or DEFAULT_SERIES:
        try:
            markets = list(client.markets(series_ticker=series, status="open"))
        except KalshiError as e:
            log(f"{series}: {e}")
            continue
        events: dict[str, list[dict]] = {}
        for m in markets:
            events.setdefault(m.get("event_ticker", ""), []).append(m)
        for ev, ms in events.items():
            code = station_from_rules(ms[0].get("rules_primary", ""))
            kind = kind_from_rules(ms[0].get("rules_primary", ""))
            day = event_date(ev)
            if not (code and kind and day):
                continue
            icao, lat, lon, std, _ = STATIONS[code]
            lead = (day - local_std_today(std, now)).days
            if not cfg.min_lead_days <= lead <= cfg.max_lead_days:
                continue
            members = list(fc.model_extremes(lat, lon, day, std, kind, session=session).values())
            if len(members) < len(fc.DET_MODELS):
                log(f"{code} {day}: model forecast incomplete")
                continue
            obs = None
            if lead == 0:
                try:
                    obs = fc.observed_extreme(icao, day, std, kind, now=now, session=session)
                except Exception as e:
                    log(f"{icao}: observations failed: {e}")
            mu, sd = distribution(members, lead, kind, cfg, cal.get(code))
            nws = None
            if kind == "high" and cfg.nws_weight > 0:
                try:
                    nws = fc.nws_forecast_high(lat, lon, day, session=session, cache=nws_cache)
                except Exception as e:
                    log(f"{icao}: NWS forecast failed: {e}")
                if nws is not None:
                    mu = cfg.nws_weight * nws + (1 - cfg.nws_weight) * mu
            for m in ms:
                ct = parse_time(m.get("close_time"))
                hours_left = (ct - now).total_seconds() / 3600 if ct else 0
                if hours_left < cfg.min_hours_left or count(m, "volume_24h") < cfg.min_volume_24h:
                    continue
                p = bracket_prob(m.get("strike_type", ""), m.get("floor_strike"), m.get("cap_strike"), mu, sd, obs, kind)
                if p is None:
                    continue
                yb, ya = price(m, "yes_bid"), price(m, "yes_ask")
                if yb is None or ya is None:
                    continue
                mid = (yb + ya) / 2
                p = cfg.model_weight * p + (1 - cfg.model_weight) * mid  # lean on the market
                best = None
                for side, p_side, ask, size in (("yes", p, ya, count(m, "yes_ask_size")),
                                                ("no", 1 - p, price(m, "no_ask"), count(m, "no_ask_size"))):
                    if not ask or not cfg.min_price <= ask <= cfg.max_price:
                        continue
                    edge = p_side - ask - fee(100, ask, cfg.taker_fee_rate) / 100
                    if edge > cfg.max_edge:
                        log(f"{m['ticker']} {side}: edge {edge:+.2f} too large, treating as model error "
                            f"(mu {mu:.1f}, nws {nws}, ask {ask:.2f})")
                        continue
                    if edge >= cfg.min_edge and (best is None or edge > best.edge):
                        best = Opp(m["ticker"], ev, code, kind, day.isoformat(), lead, m.get("yes_sub_title", ""),
                                   side, ask, round(p_side, 4), round(edge, 4), round(mu, 2), round(sd, 2),
                                   None if obs is None else round(obs, 1), size, round(hours_left, 1))
                if best:
                    out.append(best)
    return sorted(out, key=lambda o: -o.edge)


class WxTrader:
    def __init__(self, client: KalshiClient, cfg: WxConfig, data_dir: Path, live: bool = False):
        if live and not (cfg.live and client.allow_trading):
            raise SystemExit('live needs "live": true in weather_config.json, --live, and Kalshi API keys')
        self.client, self.cfg, self.live = client, cfg, live
        tag = "live" if live else "paper"
        self.state_path = data_dir / f"wx_{tag}_state.json"
        self.state = State.load(self.state_path, cfg.starting_cash)
        self.log = Journal(data_dir / f"wx_{tag}_journal.jsonl")

    def exposure(self, event: str | None = None) -> float:
        return sum(p.cost for p in self.state.positions.values() if event is None or p.event_ticker == event)

    def take(self, o: Opp) -> dict:
        cfg, st, now = self.cfg, self.state, int(time.time())
        if o.ticker in st.positions:
            return {"result": "skip", "reason": "already_holding", "ticker": o.ticker}
        if self.live:
            if Path(cfg.kill_file).exists():
                return {"result": "skip", "reason": "kill_switch", "ticker": o.ticker}
            st.cash = self.client.balance_usd()
        unit = o.ask + fee(100, o.ask, cfg.taker_fee_rate) / 100
        budget = min(cfg.usd_per_bet, cfg.max_per_market, cfg.max_per_event - self.exposure(o.event),
                     cfg.max_total_exposure - self.exposure(), st.cash)
        n = int(min(budget / unit, o.ask_size or 0))
        if n < 1:
            return {"result": "skip", "reason": "no_room_or_liquidity", "ticker": o.ticker}
        fill, f, order_id = o.ask, fee(n, o.ask, cfg.taker_fee_rate), None
        if self.live:
            try:
                ok, note = self.client.ensure_shard_funds(o.ticker, n * o.ask + f + 0.02)
            except KalshiError as e:
                ok, note = False, str(e)
            if not ok:
                return {"result": "skip", "reason": "shard_funding", "ticker": o.ticker, "err": note}
            try:
                res = (self.client.create_order(o.ticker, "bid", n, o.ask) if o.side == "yes"
                       else self.client.create_order(o.ticker, "ask", n, r2(1 - o.ask)))
            except KalshiError as e:
                self.log("order_error", ts=now, ticker=o.ticker, err=str(e))
                return {"result": "skip", "reason": "order_error", "ticker": o.ticker, "err": str(e)}
            self.log("order", ts=now, ticker=o.ticker, side=o.side, n=n, price=o.ask, response=res)
            got = int(float(res.get("fill_count") or 0))
            if got < 1:
                return {"result": "skip", "reason": "no_fill", "ticker": o.ticker}
            yes_px = float(res.get("average_fill_price") or (o.ask if o.side == "yes" else 1 - o.ask))
            fill = yes_px if o.side == "yes" else r2(1 - yes_px)
            f = round(float(res.get("average_fee_paid") or 0) * got, 4)
            n, order_id = got, res.get("order_id")
        cost = r2(n * fill + f)
        st.cash = r2(st.cash - cost)
        st.positions[o.ticker] = Position(o.ticker, o.event, o.side, n, cost)
        out = {"result": "bought", "live": self.live, "order_id": order_id, **asdict(o), "contracts": n,
               "fill": fill, "fee": f, "cost": cost}
        self.log("buy", ts=now, **out)
        return out

    def settle_all(self) -> None:
        now = int(time.time())
        for t in list(self.state.positions):
            try:
                settle(self.state, self.client.market(t), now, self.log)
            except KalshiError as e:
                self.log("error", ts=now, ticker=t, err=str(e))

    def cycle(self, session=None) -> list[dict]:
        self.settle_all()
        opps = scan(self.client, self.cfg, session=session)
        self.log("scan", ts=int(time.time()), n=len(opps), top=[asdict(o) for o in opps[:5]])
        results = [self.take(o) for o in opps]
        self.state.save(self.state_path)
        return results
