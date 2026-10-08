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

    def test_existing_ranks_are_not_forecasts(self):
        data=pv.inventory()
        self.assertEqual(data['prediction_count'],0)
        self.assertGreater(data['count'],0)
        self.assertTrue(all(r['prediction_status']=='unevaluable' for r in data['records']))

if __name__=='__main__':unittest.main()
