"""Download one bounded session of real options NBBO from local Theta Terminal v3.

No orders, subscriptions, or synthetic quote fallback. Original CSV is retained.
"""
import argparse
import csv
import gzip
import io
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import requests

FIELDS = {'timestamp', 'bid', 'ask', 'bid_size', 'ask_size'}


def inspect_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    if not FIELDS.issubset(reader.fieldnames or []):
        raise ValueError('Theta response is not quote CSV: required bid/ask/time/size fields missing.')
    count = invalid = 0
    for row in reader:
        count += 1
        try:
            values = [float(row[k]) for k in ('bid', 'ask', 'bid_size', 'ask_size')]
            bid, ask, bs, az = values
            stamp = datetime.fromisoformat(row['timestamp'])
            valid = all(math.isfinite(v) for v in values) and 0 < bid <= ask and bs > 0 and az > 0
        except (ValueError, TypeError):
            valid = False
        invalid += not valid
    if count == 0:
        raise ValueError('No historical quotes returned; no successful archive was written.')
    return {'rows': count, 'invalid_or_non_executable_rows': invalid}


def download(out, symbol, expiration, day, interval='tick', strike=None, right='both', session=None):
    """Preserve source NBBO; invalid/zero/crossed rows remain in raw archive and are counted."""
    symbol = symbol.upper()
    if not symbol.isalpha():
        raise ValueError('Use an alphabetic underlying symbol, e.g. SPY.')
    date.fromisoformat(day)
    date.fromisoformat(expiration)
    if right not in ('call', 'put', 'both') or interval not in ('tick', '1s', '1m'):
        raise ValueError('Invalid right or interval.')
    params = dict(symbol=symbol, expiration=expiration, date=day, interval=interval, right=right, format='csv')
    if strike is not None:
        if not math.isfinite(float(strike)) or float(strike) <= 0:
            raise ValueError('Strike must be finite and positive.')
        params['strike'] = str(strike)
    dest = Path(out) / 'options' / 'quotes' / 'thetadata' / symbol / expiration
    stem = f'{day}-{interval}-{right}-{strike if strike is not None else "all"}'
    path = dest / (stem + '.csv.gz')
    manifest = dest / (stem + '.json')
    if path.exists() and manifest.exists():
        return json.loads(manifest.read_text())
    try:
        r = (session or requests.Session()).get('http://127.0.0.1:25503/v3/option/history/quote',
                                                 params=params, timeout=(10, 300))
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError('Historical quotes unavailable. Start Theta Terminal v3 with an entitled account; '
                           'no bars or indicative snapshots were substituted.') from e
    stats = inspect_csv(r.text)
    info = dict(provider='thetadata', data_type='historical_nbbo', parameters=params,
                source_timezone='America/New_York (Theta v3 timestamp convention)',
                collected_at=datetime.now(timezone.utc).isoformat(), path=str(path), **stats)
    dest.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.gz.tmp')
    tmp.write_bytes(gzip.compress(r.text.encode()))
    tmp.replace(path)
    tmp_manifest = manifest.with_suffix('.json.tmp')
    tmp_manifest.write_text(json.dumps(info, indent=2) + '\n')
    tmp_manifest.replace(manifest)
    return info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbol', required=True)
    p.add_argument('--expiration', required=True, help='YYYY-MM-DD; one expiration per run')
    p.add_argument('--date', required=True, help='YYYY-MM-DD; one session per run')
    p.add_argument('--strike', type=float, help='Omit to fetch the full expiration')
    p.add_argument('--right', choices=['call', 'put', 'both'], default='both')
    p.add_argument('--interval', choices=['tick', '1s', '1m'], default='tick')
    p.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[2] / 'data')
    args = p.parse_args()
    try:
        info = download(args.out, args.symbol, args.expiration, args.date, args.interval, args.strike, args.right)
    except (ValueError, RuntimeError) as e:
        p.exit(1, str(e) + '\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
