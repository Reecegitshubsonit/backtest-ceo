# Backtest CEO Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Engine with Alpaca bars and options chains, plus a 3D CEO room whose BACKTESTS computer opens a
chart with bar replay for Stocks, ETFs, Crypto and Options.

**Architecture:** Python FastAPI engine (`engine/`) wraps Alpaca's read-only data APIs with a disk cache and
serves `/api/*`. A Vite + React + R3F front end (`web3d/`) draws the room, flies the camera to a clicked
computer, and opens an HTML panel; the Backtests panel loads bars from the engine and replays them on a canvas
chart. Pure logic (replay clock, panel state, camera poses, chart geometry, particle figures) lives in
`web3d/src/model` and is unit tested.

**Tech Stack:** Python 3.11, FastAPI, requests, pytest. Node 22, Vite 8, React 19, @react-three/fiber 9,
drei 10, three 0.186, vitest 5, TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-21-backtest-ceo-foundation-design.md`

**Code blocks:** every block preceded by `<!-- file: path -->` is the full content of that file (paths are
relative to the repo root). Blocks without that marker are commands.

## Global Constraints

- Asset classes: stocks, etfs, crypto, options. No futures.
- All data from Alpaca, read-only. No code places orders. Keys only from `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`.
- Options history starts 2024-02-01; earlier dates are refused with code `OPTIONS_TOO_EARLY`.
- Ports: view 5175, engine 8020. Engine routes live under `/api`.
- No indicators ship. Registry exists and is empty. No Scalp City session lines.
- Procedural geometry only; no downloaded models or textures.
- Bloom only with `?fx=high`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: Engine data layer (bars, Alpaca client, options chain)

**Files:**
- Create: `engine/pyproject.toml`, `engine/backtestceo/__init__.py`, `engine/backtestceo/config.py`,
  `engine/backtestceo/bars.py`, `engine/backtestceo/alpaca.py`
- Test: `engine/tests/test_alpaca.py`

**Interfaces:**
- Produces: `Bar(t, o, h, l, c, v)`, `DataError(code, message, status)`, `ASSETS`, `TIMEFRAMES`,
  `Alpaca(cache_dir, key=None, secret=None, session=None, sleep=time.sleep, today=_today)` with
  `.has_keys`, `.bars(asset, symbol, tf, start: date, end: date) -> list[Bar]`,
  `.expirations(underlying, on: date) -> list[str]`,
  `.chain(underlying, expiration: str, on: date) -> dict` (`underlying, expiration, underlying_close, contracts[{symbol,type,strike}]`).

- [ ] **Step 1: Environment**

```bash
cd ~/backtest-ceo/engine && uv venv --python 3.11 .venv && uv pip install --python .venv fastapi uvicorn requests pytest httpx
```

<!-- file: engine/pyproject.toml -->
```toml
[project]
name = "backtestceo"
version = "0.1.0"
description = "Backtest CEO engine: read-only Alpaca data for the visual backtester"
requires-python = ">=3.11,<3.12"
dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "requests>=2.31"]

[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

<!-- file: engine/backtestceo/__init__.py -->
```python
```

<!-- file: engine/backtestceo/config.py -->
```python
import os
from pathlib import Path

ENGINE_PORT = int(os.environ.get("BACKTEST_CEO_ENGINE_PORT", "8020"))
CACHE_DIR = Path(os.environ.get("BACKTEST_CEO_CACHE", str(Path.home() / ".cache" / "backtest-ceo")))
```

- [ ] **Step 2: Write the failing tests**

<!-- file: engine/tests/test_alpaca.py -->
```python
import json
from datetime import date

import pytest
import requests

from backtestceo.alpaca import Alpaca
from backtestceo.bars import Bar, DataError

TODAY = date(2026, 10, 21)
ROW = {"t": "2026-10-20T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body

    @property
    def text(self):
        return json.dumps(self._body)


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, dict(params)))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make(tmp_path, responses, key="k", secret="s"):
    s = FakeSession(responses)
    return Alpaca(tmp_path, key=key, secret=secret, session=s, sleep=lambda _: None, today=lambda: TODAY), s


def bars_body(sym, rows, token=None):
    return Resp(200, {"bars": {sym: rows}, "next_page_token": token})


def test_etf_bars_parse_and_params(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW])])
    assert a.bars("etfs", "SPY", "5Min", date(2026, 10, 20), date(2026, 10, 20)) == [Bar("2026-10-20T13:30:00Z", 1, 2, 0.5, 1.5, 100)]
    url, p = s.calls[0]
    assert url.endswith("/v2/stocks/bars")
    assert p["feed"] == "sip" and p["timeframe"] == "5Min"
    assert p["start"] == "2026-10-20T00:00:00Z" and p["end"] == "2026-10-21T00:00:00Z"


def test_crypto_uses_crypto_endpoint(tmp_path):
    a, s = make(tmp_path, [bars_body("BTC/USD", [ROW])])
    assert len(a.bars("crypto", "BTC/USD", "1Hour", date(2026, 10, 1), date(2026, 10, 2))) == 1
    url, p = s.calls[0]
    assert url.endswith("/v1beta3/crypto/us/bars") and "feed" not in p


def test_options_endpoint(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY261120C00600000", [ROW])])
    a.bars("options", "SPY261120C00600000", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert s.calls[0][0].endswith("/v1beta1/options/bars")


def test_paging_follows_token(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW], "p2"), bars_body("SPY", [ROW])])
    assert len(a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))) == 2
    assert s.calls[1][1]["page_token"] == "p2"


def test_completed_range_is_cached(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW])])
    a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert len(a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))) == 1
    assert len(s.calls) == 1


def test_range_ending_today_is_not_cached(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW]), bars_body("SPY", [ROW])])
    a.bars("stocks", "SPY", "1Min", TODAY, TODAY)
    a.bars("stocks", "SPY", "1Min", TODAY, TODAY)
    assert len(s.calls) == 2


def test_options_before_2024_02_refused(tmp_path):
    a, s = make(tmp_path, [])
    with pytest.raises(DataError) as e:
        a.bars("options", "SPY240119C00470000", "1Min", date(2024, 1, 10), date(2024, 1, 10))
    assert e.value.code == "OPTIONS_TOO_EARLY" and not s.calls


def test_bad_range(tmp_path):
    a, _ = make(tmp_path, [])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 19))
    assert e.value.code == "BAD_RANGE"


def test_missing_keys(tmp_path):
    a, _ = make(tmp_path, [], key="", secret="")
    assert not a.has_keys
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "NO_KEYS" and e.value.status == 503


def test_auth_error(tmp_path):
    a, _ = make(tmp_path, [Resp(403, {"message": "forbidden"})])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "ALPACA_AUTH"


def test_rejected_carries_alpaca_message(tmp_path):
    a, _ = make(tmp_path, [Resp(422, {"message": "invalid symbol"})])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "ZZZZ", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "ALPACA_REJECTED" and "invalid symbol" in e.value.message


def test_rate_limit_retries(tmp_path):
    a, s = make(tmp_path, [Resp(429, {}), bars_body("SPY", [ROW])])
    assert len(a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))) == 1
    assert len(s.calls) == 2


def test_rate_limit_gives_up(tmp_path):
    a, _ = make(tmp_path, [Resp(429, {})] * 5)
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "ALPACA_RATE_LIMIT"


def test_network_error(tmp_path):
    a, _ = make(tmp_path, [requests.ConnectionError("down")])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "NETWORK"


def contracts(*rows, token=None):
    return Resp(200, {"option_contracts": list(rows), "next_page_token": token})


def c(sym, exp, typ, strike):
    return {"symbol": sym, "expiration_date": exp, "type": typ, "strike_price": str(strike)}


def test_expirations_merge_active_and_expired(tmp_path):
    a, s = make(tmp_path, [
        contracts(c("A", "2026-10-23", "call", 600), c("B", "2026-10-30", "put", 600)),
        contracts(c("C", "2026-10-23", "put", 590)),
    ])
    assert a.expirations("SPY", date(2026, 10, 20)) == ["2026-10-23", "2026-10-30"]
    assert [p["status"] for _, p in s.calls] == ["active", "inactive"]
    assert s.calls[0][1]["expiration_date_gte"] == "2026-10-20"
    assert s.calls[0][1]["expiration_date_lte"] == "2026-12-19"


def test_expirations_too_early(tmp_path):
    a, _ = make(tmp_path, [])
    with pytest.raises(DataError) as e:
        a.expirations("SPY", date(2023, 12, 1))
    assert e.value.code == "OPTIONS_TOO_EARLY"


def test_chain_sorted_deduped_with_underlying_close(tmp_path):
    a, s = make(tmp_path, [
        contracts(c("SPY261023P00600000", "2026-10-23", "put", 600), c("SPY261023C00590000", "2026-10-23", "call", 590)),
        contracts(c("SPY261023C00600000", "2026-10-23", "call", 600), c("SPY261023P00600000", "2026-10-23", "put", 600)),
        bars_body("SPY", [{**ROW, "c": 598.5}]),
    ])
    out = a.chain("SPY", "2026-10-23", date(2026, 10, 20))
    assert out["underlying_close"] == 598.5
    assert [(x["strike"], x["type"]) for x in out["contracts"]] == [(590.0, "call"), (600.0, "call"), (600.0, "put")]
    assert s.calls[0][1]["expiration_date"] == "2026-10-23"
    assert s.calls[2][1]["timeframe"] == "1Day"
```

- [ ] **Step 3: Run tests, expect FAIL** — `cd engine && .venv/bin/pytest -q` → `ModuleNotFoundError: backtestceo.alpaca`.

- [ ] **Step 4: Implement**

<!-- file: engine/backtestceo/bars.py -->
```python
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
```

<!-- file: engine/backtestceo/alpaca.py -->
```python
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .bars import Bar, DataError, parse_rows

DATA = "https://data.alpaca.markets"
TRADING = "https://paper-api.alpaca.markets"  # only the read-only contracts listing is used
OPTIONS_START = date(2024, 2, 1)
EXPIRY_WINDOW_DAYS = 60
BAR_URLS = {
    "stocks": DATA + "/v2/stocks/bars",
    "etfs": DATA + "/v2/stocks/bars",
    "crypto": DATA + "/v1beta3/crypto/us/bars",
    "options": DATA + "/v1beta1/options/bars",
}
CONTRACTS_URL = TRADING + "/v2/options/contracts"


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _message(r) -> str:
    try:
        return str(r.json().get("message") or r.text[:200])
    except Exception:
        return r.text[:200]


def _too_early(on: date) -> None:
    if on < OPTIONS_START:
        raise DataError("OPTIONS_TOO_EARLY", "Alpaca options history starts 2024-02-01.")


class Alpaca:
    """Read-only Alpaca market data. Ranges that are fully in the past are cached on disk and never refetched."""

    def __init__(self, cache_dir, key=None, secret=None, session=None, sleep=time.sleep, today=_today):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.key = key if key is not None else os.environ.get("ALPACA_API_KEY", "")
        self.secret = secret if secret is not None else os.environ.get("ALPACA_SECRET_KEY", "")
        self.http = session or requests.Session()
        self.sleep, self.today = sleep, today

    @property
    def has_keys(self) -> bool:
        return bool(self.key and self.secret)

    def _get(self, url: str, params: dict) -> dict:
        if not self.has_keys:
            raise DataError("NO_KEYS", "Alpaca keys missing: set ALPACA_API_KEY and ALPACA_SECRET_KEY for the engine.", 503)
        headers = {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret}
        for attempt in range(5):
            try:
                r = self.http.get(url, headers=headers, params=params, timeout=60)
            except requests.RequestException as e:
                raise DataError("NETWORK", f"Could not reach Alpaca ({e.__class__.__name__}).", 502)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                self.sleep(2 ** attempt)
                continue
            if r.status_code in (401, 403):
                raise DataError("ALPACA_AUTH", "Alpaca refused the keys (check they are valid and have market data access).", 502)
            raise DataError("ALPACA_REJECTED", f"Alpaca answered {r.status_code}: {_message(r)}", 400)
        raise DataError("ALPACA_RATE_LIMIT", "Alpaca rate limit: try again in a minute.", 503)

    def _paged(self, url: str, params: dict, collect) -> list:
        out, token = [], None
        while True:
            body = self._get(url, {**params, **({"page_token": token} if token else {})})
            out += collect(body)
            token = body.get("next_page_token")
            if not token:
                return out

    def _cached(self, name: str, done: bool, loader):
        path = self.cache / (name.replace("/", "_") + ".json")
        if path.exists():
            return json.loads(path.read_text())
        data = loader()
        if done:
            path.write_text(json.dumps(data))
        return data

    def bars(self, asset: str, symbol: str, tf: str, start: date, end: date) -> list[Bar]:
        if end < start:
            raise DataError("BAD_RANGE", "End date is before start date.")
        if asset == "options":
            _too_early(start)
        params = dict(symbols=symbol, timeframe=tf, start=f"{start}T00:00:00Z",
                      end=f"{end + timedelta(days=1)}T00:00:00Z", limit=10000)
        if asset in ("stocks", "etfs"):
            params.update(adjustment="split", feed="sip")
        rows = self._cached(f"bars-{asset}-{symbol}-{tf}-{start}-{end}", end < self.today(),
                            lambda: self._paged(BAR_URLS[asset], params, lambda b: (b.get("bars") or {}).get(symbol, [])))
        return parse_rows(rows)

    def _contracts(self, underlying: str, **filters) -> list[dict]:
        rows: list[dict] = []
        for status in ("active", "inactive"):  # inactive = expired, needed for past dates
            rows += self._paged(CONTRACTS_URL, dict(underlying_symbols=underlying, status=status, limit=10000, **filters),
                                lambda b: b.get("option_contracts") or [])
        return rows

    def expirations(self, underlying: str, on: date) -> list[str]:
        """Expiration dates within 60 days after `on`, from contracts active then or expired since."""
        _too_early(on)
        hi = on + timedelta(days=EXPIRY_WINDOW_DAYS)

        def load():
            rows = self._contracts(underlying, expiration_date_gte=str(on), expiration_date_lte=str(hi))
            return sorted({r["expiration_date"] for r in rows})

        return self._cached(f"exp-{underlying}-{on}", hi < self.today(), load)

    def chain(self, underlying: str, expiration: str, on: date) -> dict:
        _too_early(on)

        def load():
            seen = {}
            for r in self._contracts(underlying, expiration_date=expiration):
                seen[r["symbol"]] = {"symbol": r["symbol"], "type": r["type"], "strike": float(r["strike_price"])}
            return sorted(seen.values(), key=lambda x: (x["strike"], x["type"]))

        contracts = self._cached(f"chain-{underlying}-{expiration}", date.fromisoformat(expiration) < self.today(), load)
        daily = self.bars("etfs", underlying, "1Day", on, on)
        return {"underlying": underlying, "expiration": expiration,
                "underlying_close": daily[-1].c if daily else None, "contracts": contracts}
```

- [ ] **Step 5: Run tests, expect PASS** — `cd engine && .venv/bin/pytest -q`.
- [ ] **Step 6: Commit** — `git add engine && git commit -m "feat(engine): Alpaca bars and options chain with disk cache"`

---

### Task 2: Engine HTTP server

**Files:** Create `engine/backtestceo/server.py`. Test `engine/tests/test_server.py`.

**Interfaces:**
- Consumes: `Alpaca`, `DataError`, `ASSETS`, `TIMEFRAMES`, `CACHE_DIR`.
- Produces: `create_app(client) -> FastAPI`, module `app`. Routes `GET /api/health`, `/api/bars`,
  `/api/options/expirations`, `/api/options/chain`. Errors are `{code, message}` with the DataError status.

- [ ] **Step 1: Failing tests**

<!-- file: engine/tests/test_server.py -->
```python
from fastapi.testclient import TestClient

from backtestceo.bars import Bar, DataError
from backtestceo.server import create_app


class FakeClient:
    has_keys = True

    def bars(self, asset, symbol, tf, start, end):
        if symbol == "NONE":
            return []
        if symbol == "BAD":
            raise DataError("ALPACA_REJECTED", "nope", 400)
        return [Bar("2026-10-20T13:30:00Z", 1, 2, 0.5, 1.5, 100)]

    def expirations(self, underlying, on):
        return ["2026-10-23"]

    def chain(self, underlying, expiration, on):
        return {"underlying": underlying, "expiration": expiration, "underlying_close": 600.0, "contracts": []}


http = TestClient(create_app(FakeClient()))
Q = "/api/bars?asset=etfs&tf=5Min&start=2026-10-20&end=2026-10-20&symbol="


def test_health():
    assert http.get("/api/health").json() == {"ok": True, "alpaca_keys_present": True}


def test_bars_ok_and_symbol_uppercased():
    body = http.get(Q + "spy").json()
    assert body["symbol"] == "SPY" and body["bars"][0] == {"t": "2026-10-20T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}


def test_bad_asset():
    r = http.get("/api/bars?asset=futures&symbol=ES&tf=5Min&start=2026-10-20&end=2026-10-20")
    assert r.status_code == 400 and r.json()["code"] == "BAD_ASSET"


def test_bad_timeframe():
    r = http.get("/api/bars?asset=etfs&symbol=SPY&tf=2Min&start=2026-10-20&end=2026-10-20")
    assert r.json()["code"] == "BAD_TIMEFRAME"


def test_bad_date():
    r = http.get("/api/bars?asset=etfs&symbol=SPY&tf=5Min&start=10/20/2026&end=2026-10-20")
    assert r.status_code == 400 and r.json()["code"] == "BAD_DATE"


def test_empty_is_404():
    r = http.get(Q + "NONE")
    assert r.status_code == 404 and r.json()["code"] == "EMPTY"


def test_data_error_passthrough():
    r = http.get(Q + "BAD")
    assert r.status_code == 400 and r.json() == {"code": "ALPACA_REJECTED", "message": "nope"}


def test_expirations_and_chain():
    assert http.get("/api/options/expirations?underlying=spy&on=2026-10-20").json()["expirations"] == ["2026-10-23"]
    body = http.get("/api/options/chain?underlying=spy&expiration=2026-10-23&on=2026-10-20").json()
    assert body["underlying"] == "SPY" and body["underlying_close"] == 600.0
```

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError: backtestceo.server`).
- [ ] **Step 3: Implement**

<!-- file: engine/backtestceo/server.py -->
```python
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
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(engine): /api server for bars, expirations, chain`

---

### Task 3: Front-end scaffold and pure models

**Files:** Create `web3d/package.json`, `web3d/vite.config.ts`, `web3d/tsconfig.json`, `web3d/index.html`,
`web3d/src/model/{types,format,viewport,replay,panel,camera,indicators,dates}.ts`,
`web3d/src/config/{seats,computers}.ts`. Test `web3d/tests/model.test.ts`.

**Interfaces (produced, used by Tasks 4-7):**
- `types.ts`: `Asset`, `Timeframe`, `ASSET_TABS`, `TIMEFRAMES`, `Bar`, `BarsResponse`, `Contract`, `Chain`, `ComputerId`.
- `format.ts`: `fmtTime(t, tf)`, `fmtStamp(t)`, `fmtPrice(v)`.
- `viewport.ts`: `ChartView`, `fullView`, `zoomTime`, `panTime`, `zoomPrice`, `panPrice`, `visibleRange`, `priceRange`.
- `replay.ts`: `ReplayState`, `SPEEDS`, `initialReplay(n)`, `tick(s,n,dt)`, `play(s,n)`, `pause(s)`, `seek(s,n,i)`, `step(s,n,d)`, `revealed(bars,s)`.
- `panel.ts`: `PanelState`, `PanelAction`, `PANEL_CLOSED`, `panelReduce`.
- `camera.ts`: `Vec3`, `CamPose`, `onArc`, `roomPose(aspect)`, `fovFor(aspect)`, `screenPose(angle,r,y)`, `poseDistance`.
- `indicators.ts`: `Indicator`, `INDICATORS` (empty).
- `dates.ts`: `lastSession(now)`.
- `seats.ts`: `Seat`, `SEATS`. `computers.ts`: `Computer`, `COMPUTERS`, `computerById`, `WALL_RADIUS`, `COMPUTER_Y`, `COMPUTER_W`, `COMPUTER_H`.

- [ ] **Step 1: Scaffold**

<!-- file: web3d/package.json -->
```json
{
  "name": "backtest-ceo-web3d",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run",
    "mock": "node scripts/mock_engine.mjs"
  },
  "dependencies": {
    "@react-three/drei": "^10.7.9",
    "@react-three/fiber": "^9.8.1",
    "@react-three/postprocessing": "^3.1.3",
    "postprocessing": "^6.39.5",
    "react": "^19.3.0",
    "react-dom": "^19.3.0",
    "three": "^0.186.1"
  },
  "devDependencies": {
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@types/three": "^0.186.0",
    "@vitejs/plugin-react": "^6.1.2",
    "typescript": "^7.0.2",
    "vite": "^8.3.4",
    "vitest": "^5.0.3"
  }
}
```

<!-- file: web3d/vite.config.ts -->
```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const target = process.env.VITE_ENGINE_URL ?? 'http://127.0.0.1:8020'

