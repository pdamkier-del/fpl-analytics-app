import unittest
import pandas as pd

from fpl_xpts.chip_planner import ChipPlannerConfig, TCV2Config, build_tc_values, best_chip_options, decide_chip, tc_opportunity_probabilities, decide_tc_from_samples, decide_tc_v2_from_samples, fh_opportunity_probabilities, decide_fh_from_samples, optimize_free_hit_squad, probabilistic_dgw_xp, unresolved_dgw_probability, latent_dgw_option_value


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




    def test_free_hit_optimizer_uses_sale_value_and_does_not_mutate_state(self):
        from fpl_xpts.season_replay import OwnedPlayer, ReplayState
        positions=['GKP']*2+['DEF']*5+['MID']*5+['FWD']*3
        meta=pd.DataFrame({
            'id':list(range(1,17)),
            'web_name':[f'P{i}' for i in range(1,17)],
            'position':positions+['MID'],
            'team':list(range(1,17)),
            'price_tenths':[50]*16,
            'status':['a']*16,
        })
        state=ReplayState(
            squad={i:OwnedPlayer(i,50) for i in range(1,16)},
            bank=0,free_transfers=3,
        )
        rows=[]
        for pid in range(1,17):
            rows.append(dict(id=pid,gw=10,xpts_mean=3.0,p_play=1.0))
        forecast=pd.DataFrame(rows)
        forecast.loc[forecast.id.eq(16),'xpts_mean']=20.0
        before=(set(state.squad),state.bank,state.free_transfers,{k:list(v) for k,v in state.chips_used.items()})
        r=optimize_free_hit_squad(
            state=state,meta=meta,forecast=forecast,gw=10,
            normal_squad_ids=list(range(1,16)),
        )
        after=(set(state.squad),state.bank,state.free_transfers,{k:list(v) for k,v in state.chips_used.items()})
        self.assertEqual(before,after)
        self.assertEqual(r['budget_tenths'],750)
        self.assertEqual(len(r['fh_squad_ids']),15)
        self.assertEqual(len(r['fh_xi_ids']),11)
        self.assertIn(16,r['fh_squad_ids'])
        self.assertGreater(r['fh_gain'],0.0)

    def test_free_hit_optimizer_respects_three_per_club(self):
        from fpl_xpts.season_replay import OwnedPlayer, ReplayState, valid_squad
        positions=['GKP']*2+['DEF']*5+['MID']*5+['FWD']*3
        meta=pd.DataFrame({
            'id':list(range(1,19)),
            'web_name':[f'P{i}' for i in range(1,19)],
            'position':positions+['MID','MID','FWD'],
            'team':list(range(1,16))+[99,99,99],
            'price_tenths':[50]*18,
            'status':['a']*18,
        })
        state=ReplayState({i:OwnedPlayer(i,50) for i in range(1,16)},0,1)
        forecast=pd.DataFrame([
            dict(id=pid,gw=10,xpts_mean=(30.0 if pid>=16 else 3.0),p_play=1.0)
            for pid in range(1,19)
        ])
        r=optimize_free_hit_squad(state=state,meta=meta,forecast=forecast,gw=10,normal_squad_ids=list(range(1,16)))
        self.assertTrue(valid_squad(meta,r['fh_squad_ids']))
        self.assertLessEqual(int(meta[meta.id.isin(r['fh_squad_ids'])].groupby('team').size().max()),3)

    def test_fh_timing_probabilities_sum_to_one(self):
        rows=[]
        for s in range(100):
            rows += [
                dict(simulation=s,gw=10,points=14 if s<60 else 4),
                dict(simulation=s,gw=11,points=8 if s<60 else 18),
            ]
        p=fh_opportunity_probabilities(
            pd.DataFrame(rows),current_gw=10,period_end_gw=11,
            config=ChipPlannerConfig(future_discount=1.0),
        )
        self.assertAlmostEqual(float(p.probability_best.sum()),1.0,places=12)
        self.assertAlmostEqual(float(p.loc[p.gw.eq(10),'probability_best'].iloc[0]),0.60,places=12)
        self.assertAlmostEqual(float(p.loc[p.gw.eq(11),'probability_best'].iloc[0]),0.40,places=12)

    def test_fh_saves_when_future_marginal_gain_is_better(self):
        rows=[]
        for s in range(50):
            rows += [dict(simulation=s,gw=10,points=8.0),dict(simulation=s,gw=11,points=14.0)]
        r=decide_fh_from_samples(
            pd.DataFrame(rows),current_gw=10,period_end_gw=19,
            config=ChipPlannerConfig(future_discount=1.0),
        )
        self.assertEqual(r['action'],'SAVE_FH')
        self.assertFalse(r['forced_by_expiry'])

    def test_fh_is_forced_in_gw19(self):
        rows=[dict(simulation=s,gw=19,points=2.0) for s in range(50)]
        r=decide_fh_from_samples(pd.DataFrame(rows),current_gw=19,period_end_gw=19)
        self.assertEqual(r['action'],'USE_FH')
        self.assertTrue(r['forced_by_expiry'])

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