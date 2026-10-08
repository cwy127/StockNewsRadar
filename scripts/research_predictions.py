"""Prospective, append-only research forecasts using existing Yahoo daily bars."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .validation_quality import price_errors
else:
    from validation_quality import price_errors

ROOT = Path('data/predictions')
MODEL = 'momentum-5-session-deadband-1pct-v1'
HORIZONS = (1, 5, 20)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def save_new(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never replace a previously published issuance or observation.
    with path.open('x', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def schedule(market, now):
    import exchange_calendars as xcals
    code = 'XKRX' if market == 'KR' else 'XNYS'
    calendar = xcals.get_calendar(code, start=(now-timedelta(days=60)).date().isoformat(),
                                 end=(now+timedelta(days=90)).date().isoformat())
    table = calendar.schedule
    past = table[table['close'] < now].tail(6)
    future = table[table['open'] > now].head(20)
    if len(past) != 6 or len(future) != 20:
        raise ValueError('calendar_coverage_missing')
    sessions = [{'session':str(idx.date()),'open':row['open'].isoformat(), 'close':row['close'].isoformat()}
                for idx,row in future.iterrows()]
    return {'name':code,'package':'exchange_calendars','version':version('exchange_calendars'),
            'past_sessions':[str(idx.date()) for idx in past.index], 'future_sessions':sessions}


def fetch_bars(ticker, start, end):
    import yfinance as yf
    frame = yf.download(ticker,start=start,end=end,auto_adjust=False,actions=True,
                        progress=False,threads=False,timeout=20)
    if frame is None or frame.empty:
        return []
    if getattr(frame.columns,'nlevels',1)>1:
        frame.columns=frame.columns.get_level_values(0)
    bars=[]
    for idx,row in frame.iterrows():
        bar={'session':str(idx.date())}
        for src,dst in [('Open','next_open'),('High','next_high'),('Low','next_low'),('Close','next_close'),('Stock Splits','splits')]:
            value=float(row[src]) if src in row else 0.0 if src=='Stock Splits' else None
            import math
            bar[dst]=value if value is None or math.isfinite(value) else None
        bars.append(bar)
    return bars


def model_input(bars, expected_sessions):
    selected=[b for b in bars if b['session'] in expected_sessions]
    if [b['session'] for b in selected] != expected_sessions:
        return None, None, ['missing_or_duplicate_input_sessions']
    reasons=[]
    for bar in selected:
        reasons += price_errors(dict(bar,baseline_close=bar.get('next_close')))
        if bar.get('splits') not in (None,0):reasons.append('corporate_action_in_input')
    if reasons:return None,None,sorted(set(reasons))
    change=(selected[-1]['next_close']/selected[0]['next_close']-1)*100
    direction='up' if change>=1 else 'down' if change<=-1 else None
    return direction, selected[-1]['next_close'], [] if direction else ['within_1pct_deadband']


def issue(market, now=None, fetch=fetch_bars):
    realtime = now is None
    now=now or datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo('Asia/Seoul' if market=='KR' else 'America/New_York')).date().isoformat()
    path=ROOT/'issued'/market/(day+'.json')
    if path.exists():return {'status':'already_recorded','path':str(path)}
    folder='top' if market=='KR' else 'top_us'
    source=Path('data/history')/folder/(day+'.json')
    if not source.exists():raise ValueError('current_day_snapshot_missing; historical snapshots are never backfilled')
    raw=source.read_bytes();snap=json.loads(raw)
    calendar=schedule(market,now)
    snapshot_time=datetime.fromisoformat(snap['snapshot_at'])
    fresh=timedelta(0)<=now-snapshot_time<=timedelta(hours=2)
    predictions=[]
    for item in snap['candidates']:
        symbol=str(item['symbol'])
        ticker=symbol if market=='US' else symbol+('.KS' if item.get('market')=='KOSPI' else '.KQ')
        bars=[];reasons=[];direction=None;baseline=None
        try:
            if not fresh:raise ValueError('stale_or_future_snapshot')
            bars=fetch(ticker,calendar['past_sessions'][0],(now.date()+timedelta(days=1)).isoformat())
            direction,baseline,reasons=model_input(bars,calendar['past_sessions'])
        except Exception as exc:
            reasons=['input_unavailable:'+type(exc).__name__+':'+str(exc)[:200]]
        # Publish only after fetching, so the issue timestamp is never earlier than its inputs.
        issued=datetime.now(timezone.utc) if realtime else now
        future=calendar['future_sessions']
        if datetime.fromisoformat(future[0]['open'])<=issued:
            direction=None;reasons.append('session_started_during_input_fetch')
        inputs={'candidate':item,'bars':[b for b in bars if b['session'] in calendar['past_sessions']],
                'snapshot_metadata':{k:v for k,v in snap.items() if k!='candidates'}}
        for horizon in HORIZONS:
            due=future[horizon-1]
            predictions.append({'id':f'{market}-{day}-{symbol}-{horizon}', 'symbol':symbol,'market':market,
                'issued_at':issued.isoformat(),'recorded_at':issued.isoformat(),
                'evaluation_at':due['close'],'evaluation_session':due['session'],
                'horizon':f'{horizon}_trading_sessions','type':'direction','target':direction,
                'baseline_close':baseline,'baseline_session':calendar['past_sessions'][-1],
                'rule_version':MODEL,'issuance_status':'issued' if direction else 'abstained',
                'issuance_reasons':reasons,'rationale':'Five completed-session raw close momentum: >=+1% up, <=-1% down; otherwise abstain. Research baseline, not a validated predictive model.',
                'input_data':inputs,'input_sha256':digest(inputs),'snapshot_source':str(source),
                'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'calendar':calendar,
                'price_provider':'Yahoo Finance via yfinance','ticker':ticker,
                'price_adjustment':'raw; split events make evaluation unavailable; no dividend total return'})
    save_new(path,{'version':'prospective-research-v1','created_at':now.isoformat(),'predictions':predictions})
    return {'status':'recorded','path':str(path),'count':len(predictions),
            'issued':sum(p['issuance_status']=='issued' for p in predictions)}


def collect_outcomes(now=None, fetch=fetch_bars):
    now=now or datetime.now(timezone.utc);written=0
    for path in sorted((ROOT/'issued').glob('*/*.json')):
        for prediction in json.loads(path.read_text())['predictions']:
            if prediction['issuance_status']!='issued':continue
            due=datetime.fromisoformat(prediction['evaluation_at'])
            if now<due+timedelta(hours=1):continue
            folder=ROOT/'observations'/prediction['id']
            old=[json.loads(p.read_text()) for p in sorted(folder.glob('*.json'))]
            if any(o['observation_status']=='evaluated' for o in old):continue
            target=folder/(now.date().isoformat()+'.json')
            if target.exists():continue
            observation={'prediction_id':prediction['id'],'symbol':prediction['symbol'],'market':prediction['market'],
                'evaluation_at':prediction['evaluation_at'],'observed_at':now.isoformat(),
                'source':'Yahoo Finance via yfinance; raw daily OHLC', 'observation_status':'missing_outcome'}
            try:
                bars=fetch(prediction['ticker'],prediction['baseline_session'],
                    (datetime.fromisoformat(prediction['evaluation_session'])+timedelta(days=1)).date().isoformat())
                observation['raw_bars']=bars;observation['input_sha256']=digest(bars)
                selected=[b for b in bars if b['session']==prediction['evaluation_session']]
                if any(b.get('splits') not in (None,0) for b in bars):
                    observation.update(observation_status='unevaluable',reasons=['corporate_action_in_evaluation_window'])
                elif len(selected)==1:
                    observation.update(selected[0])
                    errors=price_errors(dict(observation,baseline_close=prediction['baseline_close']))
                    observation.update(observation_status='invalid_price' if errors else 'evaluated',reasons=errors)
            except Exception as exc:
                observation['reasons']=['fetch_failed:'+type(exc).__name__+':'+str(exc)[:200]]
            save_new(target,observation);written+=1
    return written


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['issue','evaluate']);parser.add_argument('--market',choices=['KR','US'])
    args=parser.parse_args()
    if args.operation=='issue':
        if not args.market:parser.error('--market required')
        print(json.dumps(issue(args.market)))
    else:print(json.dumps({'observations_written':collect_outcomes()}))


if __name__=='__main__':main()