export default defineConfig({
  plugins: [react()],
  server: { port: 5175, proxy: { '/api': target } },
  test: { environment: 'node', include: ['tests/**/*.test.ts'] },
})
```

<!-- file: web3d/tsconfig.json -->
```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler", "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx", "strict": true, "noEmit": true, "skipLibCheck": true, "types": ["vite/client"],
    "isolatedModules": true, "esModuleInterop": true
  },
  "include": ["src", "tests", "vite.config.ts"]
}
```

<!-- file: web3d/index.html -->
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" href="/backtest-ceo.svg" />
    <title>Backtest CEO</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```bash
cd ~/backtest-ceo/web3d && npm install
```

- [ ] **Step 2: Failing tests**

<!-- file: web3d/tests/model.test.ts -->
```ts
import { describe, expect, it } from 'vitest'
import { fmtTime, fmtStamp, fmtPrice } from '../src/model/format'
import { initialReplay, pause, play, revealed, seek, step, tick } from '../src/model/replay'
import { PANEL_CLOSED, panelReduce } from '../src/model/panel'
import { fovFor, onArc, poseDistance, roomPose, screenPose } from '../src/model/camera'
import { fullView, priceRange, zoomTime } from '../src/model/viewport'
import { lastSession } from '../src/model/dates'
import { INDICATORS } from '../src/model/indicators'
import { COMPUTERS, computerById } from '../src/config/computers'
import { SEATS } from '../src/config/seats'
import type { Bar } from '../src/model/types'

const bar = (i: number, c = 100 + i): Bar => ({ t: new Date(Date.UTC(2026, 9, 20, 13, 30 + i)).toISOString(), o: c, h: c + 1, l: c - 1, c, v: 10 })

describe('format', () => {
  it('shows ET clock time intraday and a date for daily bars', () => {
    expect(fmtTime('2026-10-20T13:30:00Z', '5Min')).toBe('09:30')
    expect(fmtTime('2026-10-20T04:00:00Z', '1Day')).toBe('Oct 20')
    expect(fmtStamp('2026-10-20T13:30:00Z')).toBe('Oct 20 09:30 ET')
  })
  it('uses more decimals for cheap prices', () => {
    expect(fmtPrice(612.5)).toBe('612.50')
    expect(fmtPrice(0.85)).toBe('0.850')
  })
})

describe('replay', () => {
  it('starts showing every bar, paused', () => {
    expect(initialReplay(10)).toMatchObject({ index: 9, playing: false })
  })
  it('play from the end rewinds to the first bar', () => {
    expect(play(initialReplay(10), 10)).toMatchObject({ index: 0, playing: true })
  })
  it('advances speed bars per second and never passes the last bar', () => {
    let s = { ...play(initialReplay(10), 10), speed: 5 }
    s = tick(s, 10, 0.5)
    expect(s.index).toBe(2)
    s = tick(s, 10, 10)
    expect(s).toMatchObject({ index: 9, playing: false })
  })
  it('keeps fractional progress between ticks', () => {
    let s = { ...play(initialReplay(10), 10), speed: 1 }
    s = tick(tick(s, 10, 0.6), 10, 0.6)
    expect(s.index).toBe(1)
  })
  it('does nothing while paused', () => {
    const s = pause(play(initialReplay(10), 10))
    expect(tick(s, 10, 5)).toBe(s)
  })
  it('seek clamps and step pauses', () => {
    const s = initialReplay(10)
    expect(seek(s, 10, 99).index).toBe(9)
    expect(seek(s, 10, -3).index).toBe(0)
    expect(step(play(s, 10), 10, 3)).toMatchObject({ index: 3, playing: false })
  })
  it('revealed never includes bars past the clock', () => {
    const bars = [0, 1, 2, 3].map(i => bar(i))
    expect(revealed(bars, seek(initialReplay(4), 4, 1))).toEqual(bars.slice(0, 2))
  })
})

describe('panel state', () => {
  it('click flies, arrives opens, close returns', () => {
    let s = panelReduce(PANEL_CLOSED, { type: 'click', id: 'backtests' })
    expect(s).toEqual({ phase: 'flying', computer: 'backtests' })
    s = panelReduce(s, { type: 'arrived' })
    expect(s.phase).toBe('open')
    s = panelReduce(s, { type: 'close' })
    expect(s.phase).toBe('closing')
    expect(panelReduce(s, { type: 'returned' })).toEqual(PANEL_CLOSED)
  })
  it('ignores clicks while closing and arrivals while closed', () => {
    const closing = { phase: 'closing' as const, computer: 'scanner' as const }
    expect(panelReduce(closing, { type: 'click', id: 'backtests' })).toBe(closing)
    expect(panelReduce(PANEL_CLOSED, { type: 'arrived' })).toBe(PANEL_CLOSED)
  })
  it('clicking another computer while open flies to it', () => {
    const open = { phase: 'open' as const, computer: 'scanner' as const }
    expect(panelReduce(open, { type: 'click', id: 'strategies' })).toEqual({ phase: 'flying', computer: 'strategies' })
  })
})

describe('camera', () => {
  it('180 degrees is straight behind the CEO', () => {
    const [x, y, z] = onArc(180, 7, 3)
    expect(x).toBeCloseTo(0); expect(y).toBe(3); expect(z).toBeCloseTo(-7)
  })
  it('screen pose sits in front of the screen, looking at it', () => {
    const p = screenPose(180, 7.4, 3)
    expect(p.target[2]).toBeCloseTo(-7.4)
    expect(p.pos[2]).toBeCloseTo(-4.8)
  })
  it('narrow screens widen the field of view instead of backing out of the room', () => {
    expect(fovFor(1.6)).toBe(48)
    expect(fovFor(0.46)).toBeGreaterThan(70)
    expect(roomPose(0.46).pos[2]).toBeLessThan(13)
  })
  it('pose distance is zero for equal poses', () => {
    expect(poseDistance(roomPose(1.5), roomPose(1.5))).toBe(0)
  })
})

describe('viewport', () => {
  it('price range pads the visible highs and lows', () => {
    const r = priceRange([bar(0, 100), bar(1, 110)], fullView())
    expect(r.lo).toBeLessThan(99); expect(r.hi).toBeGreaterThan(111)
  })
  it('zoom keeps at least 10 bars', () => {
    expect(zoomTime(fullView(), 100, 1000, 0.5).span).toBe(10)
  })
})

describe('dates', () => {
  it('last session is the previous weekday', () => {
    expect(lastSession(new Date('2026-10-21T15:00:00Z'))).toBe('2026-10-20')
    expect(lastSession(new Date('2026-10-19T15:00:00Z'))).toBe('2026-10-16')
  })
})

describe('config', () => {
  it('ships no indicators', () => { expect(INDICATORS).toEqual([]) })
  it('has six seats and three computers, backtests live', () => {
    expect(SEATS).toHaveLength(6)
    expect(COMPUTERS.map(c => c.id)).toEqual(['scanner', 'backtests', 'strategies'])
    expect(computerById('backtests').live).toBe(true)
  })
})
```

- [ ] **Step 3: Run, expect FAIL** — `cd web3d && npx vitest run` (modules missing).
- [ ] **Step 4: Implement**

<!-- file: web3d/src/model/types.ts -->
```ts
export type Asset = 'stocks' | 'etfs' | 'crypto' | 'options'
export type Timeframe = '1Min' | '5Min' | '15Min' | '1Hour' | '1Day'
export type ComputerId = 'scanner' | 'backtests' | 'strategies'

export const ASSET_TABS: { id: Asset; label: string }[] = [
  { id: 'stocks', label: 'Stocks' }, { id: 'etfs', label: 'ETFs' }, { id: 'crypto', label: 'Crypto' }, { id: 'options', label: 'Options' },
]
export const TIMEFRAMES: Timeframe[] = ['1Min', '5Min', '15Min', '1Hour', '1Day']

/** One OHLCV bar from the engine; `t` is the bar start, UTC ISO. */
export interface Bar { t: string; o: number; h: number; l: number; c: number; v: number }
export interface BarsResponse { symbol: string; asset: Asset; tf: Timeframe; bars: Bar[] }
export interface Contract { symbol: string; type: 'call' | 'put'; strike: number }
export interface Chain { underlying: string; expiration: string; underlying_close: number | null; contracts: Contract[] }
```

<!-- file: web3d/src/model/format.ts -->
```ts
import type { Timeframe } from './types'

const clock = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const day = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric' })

/** Axis label: ET clock time for intraday bars, month and day for daily bars. */
export const fmtTime = (t: string, tf: Timeframe): string => (tf === '1Day' ? day : clock).format(new Date(t))

export const fmtStamp = (t: string): string => `${day.format(new Date(t))} ${clock.format(new Date(t))} ET`

/** Options and cheap coins need a third decimal. */
export const fmtPrice = (v: number): string => v.toFixed(Math.abs(v) < 10 ? 3 : 2)
```

<!-- file: web3d/src/model/viewport.ts -->
```ts
import type { Bar } from './types'

export const MIN_SPAN = 10
const MAX_PRICE_ZOOM = 20

/** Visible slice of a chart: start index and span in bars (Infinity = all), plus a vertical zoom and shift. */
export interface ChartView { start: number; span: number; priceZoom: number; priceShift: number }

export const fullView = (): ChartView => ({ start: 0, span: Infinity, priceZoom: 1, priceShift: 0 })

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x))

/** Zoom the time axis by `factor` (>1 zooms in) keeping the bar under `anchor` (0..1 across the chart) fixed. */
export function zoomTime(v: ChartView, n: number, factor: number, anchor: number): ChartView {
  const span0 = Math.min(v.span, n)
  const span = Math.min(n, Math.max(MIN_SPAN, span0 / factor))
  const idx = v.start + anchor * span0
  return { ...v, span, start: clamp(idx - anchor * span, 0, Math.max(0, n - span)) }
}

