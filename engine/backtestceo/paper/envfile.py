"""Reads only the named variables from a .env file (e.g. ~/backtest-ceo/.env -> ~/Desktop/API_KEYS.env).
The file is opened read-only and never written, copied or logged."""
from pathlib import Path

ALPACA_KEY_VARS = ("ALPACA_PAPER_API_KEY", "ALPACA_API_KEY", "APCA_API_KEY_ID")
ALPACA_SECRET_VARS = ("ALPACA_PAPER_SECRET_KEY", "ALPACA_SECRET_KEY", "APCA_API_SECRET_KEY")
WEBULL_KEY_VARS = ("WEBULL_APP_KEY", "WEBULL_API_KEY")
WEBULL_SECRET_VARS = ("WEBULL_APP_SECRET", "WEBULL_API_SECRET", "WEBULL_SECRET_KEY")
WEBULL_ACCOUNT_VARS = ("WEBULL_ACCOUNT_ID",)
FLAG_VARS = ("WEBULL_ENV", "ALPACA_PAPER_TRADING_ONLY", "PAPER_TRADING_KILL_SWITCH", "WEBULL_REGION",
             "ALPACA_BASE_URL", "APCA_API_BASE_URL", "ALPACA_PAPER_BASE_URL", "ALPACA_ENDPOINT",
             "WEBULL_ENDPOINT", "WEBULL_API_ENDPOINT", "WEBULL_HOST", "ALPACA_DATA_FEED")
NAMES = ALPACA_KEY_VARS + ALPACA_SECRET_VARS + WEBULL_KEY_VARS + WEBULL_SECRET_VARS + WEBULL_ACCOUNT_VARS + FLAG_VARS


def read(path, names=NAMES) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {}
    want, out = set(names), {}
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            if s.startswith("export "):
                s = s[7:]
            k, v = s.split("=", 1)
            k = k.strip()
            if k in want:
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                    v = v[1:-1]
                out[k] = v
    return out


class Env(dict):
    """Effective settings: process environment first, then the .env file. repr() never shows values."""

    def __repr__(self):
        return f"Env({sorted(k for k, v in self.items() if v)})"

    __str__ = __repr__

    def first(self, names):
        for n in names:
            if self.get(n):
                return self[n]
        return ""


def load(path, environ) -> Env:
    e = Env(read(path))
    for k in NAMES:
        if environ.get(k):
            e[k] = environ[k]
    return e
