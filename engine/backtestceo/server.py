from dataclasses import asdict
from datetime import date

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .alpaca import Alpaca
from .bars import ASSETS, TIMEFRAMES, DataError
from .config import CACHE_DIR


def _day(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise DataError("BAD_DATE", f"{name} must be a date like 2026-10-20.")


def create_app(client) -> FastAPI:
    app = FastAPI(title="Backtest CEO engine")

    @app.exception_handler(DataError)
    async def data_error(_request, e: DataError):
        return JSONResponse({"code": e.code, "message": e.message}, status_code=e.status)

    @app.get("/api/health")
    def health():
        return {"ok": True, "alpaca_keys_present": client.has_keys}

    @app.get("/api/bars")
    def bars(asset: str, symbol: str, tf: str, start: str, end: str):
        if asset not in ASSETS:
            raise DataError("BAD_ASSET", f"asset must be one of: {', '.join(ASSETS)}.")
        if tf not in TIMEFRAMES:
            raise DataError("BAD_TIMEFRAME", f"tf must be one of: {', '.join(TIMEFRAMES)}.")
        sym = symbol.strip().upper()
        rows = client.bars(asset, sym, tf, _day(start, "start"), _day(end, "end"))
        if not rows:
            raise DataError("EMPTY", f"No bars for {sym} between {start} and {end}.", 404)
        return {"symbol": sym, "asset": asset, "tf": tf, "bars": [asdict(b) for b in rows]}

    @app.get("/api/options/expirations")
    def expirations(underlying: str, on: str):
        u = underlying.strip().upper()
        return {"underlying": u, "on": on, "expirations": client.expirations(u, _day(on, "on"))}

    @app.get("/api/options/chain")
    def chain(underlying: str, expiration: str, on: str):
        _day(expiration, "expiration")
        return client.chain(underlying.strip().upper(), expiration, _day(on, "on"))

    return app


app = create_app(Alpaca(CACHE_DIR))
