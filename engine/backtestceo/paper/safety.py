"""Hard safety rails for the paper runner. Nothing here ever reads or prints a key value."""
import os
from pathlib import Path
from urllib.parse import urlparse

ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
WEBULL_SANDBOX_HOST = "api.sandbox.webull.com"
# Hosts that may receive orders. Anything else is refused before a request is built.
ORDER_HOSTS = frozenset({"paper-api.alpaca.markets", WEBULL_SANDBOX_HOST})
# Read-only market data (cannot place orders) and the local live-events feed.
DATA_HOSTS = frozenset({"data.alpaca.markets"})
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost"})
ALLOWED_HOSTS = ORDER_HOSTS | DATA_HOSTS | LOCAL_HOSTS
ALPACA_URL_VARS = ("ALPACA_BASE_URL", "APCA_API_BASE_URL", "ALPACA_PAPER_BASE_URL", "ALPACA_ENDPOINT")
WEBULL_URL_VARS = ("WEBULL_ENDPOINT", "WEBULL_API_ENDPOINT", "WEBULL_HOST")
TRUTHY = {"1", "true", "yes", "on", "y"}


class SafetyError(RuntimeError):
    pass


class KillSwitchEngaged(SafetyError):
    pass


def host_of(url: str) -> str:
    u = urlparse(url if "://" in url else "https://" + url)
    return (u.hostname or "").lower()


def assert_host(url: str, allowed=ALLOWED_HOSTS) -> str:
    h = host_of(url)
    if h not in allowed:
        raise SafetyError(f"host {h or '?'} is not on the paper/sandbox allowlist")
    if h not in LOCAL_HOSTS and not url.startswith("https://") and "://" in url:
        raise SafetyError(f"host {h} must be reached over https")
    return h


def check_env(env) -> list[tuple[str, bool, str]]:
    """Returns [(rule, ok, detail)]. Details describe the rule, never a secret value."""
    get = lambda k: (env.get(k) or "").strip()
    out = []
    out.append(("WEBULL_ENV=sandbox", get("WEBULL_ENV").lower() == "sandbox",
                "set" if get("WEBULL_ENV") else "missing"))
    out.append(("ALPACA_PAPER_TRADING_ONLY=true", get("ALPACA_PAPER_TRADING_ONLY").lower() == "true",
                "set" if get("ALPACA_PAPER_TRADING_ONLY") else "missing"))
    bad = [k for k in ALPACA_URL_VARS if get(k) and host_of(get(k)) != "paper-api.alpaca.markets"]
    out.append(("Alpaca base URL is paper-api.alpaca.markets", not bad,
                ("not the paper endpoint: " + ",".join(bad)) if bad else "paper (default or explicit)"))
    badw = [k for k in WEBULL_URL_VARS if get(k) and host_of(get(k)) != WEBULL_SANDBOX_HOST]
    out.append((f"Webull endpoint is {WEBULL_SANDBOX_HOST}", not badw,
                ("not the sandbox endpoint: " + ",".join(badw)) if badw else "sandbox (default or explicit)"))
    return out


def require_paper(env) -> None:
    failed = [f"{rule} ({detail})" for rule, ok, detail in check_env(env) if not ok]
    if failed:
        raise SafetyError("refusing to start: " + "; ".join(failed))


def kill_switch_on(env, kill_file: Path | None = None, env_file_reader=None) -> bool:
    """PAPER_TRADING_KILL_SWITCH in the process env, re-read from the .env file (so it can be flipped while
    running), or a KILL file in the state dir. Any one of them stops all orders."""
    vals = [env.get("PAPER_TRADING_KILL_SWITCH")]
    if env_file_reader:
        try:
            vals.append(env_file_reader().get("PAPER_TRADING_KILL_SWITCH"))
        except OSError:
            vals.append("1")  # cannot verify the switch: fail closed
    if any((v or "").strip().lower() in TRUTHY for v in vals):
        return True
    return bool(kill_file and kill_file.exists())