export function panTime(v: ChartView, n: number, deltaBars: number): ChartView {
  const span = Math.min(v.span, n)
  return { ...v, span, start: clamp(v.start + deltaBars, 0, Math.max(0, n - span)) }
}

export function zoomPrice(v: ChartView, factor: number): ChartView {
  const priceZoom = clamp(v.priceZoom * factor, 1, MAX_PRICE_ZOOM)
  return { ...v, priceZoom, priceShift: priceZoom === 1 ? 0 : v.priceShift }
}

/** Shift the price axis by a fraction of the visible price range. */
export function panPrice(v: ChartView, fraction: number): ChartView {
  return { ...v, priceShift: v.priceZoom === 1 ? 0 : v.priceShift + fraction }
}

export function visibleRange(bars: Bar[], v: ChartView): { i0: number; i1: number } {
  const n = bars.length
  const span = Math.min(v.span, n)
  const i0 = clamp(Math.floor(v.start), 0, Math.max(0, n - 1))
  return { i0, i1: Math.min(n, Math.ceil(v.start + span)) }
}

export function priceRange(bars: Bar[], v: ChartView): { lo: number; hi: number } {
  const { i0, i1 } = visibleRange(bars, v)
  let lo = Infinity, hi = -Infinity
  for (let i = i0; i < i1; i++) { if (bars[i].l < lo) lo = bars[i].l; if (bars[i].h > hi) hi = bars[i].h }
  if (!Number.isFinite(lo)) return { lo: 0, hi: 1 }
  const pad = (hi - lo) * 0.06 || Math.max(0.01, hi * 0.001)
  lo -= pad; hi += pad
  const range = (hi - lo) / v.priceZoom
  const center = (hi + lo) / 2 + v.priceShift * range
  return { lo: center - range / 2, hi: center + range / 2 }
}
```

<!-- file: web3d/src/model/replay.ts -->
```ts
/** Replay clock for a loaded bar series. `index` is the last revealed bar; speed is bars per second. */
export interface ReplayState { index: number; playing: boolean; speed: number; acc: number }

export const SPEEDS = [1, 2, 5, 10, 25, 50]

const clampIndex = (i: number, n: number) => Math.min(Math.max(0, n - 1), Math.max(0, Math.round(i)))

/** A freshly loaded series shows every bar, paused. */
export const initialReplay = (n: number): ReplayState => ({ index: Math.max(0, n - 1), playing: false, speed: 5, acc: 0 })

export function tick(s: ReplayState, n: number, dtSec: number): ReplayState {
  if (!s.playing || n === 0) return s
  const acc = s.acc + dtSec * s.speed
  const steps = Math.floor(acc)
  const index = Math.min(n - 1, s.index + steps)
  return { ...s, index, acc: acc - steps, playing: index < n - 1 }
}

/** Play; from the last bar it rewinds to the first. */
export function play(s: ReplayState, n: number): ReplayState {
  return { ...s, playing: n > 1, index: s.index >= n - 1 ? 0 : s.index, acc: 0 }
}

export const pause = (s: ReplayState): ReplayState => (s.playing ? { ...s, playing: false } : s)

export const seek = (s: ReplayState, n: number, i: number): ReplayState => ({ ...s, index: clampIndex(i, n), acc: 0 })

export const step = (s: ReplayState, n: number, delta: number): ReplayState => seek(pause(s), n, s.index + delta)

/** Bars the chart may draw: never any past the replay clock. */
export const revealed = <T>(bars: T[], s: ReplayState): T[] => bars.slice(0, s.index + 1)
```

<!-- file: web3d/src/model/panel.ts -->
```ts
import type { ComputerId } from './types'

export type Phase = 'closed' | 'flying' | 'open' | 'closing'
export interface PanelState { phase: Phase; computer: ComputerId | null }
export type PanelAction = { type: 'click'; id: ComputerId } | { type: 'arrived' } | { type: 'close' } | { type: 'returned' }

export const PANEL_CLOSED: PanelState = { phase: 'closed', computer: null }

/** closed -> flying (camera moves) -> open (panel shown) -> closing (camera returns) -> closed. */
export function panelReduce(s: PanelState, a: PanelAction): PanelState {
  switch (a.type) {
    case 'click': return s.phase === 'closed' || s.phase === 'open' ? { phase: 'flying', computer: a.id } : s
    case 'arrived': return s.phase === 'flying' ? { ...s, phase: 'open' } : s
    case 'close': return s.phase === 'open' || s.phase === 'flying' ? { ...s, phase: 'closing' } : s
    case 'returned': return s.phase === 'closing' ? PANEL_CLOSED : s
  }
}
```

<!-- file: web3d/src/model/camera.ts -->
```ts
export type Vec3 = [number, number, number]
export interface CamPose { pos: Vec3; target: Vec3 }

const NARROW = 1.25

/** Point on a circle around the room centre; 0 degrees faces the viewer (+z), 180 is behind the CEO. */
export function onArc(angleDeg: number, r: number, y: number): Vec3 {
  const a = (angleDeg * Math.PI) / 180
  return [Math.sin(a) * r, y, Math.cos(a) * r]
}

/** On narrow screens widen the field of view instead of backing the camera out through the wall. */
export function fovFor(aspect: number): number {
  if (aspect >= NARROW) return 48
  return Math.min(80, (2 * Math.atan(5.0 / 11.5 / aspect) * 180) / Math.PI)
}

export const roomPose = (aspect: number): CamPose => ({ pos: [0, 2.7, aspect >= NARROW ? 10.5 : 11.5], target: [0, 2.3, 0] })

/** Camera `dist` in front of a wall screen, looking straight at it. */
export const screenPose = (angleDeg: number, r: number, y: number, dist = 2.6): CamPose =>
  ({ pos: onArc(angleDeg, r - dist, y), target: onArc(angleDeg, r, y) })

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
export const poseDistance = (a: CamPose, b: CamPose): number => Math.max(dist(a.pos, b.pos), dist(a.target, b.target))
```

<!-- file: web3d/src/model/indicators.ts -->
```ts
import type { Bar } from './types'

/** One chart indicator. `compute` gets only revealed bars and returns one value (or null) per bar. */
export interface Indicator {
  id: string
  name: string
  color: string
  pane: 'overlay' | 'lower'
  compute: (bars: Bar[]) => (number | null)[]
}

/** Empty on purpose: each indicator will be added with the strategy that uses it. */
export const INDICATORS: Indicator[] = []
```

<!-- file: web3d/src/model/dates.ts -->
```ts
/** The most recent weekday before `now` (UTC date), as YYYY-MM-DD. Holidays are not skipped. */
export function lastSession(now: Date): string {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  do d.setUTCDate(d.getUTCDate() - 1)
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6)
  return d.toISOString().slice(0, 10)
}
```

<!-- file: web3d/src/config/seats.ts -->
```ts
/** Agent seats around the table. Angle 0 faces the viewer; seats skip the front so the table stays visible. */
export interface Seat { id: string; name: string; job: string; angleDeg: number }

export const SEATS: Seat[] = [
  { id: 'scanner', name: 'SCANNER AGENT', job: 'Surfacing candidates', angleDeg: -42 },
  { id: 'strategist', name: 'STRATEGIST', job: 'Writing strategy rules', angleDeg: -88 },
  { id: 'backtester', name: 'BACKTESTER', job: 'Running tests', angleDeg: -132 },
  { id: 'auditor', name: 'VALIDATION AUDITOR', job: 'Checking results', angleDeg: 132 },
  { id: 'regime', name: 'REGIME ANALYST', job: 'Labelling conditions', angleDeg: 88 },
  { id: 'risk', name: 'RISK MANAGER', job: 'Limits and veto', angleDeg: 42 },
]
```

<!-- file: web3d/src/config/computers.ts -->
```ts
import type { ComputerId } from '../model/types'

export interface Computer { id: ComputerId; label: string; angleDeg: number; live: boolean }

/** The three clickable computers on the wall behind the CEO (180 degrees = straight behind). */
export const COMPUTERS: Computer[] = [
  { id: 'scanner', label: 'SCANNER', angleDeg: 158, live: false },
  { id: 'backtests', label: 'BACKTESTS', angleDeg: 180, live: true },
  { id: 'strategies', label: 'STRATEGIES', angleDeg: 202, live: false },
]

export const WALL_RADIUS = 7.4
export const COMPUTER_Y = 3.0
export const COMPUTER_W = 2.6
export const COMPUTER_H = 1.6

export const computerById = (id: ComputerId): Computer => COMPUTERS.find(c => c.id === id)!
```

- [ ] **Step 5: Run, expect PASS** — `npx vitest run`.
- [ ] **Step 6: Commit** — `feat(web3d): scaffold and pure models (replay, panel, camera, viewport)`

---

### Task 4: Chart (canvas) with replay bar

**Files:** Create `web3d/src/panels/drawChart.ts`, `web3d/src/panels/ChartView.tsx`,
`web3d/src/panels/ReplayBar.tsx`, `web3d/src/hooks/useReplay.ts`. Test `web3d/tests/chart.test.ts`.

**Interfaces:**
- Consumes: `Bar`, `Timeframe`, viewport functions, `fmtTime`, `fmtStamp`, `fmtPrice`, `INDICATORS`, replay functions.
- Produces: `chartGeometry(w,h,bars,view)`, `drawChart(ctx,w,h,bars,opts)`, `<ChartView bars tf title height />`,
  `useReplay(n) -> { state, play, pause, seek, step, setSpeed }`, `<ReplayBar n replay times />`.

- [ ] **Step 1: Failing test**

<!-- file: web3d/tests/chart.test.ts -->
```ts
import { describe, expect, it } from 'vitest'
import { chartGeometry } from '../src/panels/drawChart'
import { fullView } from '../src/model/viewport'
import type { Bar } from '../src/model/types'

const bars: Bar[] = [0, 1, 2, 3].map(i => ({ t: `2026-10-20T13:3${i}:00Z`, o: 100, h: 101 + i, l: 99 - i, c: 100, v: 10 }))

describe('chartGeometry', () => {
  const g = chartGeometry(800, 400, bars, fullView())
  it('maps the padded price range onto the price plot', () => {
    expect(g.y(g.hi)).toBeCloseTo(g.padT)
    expect(g.y(g.lo)).toBeCloseTo(g.padT + g.plotH)
  })
  it('centres bars in their slots', () => {
    expect(g.x(0)).toBeCloseTo(g.padL + g.plotW / 8)
  })
  it('puts the volume panel below the price plot', () => {
    expect(g.volTop).toBeGreaterThan(g.padT + g.plotH)
    expect(g.volTop + g.volH).toBeLessThanOrEqual(400 - g.padB)
  })
})
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

<!-- file: web3d/src/panels/drawChart.ts -->
```ts
import type { Bar, Timeframe } from '../model/types'
import type { Indicator } from '../model/indicators'
import { fullView, priceRange, type ChartView } from '../model/viewport'
import { fmtPrice, fmtTime } from '../model/format'

export const CHART_COLORS = {
  bg: '#050a18', grid: '#13234a', text: '#9fc4ee', up: '#2fd27a', down: '#ff4d6a', cross: '#6cc8ff', tag: '#0b2a55',
}

export interface IndicatorSeries { ind: Indicator; values: (number | null)[] }
export interface DrawOptions { view?: ChartView; tf: Timeframe; cross?: number | null; overlays?: IndicatorSeries[] }

export interface ChartGeometry {
  start: number; span: number; n: number
  padL: number; padR: number; padT: number; padB: number
  plotW: number; plotH: number; volTop: number; volH: number; lo: number; hi: number
  x: (i: number) => number
  y: (v: number) => number
}

/** Price plot on top (about 80 %), volume panel under it, time axis at the bottom, price axis on the right. */
export function chartGeometry(w: number, h: number, bars: Bar[], view: ChartView = fullView()): ChartGeometry {
  const n = bars.length
  const padL = 8, padR = 66, padT = 10, padB = 24
  const full = Math.max(1, h - padT - padB)
  const volH = Math.round(full * 0.18), gap = 6
  const plotH = Math.max(1, full - volH - gap), volTop = padT + plotH + gap
  const plotW = Math.max(1, w - padL - padR)
  const span = Math.max(1, Math.min(view.span, n))
  const start = Math.min(Math.max(0, view.start), Math.max(0, n - span))
  const { lo, hi } = priceRange(bars, { ...view, start, span })
  return {
    start, span, n, padL, padR, padT, padB, plotW, plotH, volTop, volH, lo, hi,
    x: i => padL + ((i - start + 0.5) / span) * plotW,
    y: v => padT + (1 - (v - lo) / (hi - lo)) * plotH,
  }
}

export function drawChart(ctx: CanvasRenderingContext2D, w: number, h: number, bars: Bar[], o: DrawOptions): ChartGeometry {
  ctx.fillStyle = CHART_COLORS.bg
  ctx.fillRect(0, 0, w, h)
  const g = chartGeometry(w, h, bars, o.view)
  ctx.font = '11px system-ui, sans-serif'
  if (g.n === 0) {
    ctx.fillStyle = CHART_COLORS.text; ctx.textAlign = 'center'
    ctx.fillText('no bars loaded', w / 2, h / 2)
    return g
  }
  const slot = g.plotW / g.span
  const bw = Math.max(1, slot * 0.7)
  const i0 = Math.max(0, Math.floor(g.start) - 1), i1 = Math.min(g.n, Math.ceil(g.start + g.span) + 1)

  // grid, price axis, time axis
  ctx.strokeStyle = CHART_COLORS.grid; ctx.fillStyle = CHART_COLORS.text; ctx.lineWidth = 1; ctx.textAlign = 'left'
  for (let k = 0; k <= 5; k++) {
    const v = g.lo + ((g.hi - g.lo) * k) / 5, yy = Math.round(g.y(v)) + 0.5
    ctx.beginPath(); ctx.moveTo(g.padL, yy); ctx.lineTo(w - g.padR, yy); ctx.stroke()
    ctx.fillText(fmtPrice(v), w - g.padR + 6, yy + 4)
  }
  ctx.textAlign = 'center'
  const every = Math.max(1, Math.ceil(84 / slot))
  for (let i = i0; i < i1; i++) {
    if (i % every !== 0) continue
    const xx = Math.round(g.x(i)) + 0.5
    if (xx < g.padL || xx > w - g.padR) continue
    ctx.beginPath(); ctx.moveTo(xx, g.padT); ctx.lineTo(xx, g.volTop + g.volH); ctx.stroke()
    ctx.fillText(fmtTime(bars[i].t, o.tf), xx, h - g.padB + 16)
  }

  // volume
  let vmax = 0
  for (let i = i0; i < i1; i++) vmax = Math.max(vmax, bars[i].v)
  for (let i = i0; i < i1; i++) {
    const b = bars[i], vh = vmax ? (b.v / vmax) * g.volH : 0
    ctx.fillStyle = (b.c >= b.o ? CHART_COLORS.up : CHART_COLORS.down) + '66'
    ctx.fillRect(g.x(i) - bw / 2, g.volTop + g.volH - vh, bw, vh)
  }

  // candles and overlay indicators, clipped to the price plot
  ctx.save()
  ctx.beginPath(); ctx.rect(g.padL, g.padT, g.plotW, g.plotH); ctx.clip()
  for (let i = i0; i < i1; i++) {
    const b = bars[i], col = b.c >= b.o ? CHART_COLORS.up : CHART_COLORS.down, xx = g.x(i)
    ctx.strokeStyle = col; ctx.fillStyle = col
    ctx.beginPath(); ctx.moveTo(Math.round(xx) + 0.5, g.y(b.h)); ctx.lineTo(Math.round(xx) + 0.5, g.y(b.l)); ctx.stroke()
    const top = g.y(Math.max(b.o, b.c)), bot = g.y(Math.min(b.o, b.c))
    ctx.fillRect(xx - bw / 2, top, bw, Math.max(1, bot - top))
  }
  for (const s of o.overlays ?? []) {
    if (s.ind.pane !== 'overlay') continue
    ctx.strokeStyle = s.ind.color; ctx.lineWidth = 1.4; ctx.beginPath()
    let on = false
    for (let i = i0; i < i1; i++) {
      const v = s.values[i]
      if (v == null) { on = false; continue }
      if (on) ctx.lineTo(g.x(i), g.y(v)); else { ctx.moveTo(g.x(i), g.y(v)); on = true }
    }
    ctx.stroke()
  }
  ctx.restore()

  // crosshair with a price tag on the axis
  if (o.cross != null && o.cross >= i0 && o.cross < i1) {
    const xx = Math.round(g.x(o.cross)) + 0.5, b = bars[o.cross], yy = Math.round(g.y(b.c)) + 0.5
    ctx.strokeStyle = CHART_COLORS.cross; ctx.setLineDash([4, 4]); ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(xx, g.padT); ctx.lineTo(xx, g.volTop + g.volH); ctx.moveTo(g.padL, yy); ctx.lineTo(w - g.padR, yy); ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = CHART_COLORS.tag; ctx.fillRect(w - g.padR + 1, yy - 9, g.padR - 2, 18)
    ctx.fillStyle = '#ffffff'; ctx.textAlign = 'left'; ctx.fillText(fmtPrice(b.c), w - g.padR + 6, yy + 4)
  }
  return g
}
```

