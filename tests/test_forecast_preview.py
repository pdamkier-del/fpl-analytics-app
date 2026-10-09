#!/usr/bin/env python3
"""Contract tests for bridge preview; NEVER claim the locked MM/PM is running."""
import json,sys,unittest
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'model'))
import forecast_preview

DEFAULT=[496,572,8,173,204,229,469,15,40,154,290,399,165,346,411]
class ForecastPreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'model/base_data.json').read_text(encoding='utf8'))
    def test_preview_has_six_weeks_and_all_chips(self):
        r=forecast_preview.forecast_preview(self.data,{'player_ids':DEFAULT,'bank':1.0,'free_transfers':1},
          now=datetime(2026,10,9,tzinfo=timezone.utc))
        self.assertEqual(r['mode'],'bridge_preview_indicative_only')
        self.assertFalse(r['locked_forecast_active'])
        self.assertTrue(r['data']['stale'])
        self.assertEqual(r['data']['available_gws'],[6,7,8,9,10,11])
        self.assertEqual(len(r['weeks']),6)
        self.assertEqual({c['id'] for c in r['chips']},{'fh','wc','bb','tc'})
        self.assertTrue(all(c['confidence']=='indicative_only' for c in r['chips']))
        self.assertGreater(r['weeks'][0]['xi_xp'],0)
        print('PREVIEW_TEST_RESULT',json.dumps({
          'source':r['data']['model_version'],'stale':r['data']['stale'],
          'gws':r['data']['available_gws'],'chip_candidates':{
            x['id']:x['candidate_gw'] for x in r['chips']},
          'xi_xp_first':r['weeks'][0]['xi_xp']},ensure_ascii=False),flush=True)
    def test_invalid_squad_does_not_fabricate_forecast(self):
        r=forecast_preview.forecast_preview(self.data,{'player_ids':[411]},now=datetime(2026,10,9,tzinfo=timezone.utc))
        self.assertEqual(r['weeks'],[])
        self.assertEqual(r['chips'],[])
        self.assertFalse(r['locked_forecast_active'])
    def test_official_next_gw_supersedes_stale_bridge(self):
        r=forecast_preview.forecast_preview(self.data,{'player_ids':DEFAULT,'bank':1.0},
            official={'official_next_gw':9,'observed_at_utc':'2026-10-09T10:00:00Z',
                      'players':[{'id':411}],'fixtures':[{'event':9}]},
            now=datetime(2026,10,9,tzinfo=timezone.utc))
        self.assertEqual(r['data']['available_gws'],[9,10,11])
        self.assertEqual(len(r['weeks']),3)
        self.assertTrue(all(c['candidate_gw'] is None or c['candidate_gw']>=9 for c in r['chips']))
        self.assertEqual(r['data']['official_player_count'],1)
        self.assertTrue(any('Officielle FPL-data' in a for a in r['alerts']))
    def test_no_future_invented(self):
        data=json.loads(json.dumps(self.data))
        data['meta']['next_gw']=38
        r=forecast_preview.forecast_preview(data,{'player_ids':DEFAULT},now=datetime(2026,10,9,tzinfo=timezone.utc))
        self.assertEqual(r['weeks'],[])
        self.assertEqual(r['chips'],[])
    def test_publisher_bundles_preview(self):
        s=(ROOT/'scripts/publish_fpl_update.py').read_text(encoding='utf8')
        self.assertIn("ROOT/'model'/'forecast_preview.py'",s)
        self.assertIn("ROOT/'app'",s)
        self.assertIn("ROOT/'config'/'fpl_locked_model.json'",s)
        self.assertIn("ROOT/'src'/'fpl_xpts'",s)
        self.assertIn("ROOT/'src'/'fpl_v1_1_model'",s)
        self.assertIn("schedule_snapshot=ROOT/'scripts'/'snapshot_fpl_schedule.py'",s)
    def test_local_api_is_wired(self):
        src=(ROOT/'start_app.py').read_text(encoding='utf8')
        self.assertIn("'/api/forecast/preview'",src)
        self.assertIn('forecast_preview.forecast_preview(',src)
        page=(ROOT/'app/forecast-center.html').read_text(encoding='utf8')
        self.assertIn('/api/forecast/preview',page)
        self.assertIn('ikke låst chipforecast',page)
if __name__=='__main__':
    unittest.main()
