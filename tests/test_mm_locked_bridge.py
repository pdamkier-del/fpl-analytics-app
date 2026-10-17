"""Synthetic adapter regressions, never personal recommendations."""
import copy
from datetime import datetime,timezone,timedelta
from dataclasses import asdict
import numpy as np
import pandas as pd
import pytest
from mm_locked_bridge import attach_mm,run_current_ts,locked_sampler_expectation
from fpl_v1_1_model.forecast_snapshot import seal_forecast


def inputs():
    mm=pd.DataFrame([dict(season='2025-26',fixture_uuid='f',player_uuid=str(i),team_id=1,
        pos='GK' if i==0 else 'MID',gw=22,cutoff='2026-01-17T11:00:00Z',p=.7,q=.2,s=80.,c=15.,x=56.9) for i in range(12)])
    pm=mm[['season','fixture_uuid','player_uuid','team_id','pos','gw','cutoff']].copy()
    for c,v in dict(v4_workload_start_p_start=.5,v4_p_cameo_given_bench=.3,
        v4_start_minutes_mean=75.,v4_cameo_minutes_mean=20.,v4_workload_start_xmins=40.5,
        control_p_start=.6,control_xmins=46.8,goal_mu=.2,assist_mu=.1,mu_dc=3.,
        p_cameo_given_bench=.3,start_minutes_mean=75.,cameo_minutes_mean=15.).items():pm[c]=v
    return pm,mm


def test_bridge_changes_only_candidate_minutes_not_propensities_or_input():
    pm,mm=inputs();before=pm.copy(deep=True)
    out=attach_mm(pm.sample(frac=1,random_state=1),mm.sample(frac=1,random_state=2))
    pd.testing.assert_frame_equal(pm,before)
    assert (out.v4_workload_start_xmins==56.9).all()
    assert (out.control_xmins==46.8).all() and (out.goal_mu==.2).all()
    assert (out.mu_dc==3).all() and (out.v4_workload_start_p_start==.7).all()


@pytest.mark.parametrize('mutation',['cutoff','team_id','gw','pos','missing','duplicate','season'])
def test_bridge_rejects_mismatched_sources(mutation):
    pm,mm=inputs()
    if mutation=='missing':mm=mm.iloc[:-1]
    elif mutation=='duplicate':mm=pd.concat([mm,mm.iloc[:1]])
    elif mutation=='cutoff':mm['cutoff']='2026-01-17T10:00:00Z'
    elif mutation=='pos':mm.loc[1,'pos']='FWD'
    elif mutation=='season':mm['season']='2024-25'
    else:mm.loc[1,mutation]=99
    with pytest.raises(ValueError):attach_mm(pm,mm)


def test_hard_zero_minutes_reach_adapter_without_losing_conditional_role():
    pm,mm=inputs();mm.loc[0,['p','q','x']]=0
    out=attach_mm(pm,mm)
    assert out.loc[0,'v4_start_minutes_mean']==80
    assert out.loc[0,'v4_workload_start_xmins']==0
    assert out.loc[0,'v4_workload_start_p_start']==out.loc[0,'v4_p_cameo_given_bench']==0


def test_locked_PM_clipping_is_a_real_mean_mismatch_not_MC_noise():
    mean=float(locked_sampler_expectation(1.,0.,90.,15.))
    assert 86.0<mean<86.1  # Not 90 despite input mean90; preserve/report this.
    assert locked_sampler_expectation(0.,0.,90.,15.)==0
    cameo=float(locked_sampler_expectation(0.,1.,80.,60.))
    assert 44.8<cameo<45.  # Existing PM clips cameos at45, unlike B's support90.


