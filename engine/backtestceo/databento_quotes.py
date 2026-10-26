"""Budget-capped historical CBBO-1s downloads; no subscriptions or order API."""
import csv,gzip,json,re,hashlib,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import requests
from .cross_backtest import NY
from .options_backtest import CACHE,OUT
DEST=OUT/'databento-quotes'


def api_key():
    import os
    raw=os.environ.get('DATABENTO_API_KEY','')
    if not raw:
        for path in (Path.home()/'backtest-ceo/.env',Path.home()/'scalp-city/.env'):
            if path.exists():
                raw=next((l.partition('=')[2] for l in path.read_text().splitlines() if l.startswith('DATABENTO_API_KEY=')),'')
                if raw:break
    token=raw.strip().strip('\"\'').split()[0] if raw.strip() else ''
    if not re.fullmatch(r'db-[A-Za-z0-9]{29}',token):raise ValueError('No valid Databento key token configured.')
    return token


def occ(symbol):return symbol[:-15].ljust(6)+symbol[-15:]


def jobs():
    days={}
    for p in (CACHE/'options').glob('*/*.json'):
        day=p.stem
        days.setdefault(day,set()).update(json.loads(p.read_text()))
    return [dict(day=d,symbols=sorted(symbols)) for d,symbols in sorted(days.items())]


def params(job):
    start=datetime.fromisoformat(job['day']).replace(hour=9,minute=30,tzinfo=NY).astimezone(timezone.utc)
    return dict(dataset='OPRA.PILLAR',schema='cbbo-1s',symbols=','.join(occ(s) for s in job['symbols']),
                stype_in='raw_symbol',start=start.isoformat(),end=(start+timedelta(hours=6,minutes=30)).isoformat())


def cache_valid(job,dest):
    path=dest/(job['day']+'.csv.gz');manifest=path.with_suffix('.json')
    if not path.exists() or not manifest.exists():return False
    info=json.loads(manifest.read_text())
    present=set(info['parameters']['symbols'].split(','))
    return (info['parameters']['schema']=='cbbo-1s' and set(occ(s) for s in job['symbols']).issubset(present)
            and hashlib.sha256(path.read_bytes()).hexdigest()==info['sha256'])


def estimate(job,key,dest=None):
    path=(dest or DEST)/(job['day']+'.csv.gz')
    if cache_valid(job,dest or DEST):return dict(**job,cost=0,cached=True)
    r=requests.get('https://hist.databento.com/v0/metadata.get_cost',auth=(key,''),params=params(job),timeout=90)
    if not r.ok:raise RuntimeError(f'Databento cost HTTP {r.status_code}; response omitted to protect credentials.')
    return dict(**job,cost=float(r.json()),cached=False)


def fetch(job,key,dest=None):
    path=(dest or DEST)/(job['day']+'.csv.gz')
    if job['cached']:return
    p=params(job);p.update(encoding='csv',compression='zstd',pretty_px='true',pretty_ts='true',map_symbols='true')
    r=requests.post('https://hist.databento.com/v0/timeseries.get_range',auth=(key,''),data=p,timeout=(15,300))
    if not r.ok:raise RuntimeError(f'Databento quotes HTTP {r.status_code}; no substitute fills.')
    content=r.content
    text=subprocess.run(['zstd','-dc'],input=content,stdout=subprocess.PIPE,check=True).stdout.decode()
    required={'ts_recv','bid_px_00','ask_px_00','bid_sz_00','ask_sz_00','symbol'}
    if not required.issubset(next(csv.reader(text.splitlines()))):raise ValueError('Not Databento quote CSV.')
    raw=gzip.compress(text.encode());tmp=path.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(path)
    manifest=dict(parameters=params(job),estimate_usd=job['cost'],sha256=hashlib.sha256(raw).hexdigest(),
                  rows=max(0,len(text.splitlines())-1),source='Databento OPRA CBBO-1s',availability_timestamp='ts_recv',
                  limitation='one-second sampled NBBO; no queue or actual order fill evidence')
    path.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Downloaded real quotes',job['day'],manifest['rows'],flush=True)


def download_jobs(selected_jobs,dest,estimate_cap=5):
    dest.mkdir(parents=True,exist_ok=True);key=api_key()
    previous_path=dest/'cost-plan.json'
    previous={j['day']:j for j in json.loads(previous_path.read_text())['jobs']} if previous_path.exists() else {}
    def plan_job(j):
        if cache_valid(j,dest):return dict(**j,cost=0,cached=True)
        old=previous.get(j['day'])
        if old and old['symbols']==j['symbols'] and old['cost']>0:return dict(**j,cost=old['cost'],cached=False)
        return estimate(j,key,dest)
    with ThreadPoolExecutor(max_workers=4) as pool:plan=list(pool.map(plan_job,selected_jobs))
    total=sum(j['cost'] for j in plan)
    (dest/'cost-plan.json').write_text(json.dumps(dict(estimated_new_download_usd=total,hard_estimate_cap_usd=estimate_cap,jobs=plan),indent=2)+'\n')
    print('Databento download estimate USD',round(total,6),'sessions',len(plan),flush=True)
    # Refuse new downloads above $5, leaving broad room under the user's $100/month budget.
    if total>estimate_cap:raise RuntimeError('Selected quote download estimate exceeds run cap; no download started.')
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda j:fetch(j,key,dest),plan))

def main():
    download_jobs(jobs(),DEST)

if __name__=='__main__':main()
