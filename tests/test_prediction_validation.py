import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from scripts import build_prediction_validation as pv

NOW=datetime(2026,10,8,tzinfo=timezone.utc)

def prediction(kind='direction',target='up',**extra):
    p=dict(id='p1',symbol='TEST',market='US',issued_at='2026-10-01T12:00:00Z',recorded_at='2026-10-01T12:01:00Z',
           evaluation_at='2026-10-02T20:00:00Z',horizon='next_session_close',type=kind,target=target,
           baseline_close=100,rule_version='test-v1',evidence={'source':'archive.json','sha256':'test'})
    return dict(p,**extra)

def outcome(**extra):
    o=dict(prediction_id='p1',symbol='TEST',market='US',evaluation_at='2026-10-02T20:00:00Z',source='fixture',
           next_open=100,next_high=110,next_low=99,next_close=105)
    return dict(o,**extra)

class PredictionTests(unittest.TestCase):
    def test_archive_git_timestamp_has_second_precision(self):
        import hashlib
        import json
        p=prediction(issued_at='2026-10-01T12:00:00.987654Z',recorded_at='2026-10-01T12:00:00.987654Z')
        archived={k:v for k,v in p.items() if k!='evidence'}
        raw=json.dumps({'predictions':[archived]}).encode()
        p['evidence']={'source':'archive.json','sha256':hashlib.sha256(raw).hexdigest(),'git_commit':'a'*40}
        with patch.object(pv.subprocess,'check_output',side_effect=[raw,'2026-10-01T12:00:00Z']):
            self.assertTrue(pv.verified_archive(p))
        with patch.object(pv.subprocess,'check_output',side_effect=[raw,'2026-10-01T11:59:59Z']):
            self.assertFalse(pv.verified_archive(p))

    def test_unproven_predictions_never_score(self):
        r=pv.evaluate(prediction(),[outcome()],NOW)
        self.assertEqual(r['status'],'unevaluable')
        self.assertIn('unverified_contemporaneous_archive',r['reasons'])

    @patch.object(pv,'verified_archive',return_value=True)
    def test_direction_and_failure_denominator(self,_):
        records=[prediction(),prediction(id='p2',target='down')]
        report=pv.analyze(records,[outcome(),outcome(prediction_id='p2')],NOW)
        self.assertEqual(len(report['records']),2)
        self.assertEqual(report['groups'][0]['hit_rate_pct'],50)
        self.assertEqual(report['groups'][0]['always_up_hit_rate_pct'],100)
        self.assertEqual(report['groups'][0]['sample_status'],'표본 부족')

    @patch.object(pv,'verified_archive',return_value=True)
    def test_price_return_probability_metrics(self,_):
        for kind,target,metric,expected in [('price',103,'bias',-2),('return',3,'bias',-2),('probability_up',.8,'brier_score',.04)]:
            report=pv.analyze([prediction(kind,target)],[outcome()],NOW)
            self.assertAlmostEqual(report['groups'][0][metric],expected)
        bins=report['groups'][0]['calibration_bins']
        self.assertEqual(bins[0]['observed_frequency'],1)

    @patch.object(pv,'verified_archive',return_value=True)
    def test_pending_missing_invalid_and_mismatched_period(self,_):
        self.assertEqual(pv.evaluate(prediction(evaluation_at='2027-01-01T00:00:00Z'),[],NOW)['status'],'pending')
        self.assertEqual(pv.evaluate(prediction(),[],NOW)['status'],'missing_outcome')
        self.assertEqual(pv.evaluate(prediction(),[outcome(next_high=0)],NOW)['status'],'invalid_price')
        self.assertEqual(pv.evaluate(prediction(),[outcome(evaluation_at='2026-10-03T20:00:00Z')],NOW)['status'],'unevaluable')
        self.assertEqual(pv.evaluate(prediction(horizon=None),[outcome()],NOW)['status'],'unevaluable')
        self.assertEqual(pv.evaluate(prediction(recorded_at='2026-10-03T00:00:00Z'),[outcome()],NOW)['status'],'unevaluable')

    @patch.object(pv,'verified_archive',return_value=True)
    def test_duplicates_not_cherry_picked_and_groups_separate(self,_):
        report=pv.analyze([prediction(),prediction()],[outcome()],NOW)
        self.assertEqual(report['status_counts'],{'unevaluable':2})
        report=pv.analyze([prediction(),prediction(id='p2',horizon='week_close')],[],NOW)
        self.assertEqual(len(report['groups']),2)

    @patch.object(pv,'verified_archive',return_value=True)
    def test_cumulative_pool_crosses_symbols_and_months_without_inflating_denominator(self,_):
        predictions=[];outcomes=[]
        for i in range(30):
            symbol='A' if i%2 else 'B'
            issued='2026-09-01T12:00:00Z' if i<15 else '2026-10-01T12:00:00Z'
            predictions.append(prediction(id=str(i),symbol=symbol,target='up' if i%2 else 'down',issued_at=issued))
            outcomes.append(outcome(prediction_id=str(i),symbol=symbol))
        predictions.extend([prediction(id='missing'),prediction(id='bad'),
            prediction(id='pending',evaluation_at='2027-01-01T00:00:00Z'),
            prediction(id='abstain',target=None,issuance_status='abstained',issuance_reasons=['within_1pct_deadband'])])
        outcomes.append(outcome(prediction_id='bad',next_high=0))
        report=pv.analyze(predictions,outcomes,NOW)
        group=report['cumulative_groups'][0]
        self.assertEqual(len(report['cumulative_groups']),1)
        self.assertEqual(group['total_count'],34)
        self.assertEqual(group['evaluated_count'],30)
        self.assertEqual(group['status_counts'],{'evaluated':30,'missing_outcome':1,'invalid_price':1,'pending':1,'unevaluable':1})
        self.assertEqual(group['abstained_count'],1)
        self.assertEqual(group['pending_count'],1)
        self.assertEqual(group['sample_status'],'분석 가능')
        self.assertEqual(group['hit_rate_pct'],50)
        self.assertEqual(group['always_up_hit_rate_pct'],100)
        self.assertTrue(all(g['sample_status']=='표본 부족' for g in report['groups']))
        self.assertEqual(len(report['records']),34)

    @patch.object(pv,'verified_archive',return_value=True)
    def test_cumulative_keeps_market_horizon_type_and_version_separate(self,_):
        predictions=[prediction(),prediction(id='other-market',market='KR'),
            prediction(id='other-horizon',horizon='5_trading_sessions'),
            prediction(id='other-model',rule_version='test-v2'),prediction('return',1,id='return'),
            prediction('price',101,id='price-a',symbol='A'),prediction('price',101,id='price-b',symbol='B')]
        report=pv.analyze(predictions,[],NOW)
        self.assertEqual(len(report['cumulative_groups']),7)
        self.assertTrue(all(g['evaluated_count']==0 and g['sample_status']=='표본 부족' for g in report['cumulative_groups']))
        self.assertTrue(all('hit_rate_pct' not in g for g in report['cumulative_groups']))
        self.assertEqual({g['price_symbol'] for g in report['cumulative_groups'] if g['type']=='price'},{'A','B'})

    def test_existing_ranks_are_not_forecasts(self):
        data=pv.inventory()
        self.assertEqual(data['prediction_count'],0)
        self.assertGreater(data['count'],0)
        self.assertTrue(all(r['prediction_status']=='unevaluable' for r in data['records']))

if __name__=='__main__':unittest.main()
