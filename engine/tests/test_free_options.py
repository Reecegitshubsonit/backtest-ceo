import json
import requests
import pytest
from backtestceo.free_options import FIELDS, download

class Fake:
    def __init__(self, rows):
        self.rows, self.calls = rows, 0
    def get(self, url, params, **kw):
        self.calls += 1
        rows = [] if 'dolt_docs' in params['q'] else self.rows
        r = requests.Response()
        r.status_code = 200
        r._content = json.dumps({'query_execution_status': 'Success', 'rows': rows}).encode()
        return r


def test_marks_date_only_quotes_ineligible_for_intraday_and_resumes(tmp_path):
    row = dict.fromkeys(FIELDS, '0')
    row.update(date='2026-10-23', act_symbol='SPY')
    s = Fake([row])
    info = download(tmp_path, 'SPY', '2026-10-23', s)
    assert not info['intraday_execution_eligible']
    assert not info['quote_timestamp_available']
    assert info['rows'] == 1
    assert download(tmp_path, 'SPY', '2026-10-23', s) == info
    assert s.calls == 2


def test_no_data_does_not_become_completed_archive(tmp_path):
    assert download(tmp_path, 'SPY', '2026-10-23', Fake([]))['status'] == 'no_source_data'
    assert not list(tmp_path.rglob('*.csv.gz'))


def test_rejects_sql_injection_and_mismatched_data(tmp_path):
    with pytest.raises(ValueError):
        download(tmp_path, "SPY';DROP", '2026-10-23', Fake([]))
    with pytest.raises(ValueError):
        download(tmp_path, 'SPY', '2026-10-23', Fake([{'date': '2026-10-22'}]))
