"""Runner configuration: which strategies run where, and the hard per-strategy caps. Override with --config file.json
(same keys). Caps can only be tightened by a config file, never loosened past HARD_LIMITS."""
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

HARD_LIMITS = dict(max_open_positions=1, max_notional_usd=2500.0, max_entries_per_day=6, max_entries_per_day_total=24)


@dataclass(frozen=True)
class StrategyConfig:
    key: str            # runner id
    run: str            # results.json run id (reference stats)
    rule: str           # alphainsider | supertrend | emacross | first5m
    broker: str         # alpaca | webull
    symbol: str
    tf_hours: int = 0   # bar strategies: 1 or 4 (built from 1h bars like backtest.py's resample)
    enabled: bool = True


@dataclass(frozen=True)
class Caps:
    max_open_positions: int = 1
    max_notional_usd: float = 2000.0
    max_entries_per_day: int = 4         # per strategy, US/Eastern calendar day
    max_entries_per_day_total: int = 16


@dataclass(frozen=True)
class RunnerConfig:
    strategies: tuple = field(default_factory=lambda: (
        StrategyConfig("supertrend_eth4h", "supertrend_eth4h", "supertrend", "alpaca", "ETH/USD", 4),
        StrategyConfig("supertrend_btc4h", "supertrend_btc4h", "supertrend", "alpaca", "BTC/USD", 4),
        StrategyConfig("ai_ema_adx_eth4h", "ai_ema_adx_eth4h", "alphainsider", "alpaca", "ETH/USD", 4),
        StrategyConfig("ai_ema_adx_btc4h", "ai_ema_adx_btc4h", "alphainsider", "alpaca", "BTC/USD", 4),
        StrategyConfig("ema9_21_btc1h", "ema9_21_btc1h", "emacross", "alpaca", "BTC/USD", 1),
        StrategyConfig("first5m_qqq", "first5m_qqq", "first5m", "webull", "QQQ"),
    ))
    backtest_only: tuple = ("first5m_nq", "aex_first_hour", "ai_ema_adx_eth4h_tuned", "ai_ema_adx_btc1h_tuned")
    caps: Caps = field(default_factory=Caps)
    poll_seconds: float = 30.0
    lookback_hours: int = 4800           # 1h bars fetched for crypto (1200 x 4h bars of indicator warm-up)
    first5m_risk_usd: float = 200.0      # backtest.py's fixed $ risk, then capped by max_notional_usd
    first5m_exit_et: str = "15:58"       # backtest exits at the 15:55 bar close (16:00); orders need the session open
    live_events_url: str = "http://127.0.0.1:8030"

    def to_dict(self):
        return asdict(self)


def load(path=None) -> RunnerConfig:
    cfg = RunnerConfig()
    if not path:
        return cfg
    raw = json.loads(Path(path).read_text())
    caps = replace(cfg.caps, **raw.pop("caps", {}))
    for k, hard in HARD_LIMITS.items():
        if getattr(caps, k) > hard:
            raise ValueError(f"caps.{k}={getattr(caps, k)} exceeds the hard limit {hard}")
    strategies = tuple(StrategyConfig(**s) for s in raw.pop("strategies")) if "strategies" in raw else cfg.strategies
    for s in strategies:
        if s.broker not in ("alpaca", "webull"):
            raise ValueError(f"{s.key}: unknown broker {s.broker}")
    return replace(cfg, caps=caps, strategies=strategies, **raw)