<!-- file: web3d/src/panels/ChartView.tsx -->
```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Bar, Timeframe } from '../model/types'
import { fullView, panPrice, panTime, zoomPrice, zoomTime, type ChartView as View } from '../model/viewport'
import { fmtPrice, fmtStamp } from '../model/format'
import { INDICATORS } from '../model/indicators'
import { drawChart, type ChartGeometry } from './drawChart'

interface Props { bars: Bar[]; tf: Timeframe; title: string; height?: number }

/** Candles and volume. Wheel = zoom time, Shift+wheel = zoom price, drag = pan, double-click = reset. */
export function ChartView({ bars, tf, title, height = 420 }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const geo = useRef<ChartGeometry | null>(null)
  const drag = useRef<{ x: number; y: number } | null>(null)
  const [view, setView] = useState<View>(fullView())
  const [hover, setHover] = useState<number | null>(null)
  const n = bars.length
  const prevN = useRef(n)
  const overlays = useMemo(() => INDICATORS.map(ind => ({ ind, values: ind.compute(bars) })), [bars])

  // while replaying, keep the newest bar in view if the view was already at the right edge
  useEffect(() => {
    setView(v => {
      if (v.span === Infinity || n === prevN.current) return v
      const atEdge = v.start + Math.min(v.span, prevN.current) >= prevN.current - 0.5
      return atEdge ? { ...v, start: Math.max(0, n - Math.min(v.span, n)) } : v
    })
    prevN.current = n
  }, [n])

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const paint = () => {
      const w = cv.clientWidth, dpr = Math.min(3, window.devicePixelRatio || 1)
      if (!w) return
      cv.width = Math.round(w * dpr); cv.height = Math.round(height * dpr)
      const ctx = cv.getContext('2d')!
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      geo.current = drawChart(ctx, w, height, bars, { view, tf, cross: hover, overlays })
    }
    paint()
    const ro = new ResizeObserver(paint)
    ro.observe(cv)
    return () => ro.disconnect()
  }, [bars, view, hover, height, tf, overlays])

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const g = geo.current, factor = Math.exp(-e.deltaY * 0.0018)
      if (e.shiftKey) { setView(v => zoomPrice(v, factor)); return }
      const rect = cv.getBoundingClientRect()
      const anchor = g ? Math.min(1, Math.max(0, (e.clientX - rect.left - g.padL) / g.plotW)) : 0.5
      setView(v => zoomTime(v, n, factor, anchor))
    }
    cv.addEventListener('wheel', onWheel, { passive: false })
    return () => cv.removeEventListener('wheel', onWheel)
  }, [n])

  const idxAt = (clientX: number): number | null => {
    const g = geo.current, cv = ref.current
    if (!g || !cv || !g.n) return null
    const rect = cv.getBoundingClientRect()
    return Math.min(g.n - 1, Math.max(0, Math.round(g.start + ((clientX - rect.left - g.padL) / g.plotW) * g.span - 0.5)))
  }
  const timeZoom = useCallback((f: number) => setView(v => zoomTime(v, n, f, 0.5)), [n])
  const onKey = (e: React.KeyboardEvent) => {
    const step = geo.current ? Math.max(1, geo.current.span / 10) : 5
    const fn = ({ '+': () => timeZoom(1.4), '=': () => timeZoom(1.4), '-': () => timeZoom(1 / 1.4), '0': () => setView(fullView()),
      ArrowLeft: () => setView(v => panTime(v, n, -step)), ArrowRight: () => setView(v => panTime(v, n, step)),
      ArrowUp: () => setView(v => zoomPrice(v, 1.3)), ArrowDown: () => setView(v => zoomPrice(v, 1 / 1.3)) } as Record<string, () => void>)[e.key]
    if (fn) { e.preventDefault(); fn() }
  }

  const b = hover != null ? bars[hover] : bars[n - 1]
  const first = bars[0]
  const change = b && first ? ((b.c - first.o) / first.o) * 100 : null
  return (
    <figure className="chart">
      <figcaption className="charthead">
        <b>{title}</b>
        {b && <span> · {fmtPrice(b.c)}</span>}
        {change != null && <span className={change >= 0 ? 'pos' : 'neg'}> {change >= 0 ? '+' : ''}{change.toFixed(2)}%</span>}
        <span className="muted"> · {tf} · {n} bars</span>
        <span className="tools">
          <button onClick={() => timeZoom(1.5)} aria-label="Zoom in time">+</button>
          <button onClick={() => timeZoom(1 / 1.5)} aria-label="Zoom out time">−</button>
          <button onClick={() => setView(fullView())}>Reset</button>
        </span>
      </figcaption>
      <canvas ref={ref} tabIndex={0} role="img" className="chartcanvas" style={{ height }}
        aria-label={`${title} ${tf} chart, ${n} bars. Plus and minus zoom, arrow keys pan, 0 resets.`}
        onPointerDown={e => { drag.current = { x: e.clientX, y: e.clientY }; (e.target as HTMLElement).setPointerCapture(e.pointerId) }}
        onPointerMove={e => {
          const g = geo.current
          if (drag.current && g) {
            const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y
            drag.current = { x: e.clientX, y: e.clientY }
            setView(v => panPrice(panTime(v, n, -dx / (g.plotW / g.span)), dy / g.plotH))
          } else setHover(idxAt(e.clientX))
        }}
        onPointerUp={() => { drag.current = null }}
        onPointerLeave={() => { drag.current = null; setHover(null) }}
        onDoubleClick={() => setView(fullView())} onKeyDown={onKey} />
      <div className="readout">
        {b ? <>
          <b>{fmtStamp(b.t)}</b> O {fmtPrice(b.o)} H {fmtPrice(b.h)} L {fmtPrice(b.l)} C <b>{fmtPrice(b.c)}</b> V {Math.round(b.v).toLocaleString('en-US')}
        </> : <span className="muted">no bars</span>}
      </div>
    </figure>
  )
}
```

<!-- file: web3d/src/hooks/useReplay.ts -->
```ts
import { useCallback, useEffect, useRef, useState } from 'react'
import { initialReplay, pause, play, seek, step, tick, type ReplayState } from '../model/replay'

/** Replay clock driven by requestAnimationFrame. Resets whenever a new series (length `n`, key `key`) loads. */
export function useReplay(n: number, key: string) {
  const [state, setState] = useState<ReplayState>(() => initialReplay(n))
  const last = useRef<number | null>(null)

  useEffect(() => { setState(initialReplay(n)) }, [n, key])

  useEffect(() => {
    if (!state.playing) { last.current = null; return }
    let raf = 0
    const loop = (now: number) => {
      const dt = last.current == null ? 0 : (now - last.current) / 1000
      last.current = now
      setState(s => tick(s, n, Math.min(dt, 0.25)))
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [state.playing, n])

  return {
    state,
    play: useCallback(() => setState(s => play(s, n)), [n]),
    pause: useCallback(() => setState(pause), []),
    seek: useCallback((i: number) => setState(s => seek(s, n, i)), [n]),
    step: useCallback((d: number) => setState(s => step(s, n, d)), [n]),
    setSpeed: useCallback((speed: number) => setState(s => ({ ...s, speed })), []),
  }
}
```

<!-- file: web3d/src/panels/ReplayBar.tsx -->
```tsx
import { SPEEDS } from '../model/replay'
import { fmtStamp } from '../model/format'
import type { useReplay } from '../hooks/useReplay'

interface Props { n: number; replay: ReturnType<typeof useReplay>; time?: string }

/** Play, pause, step, speed and a scrubber for the replay clock. */
export function ReplayBar({ n, replay, time }: Props) {
  const { state } = replay
  return (
    <div className="replaybar" role="toolbar" aria-label="Replay">
      <button onClick={() => replay.step(-1)} aria-label="Step back">◀︎</button>
      {state.playing
        ? <button onClick={replay.pause} aria-label="Pause">❚❚ Pause</button>
        : <button onClick={replay.play} aria-label="Play">▶ Play</button>}
      <button onClick={() => replay.step(1)} aria-label="Step forward">▶︎</button>
      <label>Speed
        <select value={state.speed} onChange={e => replay.setSpeed(Number(e.target.value))}>
          {SPEEDS.map(s => <option key={s} value={s}>{s}x</option>)}
        </select>
      </label>
      <input type="range" min={0} max={Math.max(0, n - 1)} value={state.index} aria-label="Replay position"
        onChange={e => replay.seek(Number(e.target.value))} />
      <span className="muted">bar {Math.min(n, state.index + 1)} of {n}{time ? ` · ${fmtStamp(time)}` : ''}</span>
    </div>
  )
}
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(web3d): canvas chart with volume, zoom and replay clock`

---

### Task 5: Engine client, panels and options picker

**Files:** Create `web3d/src/net/api.ts`, `web3d/src/panels/{ComputerPanel,BacktestTab,OptionsPicker,ChartPane,ComingNext}.tsx`,
`web3d/scripts/mock_engine.mjs`. Test `web3d/tests/api.test.ts`.

**Interfaces:**
- Produces: `api.health()`, `api.bars(asset, symbol, tf, start, end)`, `api.expirations(u, on)`, `api.chain(u, exp, on)`,
  `ApiFailure(code, message)`; `<ComputerPanel panel dispatch />`.

- [ ] **Step 1: Failing test** (error mapping; fetch stubbed)

<!-- file: web3d/tests/api.test.ts -->
```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiFailure } from '../src/net/api'

const respond = (status: number, body: unknown) =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(body == null ? 'x' : JSON.stringify(body), { status })))

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('builds the query and returns the body', async () => {
    respond(200, { symbol: 'SPY', bars: [] })
    await api.bars('etfs', 'SPY', '5Min', '2026-10-20', '2026-10-20')
    const url = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toBe('/api/bars?asset=etfs&symbol=SPY&tf=5Min&start=2026-10-20&end=2026-10-20')
  })
  it('turns engine errors into ApiFailure with the code and message', async () => {
    respond(404, { code: 'EMPTY', message: 'No bars' })
    await expect(api.bars('etfs', 'SPY', '5Min', '2026-10-20', '2026-10-20')).rejects.toMatchObject({ code: 'EMPTY', message: 'No bars' })
  })
  it('reports a missing engine plainly', async () => {
    respond(502, null)
    const e = await api.health().catch(x => x)
    expect(e).toBeInstanceOf(ApiFailure)
    expect(e.code).toBe('ENGINE_DOWN')
  })
})
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

<!-- file: web3d/src/net/api.ts -->
```ts
import type { Asset, BarsResponse, Chain, Timeframe } from '../model/types'

export class ApiFailure extends Error {
  constructor(public code: string, message: string) { super(message) }
}

const DOWN = 'The engine is not running (expected on port 8020). Start it from the dock launcher or run engine/run.sh.'

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const q = new URLSearchParams(params).toString()
  let r: Response
  try { r = await fetch(`/api/${path}${q ? `?${q}` : ''}`) } catch { throw new ApiFailure('ENGINE_DOWN', DOWN) }
  const body = await r.json().catch(() => null)
  if (r.ok && body) return body as T
  if (!body && r.status >= 500) throw new ApiFailure('ENGINE_DOWN', DOWN)
  throw new ApiFailure(body?.code ?? `HTTP_${r.status}`, body?.message ?? `Engine answered ${r.status}.`)
}

export const api = {
  health: () => get<{ ok: boolean; alpaca_keys_present: boolean }>('health'),
  bars: (asset: Asset, symbol: string, tf: Timeframe, start: string, end: string) =>
    get<BarsResponse>('bars', { asset, symbol, tf, start, end }),
  expirations: (underlying: string, on: string) =>
    get<{ underlying: string; on: string; expirations: string[] }>('options/expirations', { underlying, on }),
  chain: (underlying: string, expiration: string, on: string) => get<Chain>('options/chain', { underlying, expiration, on }),
}
```

<!-- file: web3d/src/panels/ComingNext.tsx -->
```tsx
import type { Asset } from '../model/types'

const WHAT = { scanner: 'Scans for this asset class', strategies: 'Every strategy tried, with P&L, win rate and drawdown' }

export function ComingNext({ computer, asset }: { computer: 'scanner' | 'strategies'; asset: Asset }) {
  return (
    <div className="comingnext">
      <h3>{WHAT[computer]}</h3>
      <p className="muted">Comes next. This tab will hold the {asset === 'etfs' ? 'ETF' : asset} view once strategies exist.</p>
    </div>
  )
}
```

<!-- file: web3d/src/panels/ChartPane.tsx -->
```tsx
import { useMemo } from 'react'
import type { Bar, Timeframe } from '../model/types'
import { revealed } from '../model/replay'
import { useReplay } from '../hooks/useReplay'
import { ChartView } from './ChartView'
import { ReplayBar } from './ReplayBar'

interface Props { title: string; tf: Timeframe; bars: Bar[]; companion?: { title: string; bars: Bar[] } }

/** Main chart under the replay clock; an optional companion (the option's underlying) is cut to the same time. */
export function ChartPane({ title, tf, bars, companion }: Props) {
  const replay = useReplay(bars.length, title + tf + (bars[0]?.t ?? ''))
  const shown = useMemo(() => revealed(bars, replay.state), [bars, replay.state])
  const now = shown[shown.length - 1]?.t
  const companionShown = useMemo(
    () => (companion && now ? companion.bars.filter(b => b.t <= now) : []),
    [companion, now],
  )
  return (
    <div className="chartpane">
      <ReplayBar n={bars.length} replay={replay} time={now} />
      {companion && <ChartView bars={companionShown} tf={tf} title={companion.title} height={170} />}
      <ChartView bars={shown} tf={tf} title={title} height={companion ? 330 : 440} />
    </div>
  )
}
```

<!-- file: web3d/src/panels/OptionsPicker.tsx -->
```tsx
import { useEffect, useMemo, useState } from 'react'
import { api, ApiFailure } from '../net/api'
import type { Chain, Contract } from '../model/types'

const UNDERLYINGS = ['SPY', 'QQQ', 'IWM']
export const OPTIONS_START = '2024-02-01'

