import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from scripts import research_predictions as rp
from scripts import build_prediction_validation as pv

NOW=datetime(2026,10,1,22,tzinfo=timezone.utc)

class ResearchTests(unittest.TestCase):
    def bars(self,sessions,flat=False):
        return [dict(session=d,next_open=100,next_high=105,next_low=99,next_close=100 if flat else 100+i*.4,splits=0) for i,d in enumerate(sessions)]

    def test_calendar_holidays_weekend_and_full_future_sessions(self):
        kr=rp.schedule('KR',datetime(2026,10,8,8,tzinfo=timezone.utc))
        self.assertEqual(kr['future_sessions'][0]['session'],'2026-10-12')
        us=rp.schedule('US',datetime(2026,10,8,15,tzinfo=timezone.utc))
        self.assertEqual(us['future_sessions'][0]['session'],'2026-10-09')
        self.assertEqual(len(us['future_sessions']),20)

    def test_model_abstention_missing_and_invalid_inputs(self):
        days=rp.schedule('US',NOW)['past_sessions'];bars=self.bars(days)
        self.assertEqual(rp.model_input(bars,days)[0],'up')
        descending=self.bars(days)
        for i,b in enumerate(descending):b['next_close']=103-i*.4
        self.assertEqual(rp.model_input(descending,days)[0],'down')
        self.assertIsNone(rp.model_input(self.bars(days,flat=True),days)[0])
        self.assertIsNone(rp.model_input(bars[:-1],days)[0])
        bars[0]['next_open']=0
        self.assertIsNone(rp.model_input(bars,days)[0])

    def test_issuance_is_immutable_pending_and_no_historical_backfill(self):
        old=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                source=Path('data/history/top_us/2026-10-01.json');source.parent.mkdir(parents=True)
                source.write_text(json.dumps({'snapshot_at':NOW.isoformat(),'signal_date':'2026-10-01','candidates':[{'symbol':'TEST','rank':1}]}))
                days=rp.schedule('US',NOW)['past_sessions']
                result=rp.issue('US',NOW,fetch=lambda *args:self.bars(days))
                path=Path(result['path']);raw=path.read_bytes();predictions=json.loads(raw)['predictions']
                self.assertEqual(len(predictions),3)
                self.assertEqual({p['horizon'] for p in predictions},{'1_trading_sessions','5_trading_sessions','20_trading_sessions'})
                self.assertTrue(all(p['issuance_status']=='issued' and 'probability' not in p for p in predictions))
                self.assertEqual(rp.issue('US',NOW,fetch=lambda *args:[] )['status'],'already_recorded')
                self.assertEqual(path.read_bytes(),raw)
                for p in predictions:
                    p['evidence']={'source':str(path),'sha256':hashlib.sha256(raw).hexdigest()}
                with patch.object(pv,'verified_archive',return_value=True):
                    report=pv.analyze(predictions,[],NOW)
                self.assertEqual(report['status_counts'],{'pending':3})
                with self.assertRaisesRegex(ValueError,'current_day_snapshot_missing'):
                    rp.issue('US',NOW+timedelta(days=1),fetch=lambda *args:self.bars(days))
            finally:os.chdir(old)

    def test_missing_attempts_retained_then_first_valid_observation_frozen(self):
        old=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                p={'id':'US-test-1','symbol':'TEST','market':'US','ticker':'TEST','issuance_status':'issued',
                   'baseline_close':100,'baseline_session':'2026-09-30','evaluation_session':'2026-10-01',
                   'evaluation_at':'2026-10-01T20:00:00+00:00'}
                rp.save_new(Path('data/predictions/issued/US/day.json'),{'predictions':[p]})
                self.assertEqual(rp.collect_outcomes(NOW,fetch=lambda *args:[]),1)
                self.assertEqual(rp.collect_outcomes(NOW,fetch=lambda *args:[]),0)
                bars=self.bars(['2026-10-01'])
                self.assertEqual(rp.collect_outcomes(NOW+timedelta(days=1),fetch=lambda *args:bars),1)
                self.assertEqual(rp.collect_outcomes(NOW+timedelta(days=2),fetch=lambda *args:[]),0)
                attempts=list(Path('data/predictions/observations/US-test-1').glob('*.json'))
                self.assertEqual(len(attempts),2)
                self.assertEqual({json.loads(a.read_text())['observation_status'] for a in attempts},{'missing_outcome','evaluated'})
            finally:os.chdir(old)

    def test_abstained_records_never_enter_hit_rate(self):
        r=pv.evaluate({'issuance_status':'abstained','issuance_reasons':['within_1pct_deadband']},[],NOW)
        self.assertEqual(r['status'],'unevaluable')
        self.assertEqual(r['reasons'],['within_1pct_deadband'])

if __name__=='__main__':unittest.main()
