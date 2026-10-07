import unittest
import pandas as pd

from fpl_xpts.chip_planner import ChipPlannerConfig, TCV2Config, build_tc_values, best_chip_options, decide_chip, tc_opportunity_probabilities, decide_tc_from_samples, decide_tc_v2_from_samples, probabilistic_dgw_xp, unresolved_dgw_probability, latent_dgw_option_value


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


    def test_tc_timing_probabilities_sum_to_one(self):
        rows=[]
        for s in range(100):
            rows += [
                dict(simulation=s,gw=10,candidate_id=1,candidate_name='A',points=10 if s<60 else 4),
                dict(simulation=s,gw=11,candidate_id=2,candidate_name='B',points=7 if s<60 else 13),
                dict(simulation=s,gw=12,candidate_id=3,candidate_name='C',points=6),
            ]
        p=tc_opportunity_probabilities(pd.DataFrame(rows),current_gw=10,period_end_gw=12,
                                       config=ChipPlannerConfig(future_discount=1.0))
        self.assertAlmostEqual(float(p.probability_best.sum()),1.0,places=12)
        self.assertAlmostEqual(float(p.loc[p.gw.eq(10),'probability_best'].iloc[0]),0.60,places=12)
        self.assertAlmostEqual(float(p.loc[p.gw.eq(11),'probability_best'].iloc[0]),0.40,places=12)

    def test_tc_probabilities_renormalize_after_gw_passes(self):
        rows=[]
        for s in range(50):
            rows += [
                dict(simulation=s,gw=11,candidate_id=2,candidate_name='B',points=8+s%3),
                dict(simulation=s,gw=12,candidate_id=3,candidate_name='C',points=7+(s%5)),
            ]
        p=tc_opportunity_probabilities(pd.DataFrame(rows),current_gw=11,period_end_gw=12)
        self.assertAlmostEqual(float(p.probability_best.sum()),1.0,places=12)
        self.assertEqual(p.gw.tolist(),[11,12])

    def test_tc_decision_uses_expected_option_value_not_only_probability(self):
        rows=[]
        for s in range(100):
            rows += [
                dict(simulation=s,gw=10,candidate_id=1,candidate_name='A',points=10),
                dict(simulation=s,gw=11,candidate_id=2,candidate_name='B',points=20 if s<40 else 5),
            ]
        r=decide_tc_from_samples(pd.DataFrame(rows),current_gw=10,period_end_gw=11,
                                 config=ChipPlannerConfig(future_discount=1.0))
        self.assertAlmostEqual(float(r['timing_probabilities'].probability_best.sum()),1.0,places=12)
        self.assertIn(r['action'],{'USE_TC','SAVE_TC'})


    def test_probabilistic_dgw_becomes_normal_when_confirmed(self):
        self.assertAlmostEqual(probabilistic_dgw_xp(7.0,6.0,0.0),7.0)
        self.assertAlmostEqual(probabilistic_dgw_xp(7.0,6.0,0.5),10.0)
        self.assertAlmostEqual(probabilistic_dgw_xp(7.0,6.0,1.0),13.0)

    def test_latent_dgw_mass_disappears_as_concrete_dgw_resolves(self):
        self.assertAlmostEqual(unresolved_dgw_probability(1.0,0.0),1.0)
        self.assertAlmostEqual(unresolved_dgw_probability(1.0,0.7),0.3)
        self.assertAlmostEqual(unresolved_dgw_probability(1.0,1.0),0.0)

    def test_latent_dgw_option_regresses_between_mu_and_reference(self):
        mu=8.57
        full=latent_dgw_option_value(mu_tc=mu,unresolved_probability=1.0)
        half=latent_dgw_option_value(mu_tc=mu,unresolved_probability=0.5)
        none=latent_dgw_option_value(mu_tc=mu,unresolved_probability=0.0)
        self.assertAlmostEqual(full,12.26875)
        self.assertAlmostEqual(half,mu+0.5*(12.26875-mu))
        self.assertIsNone(none)

    def test_tc_v2_latent_dgw_can_hold_chip(self):
        rows=[]
        for s in range(100):
            rows += [
                dict(simulation=s,gw=20,candidate_id=1,candidate_name='Now',points=10.0),
                dict(simulation=s,gw=21,candidate_id=2,candidate_name='Future',points=9.0),
            ]
        r=decide_tc_v2_from_samples(
            pd.DataFrame(rows),current_gw=20,period_end_gw=38,
            unresolved_dgw_probability=1.0,
            config=TCV2Config(mu_tc=8.57,dgw_reference_xp=12.26875),
        )
        self.assertEqual(r['action'],'SAVE_TC')
        self.assertEqual(r['save_source'],'latent_dgw')
        self.assertAlmostEqual(r['latent_dgw_option_value'],12.26875)

    def test_tc_v2_confirmed_dgw_removes_latent_option(self):
        rows=[]
        for s in range(100):
            rows += [
                dict(simulation=s,gw=20,candidate_id=1,candidate_name='Now',points=10.0),
                dict(simulation=s,gw=21,candidate_id=2,candidate_name='ConfirmedDGW',points=13.0),
            ]
        r=decide_tc_v2_from_samples(
            pd.DataFrame(rows),current_gw=20,period_end_gw=38,
            unresolved_dgw_probability=0.0,
        )
        self.assertIsNone(r['latent_dgw_option_value'])
        self.assertEqual(r['save_source'],'concrete_gw')
        self.assertEqual(r['best_future_gw'],21)

    def test_tc_v2_uses_historical_structural_prior_by_default(self):
        rows=[]
        for s in range(50):
            rows += [
                dict(simulation=s,gw=20,candidate_id=1,candidate_name='Now',points=10.0),
                dict(simulation=s,gw=21,candidate_id=2,candidate_name='Future',points=9.0),
            ]
        r=decide_tc_v2_from_samples(pd.DataFrame(rows),current_gw=20,period_end_gw=38)
        self.assertAlmostEqual(r['structural_dgw_probability'],1.0)
        self.assertAlmostEqual(r['unresolved_dgw_probability'],1.0)
        self.assertEqual(r['save_source'],'latent_dgw')

    def test_tc_v2_concrete_probability_transfers_structural_mass(self):
        rows=[]
        for s in range(50):
            rows += [
                dict(simulation=s,gw=20,candidate_id=1,candidate_name='Now',points=10.0),
                dict(simulation=s,gw=21,candidate_id=2,candidate_name='Future',points=11.0),
            ]
        r=decide_tc_v2_from_samples(
            pd.DataFrame(rows),current_gw=20,period_end_gw=38,
            concrete_dgw_probability=0.75,
        )
        self.assertAlmostEqual(r['unresolved_dgw_probability'],0.25)

if __name__=='__main__':
    unittest.main()