interface Props { day: string; onDay: (d: string) => void; onPick: (c: Contract, underlying: string) => void; picked: string | null }

/** Underlying + date -> expirations -> strike ladder (calls left, puts right, ATM highlighted). */
export function OptionsPicker({ day, onDay, onPick, picked }: Props) {
  const [underlying, setUnderlying] = useState('SPY')
  const [exps, setExps] = useState<string[]>([])
  const [exp, setExp] = useState<string | null>(null)
  const [chain, setChain] = useState<Chain | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const early = day < OPTIONS_START

  useEffect(() => {
    setExps([]); setExp(null); setChain(null); setError(null)
    if (early || !underlying) return
    setBusy(true)
    api.expirations(underlying, day)
      .then(r => { setExps(r.expirations); setExp(r.expirations[0] ?? null) })
      .catch((e: ApiFailure) => setError(e.message))
      .finally(() => setBusy(false))
  }, [underlying, day, early])

  useEffect(() => {
    setChain(null)
    if (!exp) return
    setBusy(true)
    api.chain(underlying, exp, day).then(setChain).catch((e: ApiFailure) => setError(e.message)).finally(() => setBusy(false))
  }, [underlying, exp, day])

  const rows = useMemo(() => {
    if (!chain) return []
    const by = new Map<number, { call?: Contract; put?: Contract }>()
    for (const c of chain.contracts) by.set(c.strike, { ...by.get(c.strike), [c.type]: c })
    let strikes = [...by.keys()].sort((a, b) => a - b)
    const close = chain.underlying_close
    if (close != null) {  // keep the ladder readable: 15 strikes either side of the money
      const atm = strikes.reduce((best, s) => (Math.abs(s - close) < Math.abs(best - close) ? s : best), strikes[0])
      const i = strikes.indexOf(atm)
      strikes = strikes.slice(Math.max(0, i - 15), i + 16)
    }
    return strikes.map(s => ({ strike: s, ...by.get(s)! }))
  }, [chain])
  const atm = chain?.underlying_close != null && rows.length
    ? rows.reduce((b, r) => (Math.abs(r.strike - chain.underlying_close!) < Math.abs(b.strike - chain.underlying_close!) ? r : b)).strike
    : null

  const cell = (c: Contract | undefined, u: string) => c
    ? <button className={c.symbol === picked ? 'picked' : ''} onClick={() => onPick(c, u)}>{c.type === 'call' ? 'C' : 'P'}</button>
    : <span className="muted">-</span>

  return (
    <div className="optpicker">
      <div className="formrow">
        <label>Underlying
          <input list="opt-underlyings" value={underlying} onChange={e => setUnderlying(e.target.value.toUpperCase())} size={6} />
          <datalist id="opt-underlyings">{UNDERLYINGS.map(u => <option key={u} value={u} />)}</datalist>
        </label>
        <label>Day <input type="date" value={day} min={OPTIONS_START} onChange={e => onDay(e.target.value)} /></label>
        <label>Expiration
          <select value={exp ?? ''} onChange={e => setExp(e.target.value)} disabled={!exps.length}>
            {exps.map(x => <option key={x} value={x}>{x}</option>)}
          </select>
        </label>
        {busy && <span className="muted">loading…</span>}
      </div>
      {early && <p className="warn">Alpaca options history starts {OPTIONS_START}. Pick a later day.</p>}
      {error && <p className="warn">{error}</p>}
      <p className="muted small">Options bars have no historical bid/ask, so fills priced from them look better than live trading.</p>
      {rows.length > 0 && (
        <table className="ladder">
          <thead><tr><th>Call</th><th>Strike</th><th>Put</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.strike} className={r.strike === atm ? 'atm' : ''}>
                <td>{cell(r.call, underlying)}</td><td>{r.strike}{r.strike === atm ? ' ATM' : ''}</td><td>{cell(r.put, underlying)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

<!-- file: web3d/src/panels/BacktestTab.tsx -->
```tsx
import { useState } from 'react'
import { api, ApiFailure } from '../net/api'
import { lastSession } from '../model/dates'
import { TIMEFRAMES, type Asset, type Bar, type Contract, type Timeframe } from '../model/types'
import { ChartPane } from './ChartPane'
import { OptionsPicker } from './OptionsPicker'

const DEFAULTS: Record<Exclude<Asset, 'options'>, string[]> = {
  stocks: ['AAPL', 'NVDA', 'TSLA'], etfs: ['SPY', 'QQQ', 'IWM'], crypto: ['BTC/USD', 'ETH/USD'],
}

interface Loaded { title: string; tf: Timeframe; bars: Bar[]; companion?: { title: string; bars: Bar[] } }

/** Pick a symbol (or an option contract), a timeframe and dates; load bars from the engine; replay them. */
export function BacktestTab({ asset }: { asset: Asset }) {
  const [symbol, setSymbol] = useState(asset === 'options' ? '' : DEFAULTS[asset][0])
  const [tf, setTf] = useState<Timeframe>(asset === 'crypto' ? '15Min' : '5Min')
  const [start, setStart] = useState(lastSession(new Date()))
  const [end, setEnd] = useState(lastSession(new Date()))
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [underlying, setUnderlying] = useState<string | null>(null)

  const load = async (sym = symbol, u = underlying) => {
    if (!sym) return
    setBusy(true); setError(null)
    try {
      const main = await api.bars(asset, sym, tf, start, end)
      const companion = asset === 'options' && u
        ? await api.bars('etfs', u, tf, start, end).then(r => ({ title: r.symbol, bars: r.bars })).catch(() => undefined)
        : undefined
      setLoaded({ title: main.symbol, tf, bars: main.bars, companion })
    } catch (e) {
      setError((e as ApiFailure).message); setLoaded(null)
    } finally { setBusy(false) }
  }

  const pickContract = (c: Contract, u: string) => {
    setSymbol(c.symbol); setUnderlying(u)
    void load(c.symbol, u)
  }

  return (
    <div className="backtesttab">
      {asset === 'options' && (
        <OptionsPicker day={start} picked={symbol || null} onPick={pickContract}
          onDay={d => { setStart(d); setEnd(d) }} />
      )}
      <form className="formrow" onSubmit={e => { e.preventDefault(); void load() }}>
        <label>{asset === 'options' ? 'Contract' : 'Symbol'}
          <input list={`syms-${asset}`} value={symbol} size={asset === 'options' ? 22 : 9}
            placeholder={asset === 'options' ? 'SPY261120C00600000' : ''}
            onChange={e => setSymbol(e.target.value.toUpperCase())} />
          {asset !== 'options' && <datalist id={`syms-${asset}`}>{DEFAULTS[asset].map(s => <option key={s} value={s} />)}</datalist>}
        </label>
        <label>Timeframe
          <select value={tf} onChange={e => setTf(e.target.value as Timeframe)}>{TIMEFRAMES.map(t => <option key={t}>{t}</option>)}</select>
        </label>
        <label>From <input type="date" value={start} onChange={e => setStart(e.target.value)} /></label>
        <label>To <input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
        <button type="submit" disabled={busy || !symbol}>{busy ? 'Loading…' : 'Load'}</button>
      </form>
      {error && <p className="warn" role="alert">{error}</p>}
      {loaded
        ? <ChartPane title={loaded.title} tf={loaded.tf} bars={loaded.bars} companion={loaded.companion} />
        : !error && <p className="muted">{asset === 'options' ? 'Pick a contract from the ladder, or type one.' : 'Pick a symbol and press Load.'}</p>}
    </div>
  )
}
```

<!-- file: web3d/src/panels/ComputerPanel.tsx -->
```tsx
import { useEffect, useState } from 'react'
import type { PanelAction, PanelState } from '../model/panel'
import { ASSET_TABS, type Asset } from '../model/types'
import { computerById } from '../config/computers'
import { BacktestTab } from './BacktestTab'
import { ComingNext } from './ComingNext'

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void }

/** The open computer: asset tabs over the 3D room. Esc or Close flies the camera back. */
export function ComputerPanel({ panel, dispatch }: Props) {
  const [asset, setAsset] = useState<Asset>('etfs')
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dispatch({ type: 'close' }) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dispatch])
  if (panel.phase !== 'open' || !panel.computer) return null
  const c = computerById(panel.computer)
  return (
    <section className="computerpanel" role="dialog" aria-label={`${c.label} computer`}>
      <header>
        <h2>{c.label}</h2>
        <nav className="tabs" role="tablist">
          {ASSET_TABS.map(t => (
            <button key={t.id} role="tab" aria-selected={asset === t.id} className={asset === t.id ? 'on' : ''} onClick={() => setAsset(t.id)}>{t.label}</button>
          ))}
        </nav>
        <button className="close" onClick={() => dispatch({ type: 'close' })} aria-label="Close computer">✕ Close</button>
      </header>
      <div className="panelbody">
        {c.id === 'backtests' ? <BacktestTab key={asset} asset={asset} /> : <ComingNext computer={c.id} asset={asset} />}
      </div>
    </section>
  )
}
```

<!-- file: web3d/scripts/mock_engine.mjs -->
```js
// Fake engine for front-end work without Alpaca keys. Same /api routes and error shape as engine/backtestceo/server.py.
// node scripts/mock_engine.mjs [--port 8020]   symbol FAIL -> ALPACA_REJECTED, symbol NONE -> EMPTY
import http from 'node:http'

const port = Number(process.argv[process.argv.indexOf('--port') + 1]) || 8020
const STEP = { '1Min': 1, '5Min': 5, '15Min': 15, '1Hour': 60, '1Day': 1440 }

function rng(seed) { let s = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7); return () => ((s = (s * 1103515245 + 12345) | 0) >>> 0) / 4294967296 }

function bars(asset, symbol, tf, start, end) {
  const r = rng(symbol + tf), out = []
  let price = asset === 'options' ? 4 + r() * 6 : asset === 'crypto' ? 60000 : 100 + r() * 500
  const step = STEP[tf]
  for (let d = new Date(start + 'T00:00:00Z'); d <= new Date(end + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1)) {
    const wd = d.getUTCDay()
    if (asset !== 'crypto' && (wd === 0 || wd === 6)) continue
    const [from, to] = tf === '1Day' ? [asset === 'crypto' ? 0 : 240, asset === 'crypto' ? 1 : 241] : asset === 'crypto' ? [0, 1440] : [810, 1200]
    for (let m = from; m < to; m += step) {
      const o = price, c = Math.max(0.05, o * (1 + (r() - 0.5) * 0.004 * Math.sqrt(step)))
      out.push({ t: new Date(d.getTime() + m * 60000).toISOString().replace('.000', ''), o, h: Math.max(o, c) * (1 + r() * 0.001), l: Math.min(o, c) * (1 - r() * 0.001), c, v: Math.round(1000 + r() * 50000) })
      price = c
    }
  }
  return out
}

function fridays(on, k) { const d = new Date(on + 'T00:00:00Z'), out = []; while (out.length < k) { d.setUTCDate(d.getUTCDate() + 1); if (d.getUTCDay() === 5) out.push(d.toISOString().slice(0, 10)) } return out }

const send = (res, status, body) => { res.writeHead(status, { 'content-type': 'application/json' }); res.end(JSON.stringify(body)) }

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'), q = Object.fromEntries(u.searchParams)
  if (u.pathname === '/api/health') return send(res, 200, { ok: true, alpaca_keys_present: false })
  if (u.pathname === '/api/bars') {
    const sym = (q.symbol || '').toUpperCase()
    if (sym === 'FAIL') return send(res, 400, { code: 'ALPACA_REJECTED', message: 'Alpaca answered 422: invalid symbol (mock)' })
    if (q.asset === 'options' && q.start < '2024-02-01') return send(res, 400, { code: 'OPTIONS_TOO_EARLY', message: 'Alpaca options history starts 2024-02-01.' })
    const b = sym === 'NONE' ? [] : bars(q.asset, sym, q.tf, q.start, q.end)
    if (!b.length) return send(res, 404, { code: 'EMPTY', message: `No bars for ${sym} between ${q.start} and ${q.end}.` })
    return send(res, 200, { symbol: sym, asset: q.asset, tf: q.tf, bars: b })
  }
  if (u.pathname === '/api/options/expirations') return send(res, 200, { underlying: q.underlying, on: q.on, expirations: fridays(q.on, 6) })
  if (u.pathname === '/api/options/chain') {
    const atm = 600, yy = q.expiration.slice(2, 4) + q.expiration.slice(5, 7) + q.expiration.slice(8, 10), contracts = []
    for (let s = atm - 25; s <= atm + 25; s++) for (const t of ['call', 'put'])
      contracts.push({ symbol: `${q.underlying}${yy}${t === 'call' ? 'C' : 'P'}${String(s * 1000).padStart(8, '0')}`, type: t, strike: s })
    return send(res, 200, { underlying: q.underlying, expiration: q.expiration, underlying_close: 600.4, contracts })
  }
  send(res, 404, { code: 'NOT_FOUND', message: 'unknown route' })
}).listen(port, () => console.log(`mock engine on http://127.0.0.1:${port}`))
```

- [ ] **Step 4: Run, expect PASS** (`npx vitest run`).
- [ ] **Step 5: Commit** — `feat(web3d): engine client, computer panel, backtest tab, options picker, mock engine`

---

### Task 6: The 3D room

Port of `docs/reference/ceo-command.html` (approved look) into R3F components. Geometry, colours and
sizes follow that file; the code below is the port.

**Files:** Create `web3d/src/scene/{particles,textures}.ts`, `web3d/src/scene/{Figure,Label,Room,Table,Ceo,AgentSeat,Operator,ComputerWall,CameraRig,Scene}.tsx`,
`web3d/src/App.tsx`, `web3d/src/main.tsx`, `web3d/src/styles.css`. Test `web3d/tests/particles.test.ts`.

**Interfaces:**
- Consumes: `SEATS`, `COMPUTERS`, wall constants, camera functions, `PanelState`, `PanelAction`, `ComputerPanel`, `api.health`.
- Produces: `figurePoints(seated, density, rand)`, `mulberry32(seed)`, `<Scene panel dispatch />`, `App`.

- [ ] **Step 1: Failing test**

<!-- file: web3d/tests/particles.test.ts -->
```ts
import { describe, expect, it } from 'vitest'
import { figurePoints, mulberry32 } from '../src/scene/particles'

const ys = (a: Float32Array) => a.filter((_, i) => i % 3 === 1)

describe('figurePoints', () => {
  it('is deterministic for a seed', () => {
    expect(figurePoints(false, 1, mulberry32(4)).body).toEqual(figurePoints(false, 1, mulberry32(4)).body)
  })
  it('a standing figure spans floor to shoulders, head above', () => {
    const f = figurePoints(false, 1, mulberry32(1))
    expect(Math.min(...ys(f.body))).toBeGreaterThan(-0.1)
    expect(Math.max(...ys(f.body))).toBeLessThan(1.6)
    expect(f.headPivot[1]).toBeCloseTo(1.47)
  })
  it('a seated figure is lower', () => {
    expect(Math.max(...ys(figurePoints(true, 1, mulberry32(1)).body))).toBeLessThan(1.15)
  })
  it('density scales the point count', () => {
    expect(figurePoints(false, 2, mulberry32(1)).body.length).toBeGreaterThan(figurePoints(false, 1, mulberry32(1)).body.length * 1.9)
  })
})
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

<!-- file: web3d/src/scene/particles.ts -->
```ts
export type Rand = () => number
type V = [number, number, number]

export function mulberry32(seed: number): Rand {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const cross = (a: V, b: V): V => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
const norm = (a: V): V => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l] }

/** Points on (and a few inside) a capsule from a to b; sx/sz flatten it (torso). */
function seg(out: number[], a: V, b: V, r: number, n: number, rand: Rand, sx = 1, sz = 1) {
  const d: V = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]
  const dir = norm(d)
  const u = norm(cross(dir, Math.abs(dir[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0]))
  const v = cross(dir, u)
  for (let i = 0; i < Math.round(n); i++) {
    const t = rand(), ang = rand() * Math.PI * 2
    const rr = r * (rand() < 0.2 ? rand() : 0.85 + rand() * 0.15)
    const c = Math.cos(ang) * rr, s = Math.sin(ang) * rr
    out.push(a[0] + d[0] * t + (u[0] * c + v[0] * s) * sx, a[1] + d[1] * t + u[1] * c + v[1] * s, a[2] + d[2] * t + (u[2] * c + v[2] * s) * sz)
  }
}

export interface FigurePoints { body: Float32Array; head: Float32Array; headPivot: V }

/** Particle human facing +z. Standing: feet at y=0, about 1.85 tall. Seated: on a seat at y~0.5. */
export function figurePoints(seated: boolean, density: number, rand: Rand): FigurePoints {
  const b: number[] = [], h: number[] = [], k = density
  if (!seated) {
    seg(b, [0, 0.98, 0], [0, 1.42, 0], 0.19, 900 * k, rand, 1.25, 0.65)
    seg(b, [0, 1.42, 0], [0, 1.5, 0], 0.06, 80 * k, rand)
    seg(b, [-0.25, 1.4, 0], [-0.3, 1.1, 0.02], 0.055, 200 * k, rand)
    seg(b, [0.25, 1.4, 0], [0.3, 1.1, 0.02], 0.055, 200 * k, rand)
    seg(b, [-0.3, 1.1, 0.02], [-0.33, 0.82, 0.08], 0.045, 160 * k, rand)
    seg(b, [0.3, 1.1, 0.02], [0.33, 0.82, 0.08], 0.045, 160 * k, rand)
    seg(b, [-0.1, 0.98, 0], [-0.12, 0.5, 0], 0.075, 260 * k, rand)
    seg(b, [0.1, 0.98, 0], [0.12, 0.5, 0], 0.075, 260 * k, rand)
    seg(b, [-0.12, 0.5, 0], [-0.13, 0.04, 0.02], 0.055, 220 * k, rand)
    seg(b, [0.12, 0.5, 0], [0.13, 0.04, 0.02], 0.055, 220 * k, rand)
  } else {
    seg(b, [0, 0.56, -0.05], [0, 1.0, -0.1], 0.19, 900 * k, rand, 1.25, 0.65)
    seg(b, [0, 1.0, -0.1], [0, 1.08, -0.1], 0.06, 80 * k, rand)
    seg(b, [-0.25, 0.98, -0.1], [-0.29, 0.72, 0.05], 0.055, 200 * k, rand)
    seg(b, [0.25, 0.98, -0.1], [0.29, 0.72, 0.05], 0.055, 200 * k, rand)
    seg(b, [-0.29, 0.72, 0.05], [-0.24, 0.7, 0.38], 0.045, 160 * k, rand)
    seg(b, [0.29, 0.72, 0.05], [0.24, 0.7, 0.38], 0.045, 160 * k, rand)
    seg(b, [-0.11, 0.56, 0], [-0.13, 0.56, 0.46], 0.075, 260 * k, rand)
    seg(b, [0.11, 0.56, 0], [0.13, 0.56, 0.46], 0.075, 260 * k, rand)
    seg(b, [-0.13, 0.56, 0.46], [-0.14, 0.06, 0.52], 0.055, 220 * k, rand)
    seg(b, [0.13, 0.56, 0.46], [0.14, 0.06, 0.52], 0.055, 220 * k, rand)
  }
  for (let i = 0; i < Math.round(520 * k); i++) {
    const t = Math.acos(2 * rand() - 1), p = rand() * Math.PI * 2
    const r = 0.115 * (rand() < 0.15 ? rand() : 1)
    h.push(r * Math.sin(t) * Math.cos(p), 0.16 + r * 1.2 * Math.cos(t), r * Math.sin(t) * Math.sin(p))
  }
  return { body: new Float32Array(b), head: new Float32Array(h), headPivot: seated ? [0, 1.05, -0.1] : [0, 1.47, 0] }
}
```

<!-- file: web3d/src/scene/textures.ts -->
```ts
import * as THREE from 'three'
import { mulberry32 } from './particles'

let dot: THREE.Texture | null = null
/** Soft round sprite for particles. */
export function dotTexture(): THREE.Texture {
  if (dot) return dot
  const c = document.createElement('canvas'); c.width = c.height = 64
  const g = c.getContext('2d')!, gr = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.3, 'rgba(255,255,255,.6)'); gr.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64)
  return (dot = new THREE.CanvasTexture(c))
}

export interface LabelLine { text: string; big?: boolean }

/** White first line, coloured lines under it; sized so 230 px = 1 world unit. */
export function labelTexture(lines: LabelLine[], color: string): THREE.CanvasTexture {
  const c = document.createElement('canvas'), big = !!lines[0]?.big
  c.width = 512; c.height = 40 + lines.length * 44 + (big ? 24 : 0)
  const g = c.getContext('2d')!
  g.textAlign = 'center'; g.shadowColor = 'rgba(0,0,0,.9)'; g.shadowBlur = 6
  lines.forEach((l, i) => {
    g.font = (i === 0 ? `700 ${l.big ? 64 : 34}` : '500 26') + 'px "Segoe UI", Helvetica, Arial, sans-serif'
    g.fillStyle = i === 0 ? '#ffffff' : color
    g.fillText(l.text, 256, 52 + i * 42 + (big && i > 0 ? 24 : 0))
  })
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace
  return t
}

function drawChartLines(g: CanvasRenderingContext2D, w: number, h: number, y0: number, color: string, seed: number) {
  const r = mulberry32(seed)
  g.strokeStyle = color; g.fillStyle = color
  g.globalAlpha = 0.18; g.lineWidth = 1
  for (let x = 30; x < w - 10; x += 34) { g.beginPath(); g.moveTo(x, y0); g.lineTo(x, h - 20); g.stroke() }
  for (let y = y0 + 10; y < h - 20; y += 28) { g.beginPath(); g.moveTo(14, y); g.lineTo(w - 14, y); g.stroke() }
  g.globalAlpha = 0.95; g.shadowColor = color; g.shadowBlur = 6
  const kind = r()
  if (kind < 0.55) {
    g.lineWidth = 2.5; g.beginPath(); let y = (y0 + h) / 2
    for (let x = 16; x < w - 14; x += 4) { y = Math.max(y0 + 8, Math.min(h - 25, y + (r() - 0.5) * 18)); g.lineTo(x, y) }
    g.stroke()
  } else if (kind < 0.8) {
    let y = (y0 + h) / 2
    for (let x = 22; x < w - 18; x += 12) {
      const o = y, c = Math.max(y0 + 10, Math.min(h - 30, y + (r() - 0.5) * 30))
      const hi = Math.min(o, c) - r() * 12, lo = Math.max(o, c) + r() * 12
      g.fillRect(x + 3, hi, 1.5, lo - hi); g.fillRect(x, Math.min(o, c), 7, Math.max(2, Math.abs(c - o))); y = c
    }
  } else {
    for (let y = y0 + 6; y < h - 30; y += 13) { g.fillRect(18, y, 70, 4); g.fillRect(110, y, 40 + r() * 60, 4); g.fillRect(260, y, 30 + r() * 80, 4) }
  }
  g.shadowBlur = 0
}

/** Decorative wall screen: frame plus a random chart. */
export function screenTexture(color: string, seed: number): THREE.CanvasTexture {
  const c = document.createElement('canvas'); c.width = 384; c.height = 240
  const g = c.getContext('2d')!
  g.strokeStyle = color; g.fillStyle = color
  g.globalAlpha = 0.1; g.fillRect(6, 6, 372, 228); g.globalAlpha = 0.9; g.lineWidth = 2; g.strokeRect(6, 6, 372, 228)
  drawChartLines(g, 384, 240, 20, color, seed)
  return new THREE.CanvasTexture(c)
}

/** A clickable computer: big title bar, chart body, LIVE or NEXT badge. */
export function computerTexture(label: string, live: boolean, hot: boolean, seed: number): THREE.CanvasTexture {
  const c = document.createElement('canvas'); c.width = 640; c.height = 400
  const g = c.getContext('2d')!, col = hot ? '#bfefff' : '#6cc8ff'
  g.fillStyle = 'rgba(20,70,140,0.35)'; g.fillRect(0, 0, 640, 400)
  g.strokeStyle = col; g.lineWidth = hot ? 7 : 4; g.strokeRect(4, 4, 632, 392)
  g.fillStyle = 'rgba(40,140,255,0.35)'; g.fillRect(4, 4, 632, 78)
  g.font = '700 50px "Segoe UI", Helvetica, Arial, sans-serif'; g.textAlign = 'left'; g.fillStyle = '#ffffff'
  g.shadowColor = col; g.shadowBlur = 12; g.fillText(label, 26, 62); g.shadowBlur = 0
  g.font = '700 24px "Segoe UI", Helvetica, Arial, sans-serif'; g.textAlign = 'right'
  g.fillStyle = live ? '#2fd27a' : '#9fb4d8'; g.fillText(live ? '● LIVE' : 'NEXT', 612, 56)
  drawChartLines(g, 640, 400, 100, col, seed)
  g.font = '500 22px "Segoe UI", Helvetica, Arial, sans-serif'; g.textAlign = 'center'; g.fillStyle = '#d8f2ff'
  g.fillText('click to open', 320, 384)
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace
  return t
}
```

<!-- file: web3d/src/scene/Figure.tsx -->
```tsx
import { useMemo } from 'react'
import * as THREE from 'three'
import { figurePoints, mulberry32 } from './particles'
import { dotTexture } from './textures'

interface Props { seated?: boolean; color: number; density: number; size: number; headTilt?: number; seed: number; material?: THREE.PointsMaterial }

export function pointsMaterial(color: number, size: number, opacity = 0.9) {
  return new THREE.PointsMaterial({ color, size, map: dotTexture(), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false })
}

/** Particle hologram of a person facing +z. */
export function Figure({ seated = false, color, density, size, headTilt = 0, seed, material }: Props) {
  const pts = useMemo(() => figurePoints(seated, density, mulberry32(seed)), [seated, density, seed])
  const mat = useMemo(() => material ?? pointsMaterial(color, size), [material, color, size])
  return (
    <group>
      <points material={mat}>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[pts.body, 3]} /></bufferGeometry>
      </points>
      <group position={pts.headPivot} rotation-x={headTilt}>
        <points material={mat}>
          <bufferGeometry><bufferAttribute attach="attributes-position" args={[pts.head, 3]} /></bufferGeometry>
        </points>
      </group>
    </group>
  )
}
```

<!-- file: web3d/src/scene/Label.tsx -->
```tsx
import { useMemo } from 'react'
import { labelTexture, type LabelLine } from './textures'

interface Props { lines: LabelLine[]; color: string; position: [number, number, number]; scale?: number }

/** Camera-facing text sprite. */
export function Label({ lines, color, position, scale = 1 }: Props) {
  const key = lines.map(l => l.text).join('|')
  const tex = useMemo(() => labelTexture(lines, color), [key, color]) // eslint-disable-line react-hooks/exhaustive-deps
  const img = tex.image as HTMLCanvasElement
  return (
    <sprite position={position} scale={[(img.width / 230) * scale, (img.height / 230) * scale, 1]}>
      <spriteMaterial map={tex} transparent depthWrite={false} />
    </sprite>
  )
}
```

<!-- file: web3d/src/scene/Room.tsx -->
```tsx
import * as THREE from 'three'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const

/** Circular dark room: walls with neon strips, ceiling ring and light bars, floor grid rings. */
export function Room() {
  return (
    <group>
      <mesh position={[0, 5, 0]}>
        <cylinderGeometry args={[13, 13, 12, 64, 1, true]} />
        <meshStandardMaterial color={0x070a16} side={THREE.BackSide} metalness={0.4} roughness={0.7} />
      </mesh>
      {Array.from({ length: 16 }, (_, i) => {
        const a = (i / 16) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.sin(a) * 12.7, 3, Math.cos(a) * 12.7]}>
            <boxGeometry args={[0.05, 3.5, 0.05]} />
            <meshBasicMaterial color={i % 4 === 0 ? 0xa05cff : 0x2f8fff} />
          </mesh>
        )
      })}
      <mesh rotation-x={Math.PI / 2} position={[0, 8, 0]}>
        <torusGeometry args={[6.5, 0.03, 8, 128]} />
        <meshBasicMaterial color={0x3fc8ff} />
      </mesh>
      {Array.from({ length: 18 }, (_, i) => {
        const a = (i / 18) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.sin(a) * 9.5, 8.6, Math.cos(a) * 9.5]} rotation-y={a + Math.PI / 2}>
            <boxGeometry args={[1.4, 0.04, 0.04]} />
            <meshBasicMaterial color={i % 2 ? 0xa05cff : 0x3fa8ff} />
          </mesh>
        )
      })}
      <mesh rotation-x={-Math.PI / 2}>
        <circleGeometry args={[13, 64]} />
        <meshStandardMaterial color={0x04060c} metalness={0.3} roughness={0.85} />
      </mesh>
      {[5, 6.6, 8.2, 9.8, 11.4].map(r => (
        <mesh key={r} rotation-x={-Math.PI / 2} position-y={0.005}>
          <ringGeometry args={[r, r + 0.015, 96]} />
          <meshBasicMaterial color={0x2a5cff} opacity={0.25} {...additive} />
        </mesh>
      ))}
    </group>
  )
}
```

<!-- file: web3d/src/scene/Table.tsx -->
```tsx
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { screenTexture } from './textures'

export const TABLE_H = 0.95
export const TABLE_R = 3

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
const RINGS: [number, number, number, number][] = [
  [0.3, 0.35, 0x8fe4ff, 0.95], [0.5, 0.54, 0x5fd8ff, 0.8], [0.72, 0.77, 0x5fd8ff, 0.7], [0.95, 0.99, 0x3fa8ff, 0.6],
  [1.25, 1.31, 0xb070ff, 0.85], [1.6, 1.62, 0x5fd8ff, 0.4], [2.15, 2.18, 0x3fa8ff, 0.35],
]

function summaryTexture() {
  const c = document.createElement('canvas'); c.width = 512; c.height = 220
  const g = c.getContext('2d')!
  g.strokeStyle = g.fillStyle = '#6cc8ff'; g.lineWidth = 3
  g.globalAlpha = 0.12; g.fillRect(4, 4, 504, 212); g.globalAlpha = 1; g.strokeRect(4, 4, 504, 212)
  g.textAlign = 'center'; g.fillStyle = '#ffffff'; g.font = '700 30px "Segoe UI", Arial, sans-serif'; g.fillText('EXECUTIVE SUMMARY', 256, 50)
  g.fillStyle = '#6cc8ff'; g.font = '500 18px "Segoe UI", Arial, sans-serif'; g.fillText('SYNTHESIZING AGENT REPORTS', 256, 78)
  g.lineWidth = 2; g.beginPath()
  for (let x = 30; x < 482; x += 3) g.lineTo(x, 150 + Math.sin(x * 0.09) * 18 * Math.sin(x * 0.013) + Math.sin(x * 1.7) * 6)
  g.stroke()
  return new THREE.CanvasTexture(c)
}

/** Round strategy table: glowing edge, spinning rings, light column, rim dashboards, executive summary panel. */
export function Table() {
  const rings = useRef<(THREE.Mesh | null)[]>([])
  const beam = useRef<THREE.MeshBasicMaterial>(null)
  const dash = useMemo(() => Array.from({ length: 10 }, (_, i) => screenTexture('#5fc8ff', 100 + i)), [])
  const summary = useMemo(summaryTexture, [])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    rings.current.forEach((m, i) => { if (m) m.rotation.z = t * (i % 2 ? -0.15 : 0.25) * (1 + i * 0.1) })
    if (beam.current) beam.current.opacity = 0.045 + Math.sin(t * 1.5) * 0.015
  })
  return (
    <group>
      <mesh position-y={TABLE_H / 2}>
        <cylinderGeometry args={[TABLE_R, TABLE_R + 0.2, TABLE_H, 72]} />
        <meshStandardMaterial color={0x0a0d1a} metalness={0.75} roughness={0.3} />
      </mesh>
      <mesh rotation-x={Math.PI / 2} position-y={TABLE_H}>
        <torusGeometry args={[TABLE_R, 0.022, 8, 128]} />
        <meshBasicMaterial color={0x5fd8ff} />
      </mesh>
      {RINGS.map(([a, b, c, o], i) => (
        <mesh key={i} ref={m => { rings.current[i] = m }} rotation-x={-Math.PI / 2} position-y={TABLE_H + 0.01 + i * 0.002}>
          <ringGeometry args={[a, b, 96, 1, 0, i % 2 === 0 ? Math.PI * 1.6 : Math.PI * 2]} />
          <meshBasicMaterial color={c} opacity={o} {...additive} />
        </mesh>
      ))}
      <mesh rotation-x={-Math.PI / 2} position-y={TABLE_H + 0.008}>
        <circleGeometry args={[1, 48]} />
        <meshBasicMaterial color={0x1f6fff} opacity={0.25} {...additive} />
      </mesh>
      <mesh position-y={TABLE_H + 2.3}>
        <cylinderGeometry args={[0.55, 0.9, 4.6, 48, 1, true]} />
        <meshBasicMaterial ref={beam} color={0x3fa8ff} opacity={0.05} {...additive} />
      </mesh>
      {dash.map((tex, i) => {
        const a = (i / 10) * Math.PI * 2 + 0.3
        return (
          <mesh key={i} position={[Math.sin(a) * 2.45, TABLE_H + 0.03, Math.cos(a) * 2.45]} rotation={[-Math.PI / 2 + 0.25, a, 0, 'YXZ']}>
            <planeGeometry args={[0.8, 0.5]} />
            <meshBasicMaterial map={tex} opacity={0.55} {...additive} />
          </mesh>
        )
      })}
      <mesh position={[0, TABLE_H + 0.32, TABLE_R - 0.15]} rotation-x={-0.35}>
        <planeGeometry args={[1.6, 0.69]} />
        <meshBasicMaterial map={summary} opacity={0.95} {...additive} />
      </mesh>
    </group>
  )
}
```

<!-- file: web3d/src/scene/Ceo.tsx -->
```tsx
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Figure, pointsMaterial } from './Figure'
import { Label } from './Label'
import { TABLE_H } from './Table'

export const CEO_SCALE = 1.75
export const CEO_CHEST = new THREE.Vector3(0, TABLE_H + 1.25 * CEO_SCALE, 0)
const RAIN = 700

/** The CEO: a blue particle hologram standing full-body on the table, with data rising through it. */
export function Ceo() {
  const body = useRef<THREE.Group>(null)
  const mat = useMemo(() => pointsMaterial(0x6fdcff, 0.032), [])
  const rainMat = useMemo(() => pointsMaterial(0x6fd4ff, 0.035, 0.5), [])
  const rainPos = useMemo(() => {
    const a = new Float32Array(RAIN * 3)
    for (let i = 0; i < RAIN; i++) {
      const ang = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * 0.85
      a.set([Math.cos(ang) * r, Math.random() * 4.4, Math.sin(ang) * r], i * 3)
    }
    return a
  }, [])
  const rainGeo = useRef<THREE.BufferGeometry>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (body.current) body.current.position.y = TABLE_H + 0.02 + Math.sin(t * 0.8) * 0.025
    mat.size = 0.032 + Math.sin(t * 2.2) * 0.004
    for (let i = 0; i < RAIN; i++) { let y = rainPos[i * 3 + 1] + 0.012 + (i % 7) * 0.002; if (y > 4.4) y = 0; rainPos[i * 3 + 1] = y }
    if (rainGeo.current) rainGeo.current.attributes.position.needsUpdate = true
  })
  return (
    <group>
      <group ref={body} scale={CEO_SCALE} position-y={TABLE_H}>
        <Figure color={0x6fdcff} density={6} size={0.032} seed={1} material={mat} />
      </group>
      <points material={rainMat} position-y={TABLE_H}>
        <bufferGeometry ref={rainGeo}><bufferAttribute attach="attributes-position" args={[rainPos, 3]} /></bufferGeometry>
      </points>
      <Label lines={[{ text: 'CEO AI', big: true }, { text: 'STRATEGIC OVERSIGHT' }, { text: 'FINAL DECISION AUTHORITY' }]}
        color="#a8e6ff" position={[0, TABLE_H + 2.0, 0.9]} scale={0.6} />
    </group>
  )
}
```

<!-- file: web3d/src/scene/AgentSeat.tsx -->
```tsx
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Seat } from '../config/seats'
import { onArc } from '../model/camera'
import { Figure, pointsMaterial } from './Figure'
import { Label } from './Label'
import { TABLE_R } from './Table'
import { CEO_CHEST } from './Ceo'

const SEAT_R = TABLE_R + 0.75
const LABEL_Y = [2.05, 2.75, 1.8]
const chairMat = new THREE.MeshStandardMaterial({ color: 0x0a0d18, metalness: 0.6, roughness: 0.45 })
const edgeMat = new THREE.LineBasicMaterial({ color: 0x4fb8ff, transparent: true, opacity: 0.35 })

function Part({ geo, pos, rx = 0 }: { geo: THREE.BufferGeometry; pos: [number, number, number]; rx?: number }) {
  const edges = useMemo(() => new THREE.EdgesGeometry(geo), [geo])
  return (
    <group position={pos} rotation-x={rx}>
      <mesh geometry={geo} material={chairMat} />
      <lineSegments geometry={edges} material={edgeMat} />
    </group>
  )
}

/** Office chair facing +z, dark with faint holo edges. */
function Chair() {
  const g = useMemo(() => ({
    seat: new THREE.BoxGeometry(0.62, 0.09, 0.58), back: new THREE.BoxGeometry(0.6, 0.5, 0.07),
    arm: new THREE.BoxGeometry(0.06, 0.05, 0.42), post: new THREE.CylinderGeometry(0.04, 0.04, 0.38, 12),
    base: new THREE.CylinderGeometry(0.3, 0.3, 0.03, 5),
  }), [])
  return (
    <group>
      <Part geo={g.seat} pos={[0, 0.46, 0.05]} />
      <Part geo={g.back} pos={[0, 0.78, -0.33]} rx={-0.12} />
      <Part geo={g.arm} pos={[-0.34, 0.68, 0.02]} />
      <Part geo={g.arm} pos={[0.34, 0.68, 0.02]} />
      <Part geo={g.post} pos={[0, 0.22, 0.05]} />
      <Part geo={g.base} pos={[0, 0.03, 0.05]} />
    </group>
  )
}

/** Seated agent looking up at the CEO, with a label and a data stream arcing to the CEO's chest. */
export function AgentSeat({ seat, index }: { seat: Seat; index: number }) {
  const [x, , z] = onArc(seat.angleDeg, SEAT_R, 0)
  const yaw = (seat.angleDeg * Math.PI) / 180 + Math.PI
  const mat = useMemo(() => pointsMaterial(0x4fb8ff, 0.026), [])
  const head = useRef<THREE.Group>(null)
  const curve = useMemo(() => {
    const start = new THREE.Vector3(x, 0.85, z)
    const mid = start.clone().lerp(CEO_CHEST, 0.5).add(new THREE.Vector3(0, 1.0, 0))
    return new THREE.CatmullRomCurve3([start, mid, CEO_CHEST])
  }, [x, z])
  const streamLine = useMemo(() => new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(60)),
    new THREE.LineBasicMaterial({ color: 0x4fa8ff, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending })), [curve])
  const flow = useMemo(() => new Float32Array(18 * 3), [])
  const flowGeo = useRef<THREE.BufferGeometry>(null)
  const flowMat = useMemo(() => pointsMaterial(0xa8e0ff, 0.085), [])
  const speed = 0.12 + (index % 3) * 0.025
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    mat.opacity = 0.8 + Math.sin(t * 3 + index * 1.3) * 0.12
    const p = new THREE.Vector3()
    for (let j = 0; j < 18; j++) { curve.getPoint((t * speed + j / 18) % 1, p); flow.set([p.x, p.y, p.z], j * 3) }
    if (flowGeo.current) flowGeo.current.attributes.position.needsUpdate = true
  })
  return (
    <group>
      <group position={[x, 0, z]} rotation-y={yaw}>
        <Chair />
        <group ref={head}>
          <Figure seated color={0x4fb8ff} density={1.6} size={0.026} headTilt={-0.75} seed={10 + index} material={mat} />
        </group>
      </group>
      <mesh rotation-x={-Math.PI / 2} position={[x, 0.01, z]}>
        <ringGeometry args={[0.45, 0.5, 64]} />
        <meshBasicMaterial color={0x3fa8ff} opacity={0.4} transparent blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <Label lines={[{ text: seat.name }, { text: seat.job }, { text: '● Live Feed' }]} color="#6cc8ff"
        position={[x * 1.08, LABEL_Y[index % 3], z * 1.08]} scale={0.5} />
      <primitive object={streamLine} />
      <points material={flowMat}>
        <bufferGeometry ref={flowGeo}><bufferAttribute attach="attributes-position" args={[flow, 3]} /></bufferGeometry>
      </points>
    </group>
  )
}
```

<!-- file: web3d/src/scene/Operator.tsx -->
```tsx
import * as THREE from 'three'
import { TABLE_R } from './Table'

const dark = new THREE.MeshStandardMaterial({ color: 0x020307, metalness: 0.3, roughness: 0.8 })

/** You: a dark silhouette in a chair, back to the camera, in the foreground. */
export function Operator() {
  return (
    <group position={[0, -0.55, TABLE_R + 4.3]} scale={1.3}>
      <mesh material={dark} position={[0, 0.95, 0.12]}><boxGeometry args={[0.85, 0.8, 0.14]} /></mesh>
      <mesh material={dark} position={[0, 0.5, -0.3]}><boxGeometry args={[0.95, 0.12, 0.85]} /></mesh>
      <mesh material={dark} position={[0, 0.22, -0.3]}><cylinderGeometry args={[0.06, 0.06, 0.45, 12]} /></mesh>
      <mesh material={dark} position={[0, 1.25, -0.18]} scale={[1, 1, 0.7]}><cylinderGeometry args={[0.36, 0.27, 0.8, 20]} /></mesh>
      <mesh material={dark} position={[-0.36, 1.56, -0.18]}><sphereGeometry args={[0.15, 16, 12]} /></mesh>
      <mesh material={dark} position={[0.36, 1.56, -0.18]}><sphereGeometry args={[0.15, 16, 12]} /></mesh>
      <mesh material={dark} position={[0, 1.7, -0.2]}><cylinderGeometry args={[0.07, 0.08, 0.16, 12]} /></mesh>
      <mesh material={dark} position={[0, 1.86, -0.2]} scale={[1, 1.15, 1]}><sphereGeometry args={[0.17, 24, 16]} /></mesh>
    </group>
  )
}
```

<!-- file: web3d/src/scene/ComputerWall.tsx -->
```tsx
import { useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { COMPUTERS, COMPUTER_H, COMPUTER_W, COMPUTER_Y, WALL_RADIUS, type Computer } from '../config/computers'
import { onArc } from '../model/camera'
import type { ComputerId } from '../model/types'
import { computerTexture, screenTexture } from './textures'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
const DECOR_R = 7.9

function ComputerScreen({ c, index, onPick, disabled }: { c: Computer; index: number; onPick: (id: ComputerId) => void; disabled: boolean }) {
  const [hot, setHot] = useState(false)
  const tex = useMemo(() => computerTexture(c.label, c.live, hot, 300 + index), [c.label, c.live, hot, index])
  const pos = onArc(c.angleDeg, WALL_RADIUS, COMPUTER_Y)
  const yaw = (c.angleDeg * Math.PI) / 180 + Math.PI
  return (
    <group position={pos} rotation-y={yaw}>
      <mesh position-z={-0.03}>
        <planeGeometry args={[COMPUTER_W + 0.12, COMPUTER_H + 0.12]} />
        <meshBasicMaterial color={0x03060f} />
      </mesh>
      <mesh
        onClick={e => { e.stopPropagation(); if (!disabled) onPick(c.id) }}
        onPointerOver={e => { e.stopPropagation(); if (!disabled) { setHot(true); document.body.style.cursor = 'pointer' } }}
        onPointerOut={() => { setHot(false); document.body.style.cursor = '' }}>
        <planeGeometry args={[COMPUTER_W, COMPUTER_H]} />
        <meshBasicMaterial map={tex} opacity={hot ? 1 : 0.85} {...additive} />
      </mesh>
    </group>
  )
}

/** Curved wall of chart screens behind the CEO; three of them are the clickable computers. */
export function ComputerWall({ onPick, disabled }: { onPick: (id: ComputerId) => void; disabled: boolean }) {
  const decor = useMemo(() => {
    const out: { pos: [number, number, number]; yaw: number; tex: THREE.Texture; base: number; phase: number }[] = []
    for (let row = 0; row < 3; row++) for (let col = 0; col < 8; col++) {
      const deg = 130 + col * (100 / 7), y = 1.6 + row * 1.45
      if (row === 1 && COMPUTERS.some(c => Math.abs(c.angleDeg - deg) < 13)) continue
      out.push({ pos: onArc(deg, DECOR_R, y), yaw: (deg * Math.PI) / 180 + Math.PI,
        tex: screenTexture((row * 8 + col) % 7 === 0 ? '#a98bff' : '#5fc8ff', row * 8 + col),
        base: 0.32 + ((row * 8 + col) % 5) * 0.03, phase: row * 3.1 + col * 1.7 })
    }
    return out
  }, [])
  const mats = useMemo(() => decor.map(d => new THREE.MeshBasicMaterial({ map: d.tex, opacity: d.base, ...additive })), [decor])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    mats.forEach((m, i) => { const p = decor[i].phase; m.opacity = decor[i].base + Math.sin(t * 2 + p) * 0.05 + (Math.sin(t * 17 + p * 3) > 0.97 ? -0.25 : 0) })
  })
  return (
    <group>
      {decor.map((d, i) => (
        <mesh key={i} position={d.pos} rotation-y={d.yaw} material={mats[i]}>
          <planeGeometry args={[1.95, 1.22]} />
        </mesh>
      ))}
      {COMPUTERS.map((c, i) => <ComputerScreen key={c.id} c={c} index={i} onPick={onPick} disabled={disabled} />)}
    </group>
  )
}
```

<!-- file: web3d/src/scene/CameraRig.tsx -->
```tsx
import { useEffect, useMemo, type RefObject } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { computerById, COMPUTER_Y, WALL_RADIUS } from '../config/computers'
import { fovFor, poseDistance, roomPose, screenPose, type CamPose } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; controls: RefObject<OrbitControlsImpl | null> }

/** Flies the camera to a computer and back. Orbit controls own the camera only while the panel is closed. */
export function CameraRig({ panel, dispatch, controls }: Props) {
  const { camera, size } = useThree()
  const aspect = size.width / Math.max(1, size.height)
  const reduced = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    cam.fov = fovFor(aspect); cam.updateProjectionMatrix()
  }, [camera, aspect])

  useFrame((_, dt) => {
    if (panel.phase === 'closed' || panel.phase === 'open') return
    const want: CamPose = panel.phase === 'flying' && panel.computer
      ? screenPose(computerById(panel.computer).angleDeg, WALL_RADIUS, COMPUTER_Y)
      : roomPose(aspect)
    const target = controls.current?.target ?? new THREE.Vector3()
    const k = reduced ? 1 : 1 - Math.exp(-dt * 6)
    camera.position.lerp(new THREE.Vector3(...want.pos), k)
    target.lerp(new THREE.Vector3(...want.target), k)
    camera.lookAt(target)
    const now: CamPose = { pos: camera.position.toArray() as CamPose['pos'], target: target.toArray() as CamPose['target'] }
    if (poseDistance(now, want) < 0.03) {
      camera.position.set(...want.pos); target.set(...want.target); camera.lookAt(target)
      dispatch({ type: panel.phase === 'flying' ? 'arrived' : 'returned' })
    }
  })
  return null
}
```

<!-- file: web3d/src/scene/Scene.tsx -->
```tsx
import { useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { SEATS } from '../config/seats'
import { roomPose } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'
import { AgentSeat } from './AgentSeat'
import { CameraRig } from './CameraRig'
import { Ceo } from './Ceo'
import { ComputerWall } from './ComputerWall'
import { Operator } from './Operator'
import { Room } from './Room'
import { Table } from './Table'

const FX_HIGH = new URLSearchParams(window.location.search).get('fx') === 'high'

export function Scene({ panel, dispatch }: { panel: PanelState; dispatch: (a: PanelAction) => void }) {
  const controls = useRef<OrbitControlsImpl>(null)
  const start = roomPose(window.innerWidth / window.innerHeight)
  return (
    <Canvas className="scene" dpr={[1, 2]} camera={{ position: start.pos, fov: 48, near: 0.1, far: 200 }} gl={{ antialias: true }}>
      <color attach="background" args={['#03050b']} />
      <fogExp2 attach="fog" args={['#03050b', 0.028]} />
      <ambientLight color={0x4060ff} intensity={0.3} />
      <pointLight color={0x5fd8ff} intensity={2.4} distance={14} decay={1} position={[0, 4, 1.5]} />
      <pointLight color={0x3a7bff} intensity={1.8} distance={18} decay={1} position={[0, 6, -6]} />
      <Room />
      <Table />
      <Ceo />
      {SEATS.map((s, i) => <AgentSeat key={s.id} seat={s} index={i} />)}
      <Operator />
      <ComputerWall onPick={id => dispatch({ type: 'click', id })} disabled={panel.phase === 'flying' || panel.phase === 'closing'} />
      <OrbitControls ref={controls} target={start.target} enableDamping enablePan={false}
        minPolarAngle={0.95} maxPolarAngle={1.6} minDistance={6} maxDistance={15} enabled={panel.phase === 'closed'} />
      <CameraRig panel={panel} dispatch={dispatch} controls={controls} />
      {FX_HIGH && <EffectComposer><Bloom intensity={0.95} luminanceThreshold={0.2} mipmapBlur /></EffectComposer>}
    </Canvas>
  )
}
```

<!-- file: web3d/src/App.tsx -->
```tsx
import { useEffect, useReducer, useState } from 'react'
import { PANEL_CLOSED, panelReduce } from './model/panel'
import { api } from './net/api'
import { ComputerPanel } from './panels/ComputerPanel'
import { Scene } from './scene/Scene'

type Engine = { state: 'checking' } | { state: 'up'; keys: boolean } | { state: 'down' }

export default function App() {
  const [panel, dispatch] = useReducer(panelReduce, PANEL_CLOSED)
  const [engine, setEngine] = useState<Engine>({ state: 'checking' })
  useEffect(() => {
    const check = () => api.health().then(h => setEngine({ state: 'up', keys: h.alpaca_keys_present })).catch(() => setEngine({ state: 'down' }))
    check()
    const id = setInterval(check, 15000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="app">
      <Scene panel={panel} dispatch={dispatch} />
      <header className="hud">
        <h1>BACKTEST CEO</h1>
        <span className={`engine ${engine.state}`}>
          {engine.state === 'checking' ? 'Engine: checking…'
            : engine.state === 'down' ? 'Engine: not running'
            : engine.keys ? 'Engine: connected' : 'Engine: connected, Alpaca keys missing'}
        </span>
      </header>
      {panel.phase === 'closed' && <p className="hint">Click a computer behind the CEO · drag to orbit</p>}
      <ComputerPanel panel={panel} dispatch={dispatch} />
    </div>
  )
}
```

<!-- file: web3d/src/main.tsx -->
```tsx
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(<App />)
```

<!-- file: web3d/src/styles.css -->
```css
:root {
  --bg: #03050b; --panel: rgba(6, 14, 34, 0.94); --line: #1d3f78; --text: #d8ecff; --muted: #7f9cc4;
  --accent: #6cc8ff; --pos: #2fd27a; --neg: #ff4d6a; --warn: #ffb547;
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body, #root { margin: 0; height: 100%; background: var(--bg); color: var(--text); font: 14px/1.4 system-ui, "Segoe UI", sans-serif; overflow: hidden; }
.app { position: relative; height: 100%; }
.scene { position: absolute !important; inset: 0; }
.hud { position: absolute; top: 12px; left: 16px; right: 16px; display: flex; gap: 16px; align-items: baseline; pointer-events: none; }
.hud h1 { margin: 0; font-size: 15px; letter-spacing: .3em; color: var(--accent); text-shadow: 0 0 10px rgba(108, 200, 255, .7); }
.engine { font-size: 12px; color: var(--muted); }
.engine.down { color: var(--warn); }
.hint { position: absolute; bottom: 14px; left: 16px; margin: 0; color: var(--muted); font-size: 12px; letter-spacing: .08em; }
.muted { color: var(--muted); }
.small { font-size: 12px; }
.pos { color: var(--pos); }
.neg { color: var(--neg); }
.warn { color: var(--warn); }
button, select, input { font: inherit; color: var(--text); background: #0b1a3a; border: 1px solid var(--line); border-radius: 6px; padding: 4px 9px; }
button { cursor: pointer; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .5; cursor: default; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.computerpanel {
  position: absolute; inset: 5vh 4vw; display: flex; flex-direction: column; background: var(--panel);
  border: 1px solid var(--accent); border-radius: 10px; box-shadow: 0 0 40px rgba(60, 160, 255, .35);
  animation: panelin .25s ease-out;
}
@keyframes panelin { from { opacity: 0; transform: translateY(12px) scale(.98); } }
@media (prefers-reduced-motion: reduce) { .computerpanel { animation: none; } }
.computerpanel header { display: flex; gap: 16px; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.computerpanel h2 { margin: 0; font-size: 16px; letter-spacing: .25em; color: var(--accent); }
.tabs { display: flex; gap: 6px; }
.tabs .on { background: #1a4a8a; border-color: var(--accent); }
.close { margin-left: auto; }
.panelbody { flex: 1; overflow: auto; padding: 12px 14px; }
.formrow { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: end; margin-bottom: 10px; }
.formrow label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--muted); }
.comingnext { padding: 40px 10px; text-align: center; }

.chartpane { display: flex; flex-direction: column; gap: 8px; }
.chart { margin: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.charthead { display: flex; gap: 4px; align-items: center; padding: 6px 10px; flex-wrap: wrap; }
.charthead .tools { margin-left: auto; display: flex; gap: 4px; }
.chartcanvas { display: block; width: 100%; cursor: crosshair; touch-action: none; }
.readout { padding: 5px 10px; font-size: 12px; font-variant-numeric: tabular-nums; border-top: 1px solid var(--line); }
.replaybar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.replaybar input[type=range] { flex: 1; min-width: 160px; padding: 0; }
.replaybar label { display: flex; gap: 6px; align-items: center; font-size: 12px; color: var(--muted); }

.optpicker { margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.ladder { border-collapse: collapse; font-variant-numeric: tabular-nums; max-height: 260px; display: block; overflow: auto; }
.ladder th, .ladder td { padding: 2px 14px; text-align: center; }
.ladder tr.atm td { background: rgba(108, 200, 255, .15); color: #fff; }
.ladder button { padding: 1px 10px; }
.ladder button.picked { background: #1a4a8a; border-color: var(--accent); }

@media (max-width: 700px) {
  .computerpanel { inset: 0; border-radius: 0; }
  .hud h1 { font-size: 13px; }
}
```

- [ ] **Step 4: Run tests and type check** — `npx vitest run && npx tsc --noEmit`, expect PASS.
- [ ] **Step 5: Visual check** — `npm run mock` (port 8020) and `npm run dev`; open http://localhost:5175 in the
  browser pane. Check at desktop and 375x812: room matches the reference, labels readable, hover glows a
  computer, click flies the camera and opens the panel, Esc flies back, Backtests ETFs SPY loads mock bars,
  Play replays, Options ladder loads and a contract click loads two charts. Screenshot each.
- [ ] **Step 6: Commit** — `feat(web3d): 3D CEO room with clickable computers and camera flight`

---

### Task 7: Launcher, README, real-data check

**Files:** Create `engine/run.sh`, `web3d/scripts/launch.sh`, `web3d/scripts/stop.sh`, `web3d/public/backtest-ceo.svg`,
`backtest-ceo.desktop`, `README.md`.

<!-- file: engine/run.sh -->
```bash
#!/usr/bin/env bash
# Starts the engine on 8020. Alpaca keys come from ~/backtest-ceo/.env, else the ALPACA_ lines of ~/scalp-city/.env.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
for f in "$DIR/../.env" "$HOME/scalp-city/.env"; do
  if [ -f "$f" ]; then
    set -a; eval "$(grep -E '^ALPACA_(API_KEY|SECRET_KEY)=' "$f")"; set +a
    break
  fi
done
cd "$DIR" && exec .venv/bin/uvicorn backtestceo.server:app --host 127.0.0.1 --port "${BACKTEST_CEO_ENGINE_PORT:-8020}"
```

<!-- file: web3d/scripts/launch.sh -->
```bash
#!/usr/bin/env bash
# Dock launcher: starts the engine (8020) and the view (5175) if they are down, then opens Firefox.
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VIEW="${BACKTEST_CEO_VIEW_PORT:-5175}"
ENGINE="${BACKTEST_CEO_ENGINE_PORT:-8020}"
LOGDIR="${XDG_CACHE_HOME:-$HOME/.cache}"
up() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
mkdir -p "$LOGDIR"
if ! up "$ENGINE"; then
  nohup "$ROOT/engine/run.sh" >"$LOGDIR/backtest-ceo-engine.log" 2>&1 &
fi
if ! up "$VIEW"; then
  (cd "$DIR" && VITE_ENGINE_URL="http://127.0.0.1:$ENGINE" nohup npx vite --port "$VIEW" --strictPort >"$LOGDIR/backtest-ceo-view.log" 2>&1 &)
fi
for _ in $(seq 1 40); do up "$VIEW" && break; sleep 0.5; done
exec firefox --new-window "http://localhost:$VIEW/"
```

<!-- file: web3d/scripts/stop.sh -->
```bash
#!/usr/bin/env bash
# Stops the view (5175) and the engine (8020).
for PORT in "${BACKTEST_CEO_VIEW_PORT:-5175}" "${BACKTEST_CEO_ENGINE_PORT:-8020}"; do
  pids=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u)
  [ -n "$pids" ] && kill $pids
done
exit 0
```

<!-- file: web3d/public/backtest-ceo.svg -->
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#050a18"/>
  <ellipse cx="32" cy="50" rx="22" ry="6" fill="none" stroke="#6cc8ff" stroke-width="2.5"/>
  <circle cx="32" cy="17" r="6" fill="#6cc8ff"/>
  <path d="M22 46 L24 28 Q32 23 40 28 L42 46 Z" fill="#6cc8ff" opacity=".85"/>
  <polyline points="8,40 14,34 19,37 25,29" fill="none" stroke="#a98bff" stroke-width="2"/>
  <polyline points="39,29 45,33 50,27 56,31" fill="none" stroke="#a98bff" stroke-width="2"/>
</svg>
```

<!-- file: backtest-ceo.desktop -->
```ini
[Desktop Entry]
Type=Application
Name=Backtest CEO
Comment=Visual backtesting room: CEO, agents, backtest charts
Exec=/home/ronaldsecret/backtest-ceo/web3d/scripts/launch.sh
Icon=backtest-ceo
Terminal=false
Categories=Office;Finance;
Actions=Stop;

[Desktop Action Stop]
Name=Stop Backtest CEO
Exec=/home/ronaldsecret/backtest-ceo/web3d/scripts/stop.sh
```

<!-- file: README.md -->
```markdown
# Backtest CEO

Visual backtesting system. A CEO AI hologram stands on a strategy table with six agents around it; the
computers behind it open the Backtests, Scanner and Strategies views. Read-only: nothing here places orders.

Asset classes: Stocks, ETFs, Crypto, Options (all data from Alpaca; options history starts 2024-02-01 and is
bars only, so options fills priced from bars are optimistic). No futures.

## Run

    engine/run.sh                    # engine on 127.0.0.1:8020 (keys from .env, else ~/scalp-city/.env)
    cd web3d && npm run dev          # view on http://localhost:5175
    cd web3d && npm run mock         # fake engine on 8020 for work without keys

Or use the dock launcher (Backtest CEO). Add `?fx=high` to the URL for bloom.

## Test

    cd engine && .venv/bin/pytest -q
    cd web3d && npx vitest run && npx tsc --noEmit

## Layout

- `engine/backtestceo`: Alpaca client (bars, options expirations and chains, disk cache in
  `~/.cache/backtest-ceo`), FastAPI server under `/api`.
- `web3d/src/scene`: the 3D room. `config/seats.ts` and `config/computers.ts` hold the agents and computers.
- `web3d/src/panels`: computer panel, backtest tab, options picker, canvas chart, replay bar.
- `web3d/src/model`: pure logic with unit tests. `model/indicators.ts` is the (empty) indicator registry.
- Specs and plans: `docs/superpowers/`.
```

- [ ] **Step 1: Install launcher**

```bash
chmod +x ~/backtest-ceo/engine/run.sh ~/backtest-ceo/web3d/scripts/*.sh
cp ~/backtest-ceo/backtest-ceo.desktop ~/.local/share/applications/
mkdir -p ~/.local/share/icons/hicolor/scalable/apps && cp ~/backtest-ceo/web3d/public/backtest-ceo.svg ~/.local/share/icons/hicolor/scalable/apps/
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

- [ ] **Step 2: Real-data check** — stop the mock, run `engine/run.sh`, `curl -s localhost:8020/api/health`
  (expect `alpaca_keys_present: true`), then in the app: Backtests → ETFs → SPY 5Min last session → Load → Play.
  Options → SPY, a day after 2024-02-01, pick an ATM call → two charts load.
- [ ] **Step 3: Commit** — `feat: dock launcher, engine run script, README`
