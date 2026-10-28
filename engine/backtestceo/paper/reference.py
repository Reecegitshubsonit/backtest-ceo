"""Reference backtest stats (results.json from /workspace/backtests, copied as reference_results.json) grouped the
same way as the live-events service (live-events/results.mjs FAMILIES)."""
import json
from pathlib import Path

DEFAULT = Path(__file__).with_name("reference_results.json")
FAMILIES = [
    dict(id="ema200_adx25_trend", name="Grok EMA200 + ADX25 Trend", origin="Alpha Insider", runs=["ai_ema_adx_eth4h", "ai_ema_adx_btc4h"]),
    dict(id="ema150_adx_trend_tuned", name="Grok EMA150 + ADX Trend, source-tuned", origin="Alpha Insider", runs=["ai_ema_adx_eth4h_tuned", "ai_ema_adx_btc1h_tuned"]),
    dict(id="adaptive_supertrend", name="Grok Adaptive SuperTrend Confluence", origin="TC Trading Lab", runs=["supertrend_eth4h", "supertrend_btc4h"]),
    dict(id="ema9_21_cross", name="EMA 9/21 Cross, 2% Stop", origin="PineForge / xAI Grok", runs=["ema9_21_btc1h"]),
    dict(id="first5m_rth_direction", name="First 5-min RTH Candle Direction", origin="RHerman", runs=["first5m_nq", "first5m_qqq"]),
    dict(id="aex_first_hour_vwap", name="AEX First-Hour Range + VWAP", origin="aexopties Grok Bot", runs=["aex_first_hour"]),
    dict(id="stocks_in_play_orb", name="Stocks-in-Play 5-min ORB", origin="Zarattini, Barbon & Aziz (SSRN 4729284)",
         runs=["alpaca_sip_PLTR", "alpaca_sip_TSLA", "alpaca_sip_ARKK"]),
    dict(id="rsi2_pullback", name="RSI(2) Pullback", origin="Connors", runs=["alpaca_rsi2_SMH", "alpaca_rsi2_AMD"]),
    dict(id="overnight_hold", name="Overnight Hold", origin="close -> next open", runs=["alpaca_overnight_NVDA", "alpaca_overnight_MSTR", "alpaca_overnight_LLY"]),
]
# Short wall-screen names for one paper leg (one screen per active strategy x symbol)
LEG_NAMES = {"ema200_adx25_trend": "EMA200 + ADX25 Trend", "adaptive_supertrend": "Adaptive SuperTrend", "ema9_21_cross": "EMA 9/21 Cross",
             "first5m_rth_direction": "First 5-min Candle", "stocks_in_play_orb": "Stocks-in-Play ORB", "rsi2_pullback": "RSI(2) Pullback",
             "overnight_hold": "Overnight Hold"}
STAT_KEYS = ("trades", "win_rate", "profit_factor", "net_return_pct", "max_drawdown_pct", "sharpe", "start", "end")


def _pick(s):
    return {k: s.get(k) for k in STAT_KEYS} if s else None


class Reference:
    def __init__(self, path=DEFAULT):
        doc = json.loads(Path(path).read_text())
        self.generated = doc.get("generated", "")
        self.runs = {r["id"]: r for r in doc["strategies"]}

    def run_stats(self, run_id):
        r = self.runs.get(run_id)
        return None if not r else dict(full=_pick(r["full"]), out_of_sample=_pick(r.get("out_of_sample")), market=r["market"])

    def family_payload(self, fam):
        """The fields the room's wall screens read (same shape as live-events/results.mjs)."""
        runs = [self.runs[i] for i in fam["runs"] if i in self.runs]
        main = runs[0]
        return dict(strategy=fam["id"], name=fam["name"], origin=fam["origin"], market=main["market"], primary_run=main["id"],
                    source_url=main.get("source"), tuned=main.get("tuned"), split_date=main.get("split_date"),
                    stats=_pick(main["full"]), in_sample=_pick(main.get("in_sample")), out_of_sample=_pick(main.get("out_of_sample")),
                    equity=[p["equity"] for p in main.get("equity_curve", [])],
                    trades=[{k: t[k] for k in ("entry_time", "exit_time", "side", "entry", "exit", "ret")} for t in main.get("last_trades", [])],
                    runs=[dict(id=r["id"], market=r["market"], tuned=r.get("tuned"), full=_pick(r["full"]), out_of_sample=_pick(r.get("out_of_sample"))) for r in runs])


    def leg_payload(self, fam, s):
        """One paper leg (strategy x symbol) as its own wall screen: strategy id = the runner key."""
        r = self.runs.get(s.run)
        p = self.family_payload(dict(fam, runs=[s.run])) if r else dict(strategy=fam["id"], name=fam["name"], origin=fam["origin"], market=s.symbol,
                                                                        stats={}, equity=[], trades=[], runs=[])
        tf = f" {s.tf_hours}h" if getattr(s, "tf_hours", 0) else ""
        p.update(strategy=s.key, family=fam["id"], name=f"{LEG_NAMES.get(fam['id'], fam['name'])} · {s.symbol}{tf}",
                 market=f"{s.symbol}{tf} · {'Alpaca paper' if s.broker == 'alpaca' else 'Webull sandbox'}")
        eq = (r or {}).get("equity_curve") or []
        if eq:
            p.update(equity_from=eq[0]["date"], equity_to=eq[-1]["date"])
        return p


def family_of(run_id):
    for f in FAMILIES:
        if run_id in f["runs"]:
            return f
    raise KeyError(run_id)
