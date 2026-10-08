import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_performance_analysis as performance
from scripts import build_persistence_performance as persistence
from scripts import evaluate_top_history as kr
from scripts import evaluate_us_top_history as us
from scripts.validation_quality import evaluation_errors, finalize_evaluation, partition_records

ROOT = Path(__file__).resolve().parents[1]


def good():
    return finalize_evaluation(dict(signal_date='2026-08-27', symbol='094820', rank=1,
        baseline_close=100, next_open=101, next_high=105, next_low=99, next_close=102))


class QualityTests(unittest.TestCase):
    def test_invalid_prices_and_returns(self):
        for field in ('baseline_close', 'next_open', 'next_high', 'next_low', 'next_close'):
            for value in (None, 0, -1, float('nan'), float('inf'), '100', True):
                with self.subTest(field=field, value=value):
                    row = good(); row[field] = value
                    self.assertTrue(evaluation_errors(row))
                    self.assertFalse(partition_records([row])[0])
        for value in (None, float('nan'), float('inf'), '2', True, 999):
            row = good(); row['next_close_pct'] = value
            self.assertTrue(evaluation_errors(row))

    def test_valid_and_impossible_bars(self):
        self.assertEqual(evaluation_errors(good()), [])
        row = good(); row['next_high'] = 101
        self.assertIn('invalid_ohlc', evaluation_errors(row))
        row = good(); row['next_low'] = 103
        self.assertIn('invalid_ohlc', evaluation_errors(row))
        flat = dict.fromkeys(('baseline_close','next_open','next_high','next_low','next_close'), 100)
        self.assertEqual(evaluation_errors(finalize_evaluation(flat)), [])

    def test_nonmutating_quarantine_and_duplicates(self):
        row = good(); bad = good(); bad.update(symbol='BAD', next_open=0,next_high=0,next_low=0)
        rows = [row,bad,dict(status='pending')]; original = copy.deepcopy(rows)
        valid, excluded = partition_records(rows)
        self.assertEqual(valid,[row]); self.assertEqual(excluded[0]['source_index'],1)
        self.assertEqual(rows, original)
        self.assertEqual(len(partition_records([row,copy.deepcopy(row)])[1]),2)
        self.assertEqual(len(partition_records([dict(row,status='pending'),row])[0]),1)

    def test_all_consumers_exclude_bad_record(self):
        bad=good(); bad.update(symbol='BAD',next_open=0,next_high=0,next_low=0,gap_open_pct=-100,next_high_pct=-100,next_low_pct=-100)
        rows=[good(),bad]
        report=performance.analyze_market({'records':rows},'KR')
        self.assertEqual(report['overall']['count'],1)
        self.assertEqual(report['overall']['avg_high_return_pct'],5)
        self.assertEqual(report['by_rank'][0]['count'],1)
        for module in (kr,us):
            self.assertEqual(module.summarize(rows)['evaluated_count'],1)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); result=folder/'results.json'; snap=folder/'snap';snap.mkdir()
            result.write_text(json.dumps({'records':rows}))
            (snap/'day.json').write_text(json.dumps({'signal_date':'2026-08-27','candidates':rows}))
            report=persistence.analyze_market(snap,result,'KR')
            self.assertEqual(report['overall']['count'],1)
            self.assertEqual(report['data_quality']['excluded_count'],1)

    def test_evaluators_quarantine_new_bad_bars_and_preserve_history(self):
        for module in (kr,us):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp); snap=folder/'snap';snap.mkdir(); result=folder/'results.json'
                original=good();original['symbol']='OLD'
                result.write_text(json.dumps({'records':[original]}))
                (snap/'day.json').write_text(json.dumps({'signal_date':'2026-08-27','candidates':[
                    {'symbol':'094820','market':'KOSDAQ','rank':1,'baseline_close':100}]}))
                bar=dict(trade_date='2026-08-28',open=0,high=0,low=0,close=102,volume=0)
                with patch.object(module,'HISTORY_DIR',snap),patch.object(module,'RESULTS',result),patch.object(module,'next_trade_bar',return_value=bar):
                    module.main();module.main()
                rows=json.loads(result.read_text())['records']
                self.assertEqual(len(rows),2)
                self.assertIn(original,rows)
                bad=next(r for r in rows if r['symbol']=='094820')
                self.assertEqual(bad['status'],'invalid')
                self.assertIsNone(bad['next_high_pct'])
                self.assertEqual(bad['next_high'],0)

    def test_finalization_recomputes_valid_returns_and_rejects_bad_baseline(self):
        row = good(); row['next_close_pct'] = -100
        self.assertEqual(finalize_evaluation(row)['next_close_pct'], 2)
        row = good(); row['baseline_close'] = 0
        self.assertEqual(finalize_evaluation(row)['status'], 'invalid')
        self.assertIsNone(row['next_close_pct'])

    def test_integrity_cli_exit_and_report(self):
        for bad in (False,True):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)
                for name in ('top','top_us'):
                    target=folder/'data/history'/name;target.mkdir(parents=True)
                    (target/'day.json').write_text(json.dumps({'candidates':[]}))
                target=folder/'data/validation';target.mkdir(parents=True)
                row=good()
                if bad: row['next_open']=0
                for name in ('results.json','results_us.json'):
                    (target/name).write_text(json.dumps({'records':[row]}))
                process=subprocess.run([sys.executable,str(ROOT/'scripts/check_data_integrity.py')],cwd=folder,capture_output=True)
                self.assertEqual(process.returncode,int(bad),process.stderr)
                report=json.loads((folder/'data/health/integrity_report.json').read_text())
                self.assertEqual(report['summary']['errors'],2 if bad else 0)

    def test_malformed_source_fails_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text('{broken')
            for module in (performance,persistence):
                with self.assertRaises(json.JSONDecodeError):module.load_json(path)
            for module in (kr,us):
                with patch.object(module,'RESULTS',path),self.assertRaises(json.JSONDecodeError):module.load_results()
            self.assertEqual(path.read_text(),'{broken')

    def test_repository_regression(self):
        for market,name in [('KR','results.json'),('US','results_us.json')]:
            payload=json.loads((ROOT/'data/validation'/name).read_text())
            report=performance.analyze_market(payload,market)
            valid, excluded = partition_records(payload['records'])
            self.assertEqual(report['overall']['count'],len(valid))
            self.assertEqual(report['data_quality']['excluded_count'],len(excluded))
            self.assertEqual(len(valid) + len(excluded), sum(r.get('status') in ('evaluated','invalid') for r in payload['records']))
            if market=='KR':
                self.assertTrue(any(e['record']['symbol']=='094820' and e['record']['signal_date']=='2026-08-27' for e in report['quarantine']))


if __name__ == '__main__':
    unittest.main()
