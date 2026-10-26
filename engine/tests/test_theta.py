import gzip
import pytest
import requests
from backtestceo.theta import download, inspect_csv

CSV = 'timestamp,bid,ask,bid_size,ask_size\n2026-10-23T10:00:00.123,1.0,1.2,2,3\n'

class Session:
    def __init__(self, text=CSV):
        self.text, self.calls = text, []
    def get(self, url, **kw):
        self.calls.append((url, kw))
        response = requests.Response()
        response.status_code = 200
        response._content = self.text.encode()
        return response


def test_preserves_real_quote_fields_and_feed_provenance(tmp_path):
    s = Session()
    info = download(tmp_path, 'SPY', '2026-10-23', '2026-10-23', strike=600, session=s)
    assert info['data_type'] == 'historical_nbbo' and info['rows'] == 1
    assert info['invalid_or_non_executable_rows'] == 0
    from pathlib import Path
    assert gzip.decompress(Path(info['path']).read_bytes()).decode() == CSV
    assert s.calls[0][1]['params']['interval'] == 'tick'
    assert s.calls[0][1]['params']['format'] == 'csv'
    download(tmp_path, 'SPY', '2026-10-23', '2026-10-23', strike=600, session=s)
    assert len(s.calls) == 1


def test_refuses_bar_or_empty_response(tmp_path):
    for text in ['t,o,h,l,c\n1,1,1,1,1\n', CSV.splitlines()[0] + '\n']:
        with pytest.raises(ValueError):
            download(tmp_path, 'SPY', '2026-10-23', '2026-10-23', session=Session(text))
    assert not list(tmp_path.rglob('*.csv.gz'))


def test_counts_unusable_markets_instead_of_presenting_as_executable():
    bad = ('2026-10-23T10:00:01,2,1,1,1\n'
           '2026-10-23T10:00:02,0,1,0,1\n'
           '2026-10-23T10:00:03,nan,1,1,1\n')
    assert inspect_csv(CSV + bad) == {'rows': 4, 'invalid_or_non_executable_rows': 3}


def test_unavailable_terminal_does_not_fall_back(tmp_path):
    class Offline:
        def get(self, *a, **kw):
            raise requests.ConnectionError()
    with pytest.raises(RuntimeError, match='no bars'):
        download(tmp_path, 'SPY', '2026-10-23', '2026-10-23', session=Offline())
    assert not list(tmp_path.rglob('*.csv.gz'))
