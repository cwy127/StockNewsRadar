"""Audit explicit, contemporaneously recorded predictions; never infer them from ranks.

Optional input: data/predictions/ledger.json with predictions and outcomes arrays.
See evidence/prediction_contract.txt. Existing TOP snapshots remain exploratory.
"""
import hashlib
import json
import subprocess
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .validation_quality import finite_number, partition_records, price_errors
else:
    from validation_quality import finite_number, partition_records, price_errors

OUT = Path('data/analysis/prediction_validation.json')
LEDGER = Path('data/predictions/ledger.json')


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def verified_archive(prediction):
    """Require an existing Git archive containing the exact forecast before its due time.

    Commit metadata is provenance evidence, not a trusted external timestamp authority.
    """
    evidence = prediction.get('evidence')
    if not isinstance(evidence, dict):
        return False
    commit, source = evidence.get('git_commit', ''), evidence.get('source', '')
    if not re.fullmatch(r'[0-9a-f]{40}', commit) or not source or source.startswith('/') or '..' in Path(source).parts:
        return False
    try:
        raw = subprocess.check_output(['git','show',f'{commit}:{source}'], stderr=subprocess.DEVNULL)
        committed = timestamp(subprocess.check_output(['git','show','-s','--format=%cI',commit],text=True,stderr=subprocess.DEVNULL).strip())
        if hashlib.sha256(raw).hexdigest() != evidence.get('sha256'):
            return False
        if not committed or not timestamp(prediction['issued_at']).replace(microsecond=0) <= committed < timestamp(prediction['evaluation_at']):
            return False
        archived = json.loads(raw)
        expected = {k:v for k,v in prediction.items() if k != 'evidence'}
        return expected in archived['predictions']
    except (subprocess.CalledProcessError, KeyError, TypeError, ValueError, OSError):
        return False


def evaluate(prediction, outcomes, now):
    result = {'prediction': prediction, 'status': 'unevaluable', 'reasons': []}
    if prediction.get('issuance_status') == 'abstained':
        result['reasons'] = prediction.get('issuance_reasons') or ['model_abstained']
        return result
    required = ('id','symbol','market','issued_at','recorded_at','evaluation_at','horizon',
                'type','target','baseline_close','rule_version','evidence')
    reasons = [f'missing:{key}' for key in required if prediction.get(key) is None or prediction.get(key) == '']
    issued, recorded, due = (timestamp(prediction.get(k)) for k in ('issued_at','recorded_at','evaluation_at'))
    if not all((issued, recorded, due)):
        reasons.append('missing_timezone_or_invalid_time')
    elif not issued <= recorded < due:
        reasons.append('not_recorded_before_evaluation')
    kind, target = prediction.get('type'), prediction.get('target')
    if kind not in ('direction','price','return','probability_up'):
        reasons.append('unsupported_prediction_type')
    elif kind == 'direction' and target not in ('up','down','flat'):
        reasons.append('invalid_direction_target')
    elif kind != 'direction' and not finite_number(target):
        reasons.append('invalid_numeric_target')
    elif kind == 'price' and target <= 0:
        reasons.append('invalid_price_target')
    elif kind == 'probability_up' and not 0 <= target <= 1:
        reasons.append('invalid_probability')
    baseline = prediction.get('baseline_close')
    if not finite_number(baseline) or baseline <= 0:
        reasons.append('invalid_baseline')
    evidence = prediction.get('evidence')
    if not isinstance(evidence, dict) or not evidence.get('source') or not evidence.get('sha256'):
        reasons.append('missing_contemporaneous_source_reference')
    if not reasons and not verified_archive(prediction):
        reasons.append('unverified_contemporaneous_archive')
    if reasons:
        result['reasons'] = reasons
        return result
    if due > now:
        result['status'] = 'pending'
        return result
    matches = [o for o in outcomes if o.get('prediction_id') == prediction['id']]
    result['outcome_candidates'] = matches
    if not matches:
        result.update(status='missing_outcome', reasons=['no_outcome'])
        return result
    if len(matches) != 1:
        result['reasons'] = ['ambiguous_outcomes']
        return result
    outcome = matches[0]
    if (outcome.get('symbol') != prediction['symbol'] or outcome.get('market') != prediction['market']
            or timestamp(outcome.get('evaluation_at')) != due):
        result['reasons'] = ['outcome_identity_or_horizon_mismatch']
        return result
    if not outcome.get('source'):
        result['reasons'] = ['missing_outcome_source']
        return result
    if outcome.get('observation_status') in ('missing_outcome', 'unevaluable'):
        result.update(status=outcome['observation_status'], reasons=outcome.get('reasons') or ['outcome_unavailable'])
        return result
    errors = price_errors(dict(outcome, baseline_close=baseline))
    if errors:
        result.update(status='invalid_price', reasons=errors)
        return result
    actual_return = (outcome['next_close'] / baseline - 1) * 100
    actual_direction = 'up' if actual_return > 0 else 'down' if actual_return < 0 else 'flat'
    result.update(status='evaluated', actual_return_pct=actual_return, actual_direction=actual_direction)
    if kind == 'direction':
        result.update(hit=target == actual_direction, baseline_hit=actual_direction == 'up')
    elif kind in ('price','return'):
        actual = outcome['next_close'] if kind == 'price' else actual_return
        simple = baseline if kind == 'price' else 0
        result.update(error=target-actual, baseline_error=simple-actual)
    else:
        event = int(actual_return > 0)
        result.update(probability=target, event=event, brier=(target-event)**2, baseline_brier=(0.5-event)**2)
    return result


