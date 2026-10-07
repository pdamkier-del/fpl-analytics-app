import unittest
import pandas as pd

from fpl_xpts.chip_planner import ChipPlannerConfig, build_tc_values, best_chip_options, decide_chip


class ChipPlannerTests(unittest.TestCase):
    def test_tc_evaluates_top_players_not_only_one(self):
        f=pd.DataFrame([
            dict(id=1,web_name='A',gw=10,xpts_mean=9.0),
            dict(id=2,web_name='B',gw=10,xpts_mean=12.0),
            dict(id=3,web_name='C',gw=10,xpts_mean=10.0),
        ])
        v=build_tc_values(f,current_gw=10,period_end_gw=19,config=ChipPlannerConfig(top_tc_candidates=3))
        self.assertEqual(set(v.candidate_id),{1,2,3})
        best=best_chip_options(v,current_gw=10,period_end_gw=19)
        self.assertEqual(int(best.iloc[0].candidate_id),2)
        self.assertAlmostEqual(float(best.iloc[0].raw_value),12.0)

    def test_future_uncertainty_can_make_now_better(self):
        values=pd.DataFrame([
            dict(chip='TC',gw=10,candidate_id=1,candidate_name='A',raw_value=10.0),
            dict(chip='TC',gw=18,candidate_id=2,candidate_name='B',raw_value=12.0),
        ])
        r=decide_chip(values,current_gw=10,period_end_gw=19,chips_remaining=['TC'],
                      config=ChipPlannerConfig(future_discount=.97))
        self.assertEqual(r['action'],'USE')
        self.assertEqual(r['chip'],'TC')
        self.assertGreater(r['use_edge'],0)

    def test_save_when_future_option_is_better(self):
        values=pd.DataFrame([
            dict(chip='TC',gw=10,candidate_id=1,candidate_name='A',raw_value=8.0),
            dict(chip='TC',gw=12,candidate_id=2,candidate_name='B',raw_value=12.0),
        ])
        r=decide_chip(values,current_gw=10,period_end_gw=19,chips_remaining=['TC'],
                      config=ChipPlannerConfig(future_discount=.97))
        self.assertEqual(r['action'],'NONE')

    def test_chips_compete_for_current_gw(self):
        values=pd.DataFrame([
            dict(chip='TC',gw=10,raw_value=10.0),dict(chip='TC',gw=11,raw_value=9.9),
            dict(chip='BB',gw=10,raw_value=13.0),dict(chip='BB',gw=11,raw_value=8.0),
        ])
        r=decide_chip(values,current_gw=10,period_end_gw=19,chips_remaining=['TC','BB'])
        self.assertEqual(r['chip'],'BB')

    def test_expiry_pressure_forces_use(self):
        values=pd.DataFrame([
            dict(chip='TC',gw=18,raw_value=6.0),dict(chip='TC',gw=19,raw_value=12.0),
            dict(chip='BB',gw=18,raw_value=8.0),dict(chip='BB',gw=19,raw_value=10.0),
        ])
        r=decide_chip(values,current_gw=18,period_end_gw=19,chips_remaining=['TC','BB'])
        self.assertEqual(r['action'],'USE')
        self.assertTrue(r['forced_by_expiry'])
        self.assertEqual(r['chip'],'BB')


if __name__=='__main__':
    unittest.main()