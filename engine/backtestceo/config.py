import os
from pathlib import Path

ENGINE_PORT = int(os.environ.get("BACKTEST_CEO_ENGINE_PORT", "8020"))
CACHE_DIR = Path(os.environ.get("BACKTEST_CEO_CACHE", str(Path.home() / ".cache" / "backtest-ceo")))
