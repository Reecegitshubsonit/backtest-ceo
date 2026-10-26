"""Free date-level options snapshots. These are NOT intraday NBBO or guaranteed fills."""
import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from .collect import write_csv

URL = 'https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master'
SOURCE = 'https://www.dolthub.com/repositories/post-no-preference/options'
FIELDS = ['date', 'act_symbol', 'expiration', 'strike', 'call_put', 'bid', 'ask',
          'vol', 'delta', 'gamma', 'theta', 'vega', 'rho']


def query(sql, session):
    r = session.get(URL, params={'q': sql}, timeout=90)
    r.raise_for_status()
    data = r.json()
    if data.get('query_execution_status') != 'Success':
        raise ValueError('Public options query failed: ' + str(data.get('query_execution_message')))
    if data.get('next_page_token') or data.get('nextPageToken'):
        raise ValueError('Unexpected paginated result; refusing an incomplete archive.')
    return data['rows']


def download(out, symbol, day, session=None):
    symbol = symbol.upper()
    if not re.fullmatch(r'[A-Z]{1,10}', symbol):
        raise ValueError('Invalid underlying symbol.')
    day = date.fromisoformat(day).isoformat()
    folder = Path(out) / 'options' / 'daily_quotes' / 'dolthub' / symbol
    archive, manifest = folder / f'{day}.csv.gz', folder / f'{day}.json'
    if archive.exists() and manifest.exists():
        info = json.loads(manifest.read_text())
        if info.get('sha256') == hashlib.sha256(archive.read_bytes()).hexdigest():
            return info
    http = session or requests.Session()
    rows = query("SELECT * FROM option_chain WHERE act_symbol='" + symbol + "' AND date='" + day +
                 "' ORDER BY expiration,strike,call_put LIMIT 10000", http)
    if len(rows) >= 10000:
        raise ValueError('Result reached safety limit; refusing possible truncation.')
    if not rows:
        return {'symbol': symbol, 'date': day, 'rows': 0, 'status': 'no_source_data'}
    for r in rows:
        if r.get('date') != day or r.get('act_symbol') != symbol or not set(FIELDS).issubset(r):
            raise ValueError('Unexpected source schema or mismatched date/symbol.')
    # Preserve upstream provenance/license before saving a usable archive.
    docs = query('SELECT * FROM dolt_docs', http)
    folder.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        if doc.get('doc_name') in ('README.md', 'LICENSE.md'):
            (folder.parent / ('SOURCE-' + doc['doc_name'])).write_text(doc['doc_text'])
    write_csv(archive, FIELDS, rows)
    info = dict(source=SOURCE, symbol=symbol, date=day, rows=len(rows), data_type='date_level_option_snapshot',
                quote_timestamp_available=False, displayed_size_available=False, intraday_execution_eligible=False,
                available_for_simulation='following_session_only; exact observation time unverified',
                limitations=['Filtered/possibly incomplete chain', 'Snapshot timing and NBBO provenance unverified',
                             'No volume or open interest in this table', 'Missing dates must not be forward-filled as fresh quotes'],
                sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                collected_at=datetime.now(timezone.utc).isoformat(), path=str(archive))
    tmp = manifest.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(info, indent=2) + '\n')
    tmp.replace(manifest)
    return info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbol', required=True)
    p.add_argument('--date', required=True)
    p.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[2] / 'data')
    a = p.parse_args()
    print(json.dumps(download(a.out, a.symbol, a.date), indent=2))


if __name__ == '__main__':
    main()
