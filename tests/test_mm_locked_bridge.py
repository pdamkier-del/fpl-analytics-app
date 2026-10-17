"""Synthetic adapter regressions, never personal recommendations."""
import copy
from datetime import datetime,timezone,timedelta
from dataclasses import asdict
import numpy as np
import pandas as pd
import pytest
from mm_locked_bridge import attach_mm,run_current_ts
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
