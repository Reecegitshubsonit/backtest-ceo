from dataclasses import dataclass

ASSETS = ("stocks", "etfs", "crypto", "options")
TIMEFRAMES = ("1Min", "5Min", "15Min", "1Hour", "1Day")


@dataclass(frozen=True)
class Bar:
    """One OHLCV bar. `t` is the bar start in UTC, ISO 8601, as Alpaca sends it."""
    t: str
    o: float
    h: float
    l: float
    c: float
    v: float


def parse_rows(rows: list[dict]) -> list[Bar]:
    return [Bar(r["t"], float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r.get("v", 0))) for r in rows]


class DataError(Exception):
    """A failure the front end shows to the user: `code` is stable, `message` is plain words."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