def ts_fixture():
    now=datetime.now(timezone.utc);cut=now-timedelta(minutes=10)
    positions=[1]*2+[2]*5+[3]*5+[4]*3
    payload=dict(scope='prospective_preview',model='B_locked_PM_preview',locked_model_active=False,
        season='2026-27',gws=list(range(7,13)),data_asof=cut.isoformat(),
        freshness_limit_hours=24,origin_deadline=(now+timedelta(hours=2)).isoformat(),
        blockers=['SYNTHETIC REGRESSION FIXTURE — not a user forecast'],
        players=[dict(id=i+1,name='Synthetic '+str(i+1),team_id=i//3+1,position=pos,price_tenths=50,
            weeks=[dict(gw=gw,xpts=4.,p_play=1.,fixtures=[{}]) for gw in range(7,13)]) for i,pos in enumerate(positions)])
    manager=dict(season='2026-27',gw=7,source='SYNTHETIC REGRESSION FIXTURE',
        observed_at=(cut-timedelta(minutes=5)).isoformat(),bank_tenths=7,free_transfers=2,
        squad=[dict(id=i+1,purchase_price_tenths=48) for i in range(15)],
        chips_used={k:[] for k in ['wildcard','free_hit','bench_boost','triple_captain']})
    return seal_forecast(payload),manager


def test_real_locked_six_gw_TS_runs_on_preview_contract_without_changing_state():
    payload,manager=ts_fixture();before=copy.deepcopy(manager)
    result=run_current_ts(payload,manager,include_chips=False)
    assert manager==before
    assert len(result['plan']['path'])==6 and len(result['lineup'])==15
    assert result['plan']['weights']==(1.,.6,.36,.216,.1296,.07776)
    assert not result['locked_model_active']
    assert sum(r['role'] in ('XI','C','VC') for r in result['lineup'])==11


def test_current_TS_rejects_historical_incomplete_or_tampered_forecasts():
    payload,manager=ts_fixture()
    for change in [dict(scope='historical_replay'),dict(gws=[7]),dict(origin_deadline='2020-01-01T00:00:00Z')]:
        with pytest.raises(ValueError):run_current_ts(seal_forecast({**payload,**change}),manager)
    payload['players'][0]['weeks'][0]['xpts']=999
    with pytest.raises(ValueError,match='checksum'):run_current_ts(payload,manager)