def metrics(rows, kind):
    valid = [r for r in rows if r['status'] == 'evaluated']
    n = len(valid)
    result = {'total_count':len(rows), 'status_counts':dict(Counter(r['status'] for r in rows)),
              'evaluated_count':n, 'sample_status':'표본 부족' if n < 30 else '분석 가능',
              'abstained_count':sum(r['prediction'].get('issuance_status') == 'abstained' for r in rows),
              'pending_count':sum(r['status'] == 'pending' for r in rows),
              'symbol_count':len({r['prediction'].get('symbol') for r in rows}),
              'issue_date_count':len({str(r['prediction'].get('issued_at', 'unknown'))[:10] for r in rows})}
    if not n:
        return result
    def mean(key): return sum(r[key] for r in valid)/n
    if kind == 'direction':
        result.update(hit_rate_pct=100*mean('hit'), always_up_hit_rate_pct=100*mean('baseline_hit'))
    elif kind in ('price','return'):
        result.update(mae=sum(abs(r['error']) for r in valid)/n, bias=mean('error'),
                      rmse=(sum(r['error']**2 for r in valid)/n)**0.5,
                      no_change_mae=sum(abs(r['baseline_error']) for r in valid)/n)
    else:
        bins=[]
        for i in range(10):
            bucket=[r for r in valid if min(int(r['probability']*10),9)==i]
            if bucket:
                bins.append({'lower':i/10,'upper':(i+1)/10,'count':len(bucket),
                             'mean_probability':sum(r['probability'] for r in bucket)/len(bucket),
                             'observed_frequency':sum(r['event'] for r in bucket)/len(bucket)})
        result.update(brier_score=mean('brier'), constant_half_brier_score=mean('baseline_brier'),calibration_bins=bins)
    return result


def analyze(predictions, outcomes, now):
    counts=Counter(p.get('id') for p in predictions)
    rows=[]
    for p in predictions:
        row=evaluate(p,outcomes,now)
        if counts[p.get('id')] > 1:
            row.update(status='unevaluable',reasons=['duplicate_prediction_id'])
        rows.append(row)
    groups=defaultdict(list)
    cumulative=defaultdict(list)
    for row in rows:
        p=row['prediction']
        key=tuple(str(p.get(k,'unknown')) for k in ('market','horizon','type','rule_version','symbol'))+(str(p.get('issued_at','unknown'))[:7],)
        groups[key].append(row)
        # Raw price errors cannot be pooled across differently priced instruments.
        pooled_key=key[:4]+(str(p.get('symbol','unknown')) if p.get('type') == 'price' else None,)
        cumulative[pooled_key].append(row)
    return {'total_count':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),
            'groups':[dict(zip(('market','horizon','type','rule_version','symbol','issue_month'),key),**metrics(group,key[2])) for key,group in sorted(groups.items())],
            'cumulative_groups':[dict(zip(('market','horizon','type','rule_version','price_symbol'),key),
                                      **metrics(group,key[2])) for key,group in sorted(cumulative.items())],
            'cumulative_definition':{
                'scope':'All issuance months and symbols within market, horizon, prediction type and rule version; raw price errors stay per symbol.',
                'sample_unit':'One evaluated prediction at its fixed horizon',
                'minimum_evaluated_for_sample_label':30,
                'abstained_count':'Subset of unevaluable, not an additional status or denominator',
                'limitation':'Overlapping horizons and correlated symbols are not independent samples. The sample label is descriptive, not evidence of statistical significance or predictive edge.'},
            'records':rows, 'outcomes':outcomes}


