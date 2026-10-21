import copy
from dataclasses import replace
import numpy as np
import pytest
from b_chain_contract import VERSION,SCENARIOS,duration_pmf,field_marginals,prepare_match,validate_forecast
from b_preview_ts import autosub_points,preview_scoring
from fpl_v1_1_model.joint_simulator import PlayerSimInput,MatchSimInput,simulate_many
from fpl_v1_1_model.forecast_snapshot import seal_forecast
from test_mm_locked_bridge import ts_fixture


def unified_fixture():
    f,s=ts_fixture();f.update(model=VERSION,mm_version=VERSION,
        minute_sampler_audit={'sampler':VERSION,'all_MM_to_PM_means_consistent':True},
        scenario_contract={'version':SCENARIOS,'draws':5})
    for p in f['players']:
        for w in p['weeks']:
            points=[4]*5;minutes=[90]*5
            if p['id']==1:points[0]=0;minutes[0]=0
            if p['id']==2:points=[2]*5
            w.update(xpts=float(np.mean(points)),xmins=float(np.mean(minutes)),pm_analytic_minutes=float(np.mean(minutes)),
                p_play=float(np.mean(np.array(minutes)>0)),scenarios={'points':points,'minutes':minutes},
                fixtures=[{'xmins':float(np.mean(minutes)),'pm_analytic_minutes':float(np.mean(minutes))}])
    return seal_forecast(f),s


@pytest.mark.parametrize('mean',[1,2,10,45,60,80,89.9,90])
def test_pmf_is_bounded_normalized_and_preserves_conditional_mean(mean):
    for sigma in (7,10):
        mass=duration_pmf(mean,sigma)
        assert len(mass)==91 and min(mass)>=0 and mass[0]==0
        assert mass.sum()==pytest.approx(1)
        assert mass@np.arange(91)==pytest.approx(mean,abs=1e-9)


def test_mixture_preserves_mm_and_has_compatible_probabilities():
    p=PlayerSimInput('x','H','MID',.65,.25,87.,16.)
    mass=field_marginals(p)
    assert mass@np.arange(91)==pytest.approx(.65*87+.35*.25*16)
    assert mass[0]==pytest.approx(.35*.75)
    assert mass[90]<=sum(mass[60:])<=1-mass[0]


@pytest.mark.parametrize('first_available',[True,False])
def test_published_penalty_role_wins_only_while_available(first_available):
    first=PlayerSimInput('first','H','MID',float(first_available),0,90,1,goal_weight=1,penalty_weight=.001,penalty_conversion=1)
    second=PlayerSimInput('second','H','MID',1,0,90,1,goal_weight=1,penalty_weight=.999,penalty_conversion=1)
    inp=prepare_match(MatchSimInput('H','A',0,0,(first,second),lambda_home_penalties=2),
        {'first':{'penalties_order':1},'second':{'penalties_order':2}})
    sim=simulate_many(inp,n=60,seed=123)
    winner='first'if first_available else'second';loser='second'if first_available else'first'
    assert sim[winner]['goal_points']>5
    assert sim[loser]['goal_points']==0


def test_autosubs_respect_keeper_separation_formation_priority_and_cameos():
    # 3-4-3; missing defender and keeper. First bench MID cannot take the DEF
    # slot; second bench DEF can. A one-minute starter blocks a replacement.
    positions=['GKP']+['DEF']*3+['MID']*4+['FWD']*3+['MID','DEF','DEF','GKP']
    points=np.ones((3,15));plays=np.ones((3,15),bool)
    plays[0,[0,1]]=False;points[0,[0,1]]=0
    points[:,11:]=[10,5,3,2]
    plays[1,1]=False;points[1,1]=0
    scores=autosub_points(points,plays,positions,list(range(11)),list(range(11,15)))
    assert scores.tolist()==[16,15,11]


def test_real_six_gw_worker_reuses_search_and_restores_originals():
    from service.preview_manager_job import calculate
    import fpl_xpts.transfer_planner as planner
    import fpl_xpts.optimize as optimize
    f,s=unified_fixture();before=copy.deepcopy(s);original=(planner._fast_manager_score,optimize.plan_squad)
    result=calculate(f,s)
    assert s==before and original==(planner._fast_manager_score,optimize.plan_squad)
    assert len(result['plan']['path'])==6 and len(result['lineup'])==15
    assert result['chain_version']==VERSION and not result['chips_ran']
    # Field XI:40; keeper3.2 + fallback .4; captain4 =>47.6.
    assert result['current_team']['expected_score']==pytest.approx(47.6)
    assert result['comparison']['hold_squad_without_transfers'][0]['expected_score']==pytest.approx(47.6)
    assert result['plan']['path'][0]['projected_manager_score']==pytest.approx(47.6)


def test_better_reserve_is_credited_by_fast_search_and_reported_lineup():
    f,s=unified_fixture()
    with preview_scoring(f)as scorer:
        a=scorer.decision(7,tuple(range(1,16)))[-1]
    for w in f['players'][1]['weeks']:
        w['scenarios']['points']=[3]*5;w['xpts']=3.
    f=seal_forecast(f)
    with preview_scoring(f)as scorer:
        b=scorer.decision(7,tuple(range(1,16)))[-1]
    assert b-a==pytest.approx(.2)


def test_contract_rejects_inconsistent_means_and_scenario_marginals():
    f,_=unified_fixture();assert validate_forecast(f)
    for name in ['points','minutes']:
        bad=copy.deepcopy(f);bad['players'][0]['weeks'][0]['scenarios'][name].pop()
        with pytest.raises(ValueError):validate_forecast(bad)
    bad=copy.deepcopy(f);bad['players'][0]['weeks'][0]['xpts']+=1
    with pytest.raises(ValueError):validate_forecast(bad)


def test_private_api_accepts_unified_only_on_preview_route():
    from service.app import verify_current_window
    from test_mm_preview_service import official
    f,_=unified_fixture()
    assert verify_current_window(f,official(f),preview=True)==7
    with pytest.raises(ValueError):verify_current_window(f,official(f),preview=False)