def test_complete_B_PM_TS_entry_with_explicit_synthetic_six_GW_inputs():
    """Actual simulator/TS, no mocks; generated data never enters public output."""
    from run_mm_locked_preview import run_pipeline
    from research_individual_mm_refinement import NUM
    from scipy.special import logit
    now=datetime.now(timezone.utc);cut=now-timedelta(minutes=10)
    known=(cut-timedelta(days=1)).isoformat();clock=cut.isoformat()
    positions=['GK']*2+['DEF']*5+['MID']*5+['FWD']*4
    target=[];pm=[];elements=[]
    for team in range(1,7):
        for slot,pos in enumerate(positions):
            pid=(team-1)*16+slot+1
            elements.append(dict(id=pid,web_name='Synthetic '+str(pid),team=team,
                element_type={'GK':1,'DEF':2,'MID':3,'FWD':4}[pos],now_cost=50))
            for gw in range(7,13):
                fx=f'live-2026-27-fpl-{gw*100+(team-1)//2}'
                r=dict(season='2026-27',fixture_uuid=fx,player_uuid=str(pid),team_id=team,
                    pos=pos,gw=gw,cutoff=clock,p=.7,q=.2,s=80.,c=15.,x=56.9,
                    news_eligible=False,news_state='UNKNOWN',news_chance=np.nan,
                    news_effective_at=None,max_history_known_at=known,physical_last_known_at=known)
                for col in NUM:r[col]=0.
                r.update(logit_p=float(logit(.7)),logit_q=float(logit(.2)),normal_p=.7,stable_p=.7)
                target.append(r)
                pm.append(dict(**{k:r[k] for k in ['season','fixture_uuid','player_uuid','team_id','pos','gw','cutoff']},
                    fpl_element=pid,target_gw=gw,target_kickoff=(now+timedelta(days=1+7*(gw-7))).isoformat(),
                    home_team_id=team if team%2 else team-1,away_team_id=team+1 if team%2 else team,
                    lambda_home_goals=1.5,lambda_away_goals=1.2,assist_probability_per_goal=.7,
                    control_p_start=.7,control_xmins=56.9,p_cameo_given_bench=.2,
                    start_minutes_mean=80.,cameo_minutes_mean=15.,v4_workload_start_p_start=.7,
                    v4_workload_start_xmins=56.9,v4_p_cameo_given_bench=.2,
                    v4_start_minutes_mean=80.,v4_cameo_minutes_mean=15.,
                    goal_mu=.1,assist_mu=.07,mu_dc=3.,dc_alpha=.1,p_yellow=.05,p_red=.001,
                    lambda_saves=3. if pos=='GK' else 0.,lambda_pen=.1,pen_weight=1/16,
                    pen_conversion=.78,team_pen_conversion=.78,bg_mean_rate90=8.,bg_sd90=2.))
    target=pd.DataFrame(target);history=target.iloc[:300].copy()
    history['fixture_uuid']='SYNTHETIC-HISTORICAL-'+history.index.astype(str)
    history['known_at']=known;history['y']=history.index%2
    deadline=(now+timedelta(hours=4)).isoformat()
    bootstrap=dict(elements=elements,teams=[dict(id=i,name='Synthetic club '+str(i)) for i in range(1,7)],
        events=[dict(id=7,is_next=True,deadline_time=deadline)])
    fixtures=[dict(id=gw*100+pair,event=gw,team_h=pair*2+1,team_a=pair*2+2,started=False,
        kickoff_time=(now+timedelta(days=1+7*(gw-7))).isoformat()) for gw in range(7,13) for pair in range(3)]
    provenance=dict(data_at=clock,origin_deadline=deadline,source_manifest_sha256='0'*64,
        upstream_variant='role_chance_return_duration',features=NUM,source_workflow='SYNTHETIC REGRESSION ONLY')
    import hashlib,json
    for name,obj in [('bootstrap',bootstrap),('fixtures',fixtures)]:
        provenance[name+'_sha256']=hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        provenance[name+'_observed_at']=known
    roles=pd.DataFrame(columns=['season','team_id','fixture_uuid','player_uuid','final_role','formation','kickoff'])
    squad=[1,17,3,19,35,51,67,40,56,72,88,8,29,45,93]
    manager=dict(season='2026-27',gw=7,source='SYNTHETIC REGRESSION ONLY',observed_at=known,
        bank_tenths=7,free_transfers=2,squad=[dict(id=i,purchase_price_tenths=50) for i in squad],
        chips_used=dict(wildcard=[1],free_hit=[2],bench_boost=[3],triple_captain=[4]))
    before=copy.deepcopy(manager)
    doc,forecast,plan,audit=run_pipeline(history,target,roles,provenance,pd.DataFrame(pm),bootstrap,
        dict(verified_player_match_rows=0,quarantined_rows=0,missing_fields=[]),manager,fixtures=fixtures)
    assert manager==before and len(doc['players'])==576
    assert len(forecast['players'])==96 and forecast['gws']==list(range(7,13))
    assert len(plan['plan']['path'])==6 and len(plan['lineup'])==15
    assert plan['forecast_sha256']==forecast['forecast_sha256']
    assert forecast['model']=='B_locked_PM_preview' and not forecast['locked_model_active']
    assert audit['point_components_reconciled']
    assert not audit['MM_to_PM_mean_consistent']
    assert any('rounded/clipped' in b for b in forecast['blockers'])
    from mm_candidate_forecast import seal_document
    assert seal_document(doc)['content_sha256']==doc['content_sha256']
    assert all(p['name'].startswith('Synthetic ') and p['club'].startswith('Synthetic club') for p in doc['players'])
    assert 'scripts/run_mm_locked_preview.py' in doc['code_sha256']