def inventory():
    rows=[]
    for market,folder,result_file in [('KR','top','results.json'),('US','top_us','results_us.json')]:
        results=json.loads((Path('data/validation')/result_file).read_text())['records']
        valid, excluded=partition_records(results)
        for path in sorted((Path('data/history')/folder).glob('*.json')):
            raw=path.read_bytes(); snap=json.loads(raw)
            for index,item in enumerate(snap.get('candidates',[])):
                key=(snap.get('signal_date'),item.get('symbol'),item.get('rank'))
                def matches(r):return (r.get('signal_date'),r.get('symbol'),r.get('rank'))==key
                actual=[r for r in results if matches(r)]
                bad=[r for r in excluded if matches(r['record'])]
                good=[r for r in valid if matches(r)]
                rows.append({'market':market,'source_file':str(path),'source_sha256':hashlib.sha256(raw).hexdigest(),
                    'candidate_index':index,'snapshot_metadata':{k:v for k,v in snap.items() if k!='candidates'},
                    'original_candidate':item,'classification':'exploratory_signal',
                    'prediction_status':'unevaluable','reasons':['no_explicit_forecast_target','no_precommitted_forecast_horizon'],
                    'outcome_status':'invalid_price_or_evaluation' if bad else 'available' if good else 'missing',
                    'original_outcomes':actual,'quarantine_reasons':[r['reasons'] for r in bad]})
    return {'count':len(rows),'prediction_count':0,'classification':'exploratory_only',
            'outcome_status_counts':dict(Counter(r['outcome_status'] for r in rows)), 'records':rows}


def prospective_ledger():
    predictions, observations, selected = [], [], []
    for path in sorted(Path('data/predictions/issued').glob('*/*.json')):
        raw = path.read_bytes()
        commits = subprocess.check_output(['git','log','--diff-filter=A','--format=%H','--',str(path)],text=True).splitlines()
        commit = commits[-1] if commits else ''
        for original in json.loads(raw)['predictions']:
            prediction = dict(original, evidence={'source':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'git_commit':commit})
            predictions.append(prediction)
            attempts = [json.loads(p.read_text()) for p in sorted((Path('data/predictions/observations')/prediction['id']).glob('*.json'))]
            observations.extend(attempts)
            # Freeze the first complete valid observation; retain every failed attempt for audit.
            valid = [a for a in attempts if a.get('observation_status') == 'evaluated']
            if valid or attempts:
                selected.append(valid[0] if valid else attempts[-1])
    return predictions, selected, observations


def main():
    now=datetime.now(timezone.utc)
    ledger=json.loads(LEDGER.read_text()) if LEDGER.exists() else {'predictions':[],'outcomes':[]}
    prospective, actual, observations = prospective_ledger()
    ledger['predictions'] += prospective
    ledger['outcomes'] += actual
    report={'version':'prediction-validation-v1','generated_at':now.isoformat(),
            'explicit_ledger_present':LEDGER.exists() or bool(prospective),
            'observation_attempts':observations,
            'interpretation':'Rank, material score and news sentiment are not explicit forecasts. No retrospective forecasts created.',
            'explicit_predictions':analyze(ledger['predictions'],ledger['outcomes'],now),
            'existing_signals':inventory()}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(f"Wrote {OUT}: explicit={report['explicit_predictions']['total_count']}, exploratory={report['existing_signals']['count']}")


if __name__ == '__main__':
    main()
