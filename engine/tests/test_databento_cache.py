import hashlib,json
from backtestceo.databento_quotes import cache_valid,occ


def test_same_day_cache_cannot_substitute_different_expiry(tmp_path):
    path=tmp_path/'2026-07-23.csv.gz';path.write_bytes(b'archive')
    symbol='SPY260723C00600000'
    info=dict(parameters=dict(schema='cbbo-1s',symbols=occ(symbol)),sha256=hashlib.sha256(b'archive').hexdigest())
    path.with_suffix('.json').write_text(json.dumps(info))
    assert cache_valid(dict(day='2026-07-23',symbols=[symbol]),tmp_path)
    assert not cache_valid(dict(day='2026-07-23',symbols=['SPY260724C00600000']),tmp_path)
    path.write_bytes(b'corrupt')
    assert not cache_valid(dict(day='2026-07-23',symbols=[symbol]),tmp_path)
