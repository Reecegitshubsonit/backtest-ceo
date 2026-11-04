"""NWS climate-report (CLI) stations used by Kalshi temperature markets.

Kalshi rules name the station as e.g. "New York City (CLINYC)"; the code after CLI keys this table.
Coordinates are the official ASOS sites. std_utc is the station's *standard* time offset: the NWS climate
day runs midnight to midnight local standard time all year, so during daylight time it is 1am to 1am.
"""
from __future__ import annotations

import re

# code: (ICAO, lat, lon, standard-time UTC offset, name)
STATIONS = {
    "NYC": ("KNYC", 40.7789, -73.9692, -5, "New York Central Park"),
    "MDW": ("KMDW", 41.7861, -87.7524, -6, "Chicago Midway"),
    "ORD": ("KORD", 41.9602, -87.9316, -6, "Chicago O'Hare"),
    "MIA": ("KMIA", 25.7881, -80.3169, -5, "Miami"),
    "AUS": ("KAUS", 30.1831, -97.6799, -6, "Austin Bergstrom"),
    "DEN": ("KDEN", 39.8466, -104.6562, -7, "Denver"),
    "LAX": ("KLAX", 33.9382, -118.3866, -8, "Los Angeles"),
    "PHL": ("KPHL", 39.8733, -75.2268, -5, "Philadelphia"),
    "HOU": ("KHOU", 29.6375, -95.2824, -6, "Houston Hobby"),
    "IAH": ("KIAH", 29.9844, -95.3608, -6, "Houston Intercontinental"),
    "BOS": ("KBOS", 42.3606, -71.0097, -5, "Boston"),
    "DCA": ("KDCA", 38.8483, -77.0342, -5, "Washington National"),
    "SEA": ("KSEA", 47.4447, -122.3144, -8, "Seattle"),
    "SFO": ("KSFO", 37.6197, -122.3647, -8, "San Francisco"),
    "PHX": ("KPHX", 33.4278, -112.0037, -7, "Phoenix"),
    "LAS": ("KLAS", 36.0719, -115.1634, -8, "Las Vegas"),
    "ATL": ("KATL", 33.6301, -84.4418, -5, "Atlanta"),
    "DFW": ("KDFW", 32.8974, -97.0220, -6, "Dallas Fort Worth"),
    "DAL": ("KDAL", 32.8471, -96.8518, -6, "Dallas Love Field"),
    "MSP": ("KMSP", 44.8831, -93.2289, -6, "Minneapolis"),
    "OKC": ("KOKC", 35.3889, -97.6006, -6, "Oklahoma City"),
    "SAT": ("KSAT", 29.5443, -98.4839, -6, "San Antonio"),
    "MSY": ("KMSY", 29.9934, -90.2580, -6, "New Orleans"),
    "EWR": ("KEWR", 40.6925, -74.1687, -5, "Newark"),
}

DEFAULT_SERIES = [
    # daily highs
    "KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS", "KXHIGHDEN", "KXHIGHLAX", "KXHIGHPHIL", "KXHIGHTHOU",
    "KXHIGHTBOS", "KXHIGHTDC", "KXHIGHTSEA", "KXHIGHTSFO", "KXHIGHTPHX", "KXHIGHTLV", "KXHIGHTATL",
    "KXHIGHTDAL", "KXHIGHTMIN", "KXHIGHTOKC", "KXHIGHTSATX", "KXHIGHTNOLA", "KXHIGHTEWR",
    # daily lows
    "KXLOWTNYC", "KXLOWTMIA", "KXLOWTAUS", "KXLOWTLAX", "KXLOWTBOS", "KXLOWTHOU", "KXLOWTMIN", "KXLOWTOKC",
    "KXLOWTEWR", "KXLOWTSATX",
]

_CODE = re.compile(r"\(CLI([A-Z]{3})\)")


def station_from_rules(rules: str) -> str | None:
    m = _CODE.search(rules or "")
    return m.group(1) if m and m.group(1) in STATIONS else None


def kind_from_rules(rules: str) -> str | None:
    r = (rules or "").lower()
    if "maximum temperature" in r or "highest temperature" in r:
        return "high"
    if "minimum temperature" in r or "lowest temperature" in r:
        return "low"
    return None
