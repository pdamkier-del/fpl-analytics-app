#!/usr/bin/env python3
"""Replay current one-match/GW stages with full-horizon seeds; test original TS."""
from pathlib import Path
import copy,json,hashlib
import pandas as pd
from gk_joint_bridge import observations
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from run_joint_gk_preview import run,ROOT,write
from run_live_locked_ts import run as run_ts,CHIPS

def main(source=None,inputs=None):
    source=Path(source)if source else ROOT/'work/joint-gk-current';inputs=Path(inputs)if inputs else ROOT/'work/current-B-inputs'
    payload=json.loads((source/'forecast.json').read_text())
    from b_chain_contract import VERSION,validate_forecast
    unified=payload['model']==VERSION
    if unified:validate_forecast(payload)
    h=pd.read_csv(inputs/'history.csv.gz',low_memory=False);t=pd.read_csv(inputs/'target.csv.gz',low_memory=False);prov=json.loads((inputs/'provenance.json').read_text())
    from gk_solo_role import mark_horizon_absences
    pred,_=infer_B(h,t,prov);pred=mark_horizon_absences(pred,json.loads((inputs/'bootstrap.json').read_text()));frame=attach_mm(pd.read_csv(inputs/'pm.csv.gz',low_memory=False),pred);offsets={fx:i for i,fx in enumerate(sorted(frame.fixture_uuid.unique()))}
    origin=frame.gw.min();first=frame[frame.gw.eq(origin)].sort_values(['target_kickoff','fixture_uuid']).iloc[0].fixture_uuid
    expected={(x['fixture_uuid'],p['player_uuid']):x for p in payload['players']for w in p['weeks']for x in w['fixtures']}
    evidence=payload['official_gk_evidence'];partial=(evidence['team_id'],)if evidence['unlisted_competitors']else()
    from gk_solo_role import load_policy
    policy=load_policy(ROOT,h)
    stages=[];obs=observations(ROOT)
    for scope,mask in [('one-match',frame.fixture_uuid.eq(first)),('one-gw',frame.gw.eq(origin))]:
        chosen=frame[mask];p=pred[pred.fixture_uuid.isin(chosen.fixture_uuid)]
        catalogue={r.player_uuid:next(p for p in json.loads((inputs/'bootstrap.json').read_text())['elements']if p['id']==int(r.fpl_element))for r in chosen.itertuples()}if unified else None
        xp,_,audit,_=run(chosen,p,obs,season='2026-27',incomplete_teams=partial,offsets=offsets,role_policy=policy,distributions=True,chain=unified,catalogue=catalogue)
        for r in xp.itertuples():
            old=expected[(r.fixture_uuid,r.player_uuid)]
            if r.distribution!=old['distribution']:raise ValueError('PM distributions differ across scopes')
            if abs(r.xpts_fixture-old['xpts'])>1e-10 or abs(r.expected_minutes-old['simulated_minutes'])>1e-10:raise ValueError('Stage differs from six-GW computation')
        stages.append(dict(scope=scope,fixtures=chosen.fixture_uuid.nunique(),rows=len(xp),exact_full_horizon_comparison=True,all_gk_team_minutes_90=True))
        print('Validated',scope,flush=True)
    write(source/'stage-validation.json',dict(passed=True,stages=stages,six_gw_fixtures=payload['fixtures']))
    # Reuse the repository's explicit regression-fixture construction. It is
    # never sent to the public app and is not claimed to be the user's squad.
    clubs={};picked=[]
    for pos,count in [(1,2),(2,5),(3,5),(4,3)]:
        for p in sorted([p for p in payload['players']if p['position']==pos],key=lambda p:(p['price_tenths'],p['id'])):
            if clubs.get(p['team_id'],0)>=3:continue
            picked.append(p);clubs[p['team_id']]=clubs.get(p['team_id'],0)+1;count-=1
            if not count:break
        if count:raise ValueError('Cannot construct the legal TS regression fixture')
    state=dict(season=payload['season'],gw=min(payload['gws']),source='SYNTHETIC_REGRESSION_FIXTURE_NOT_USER_TEAM',validation_only=True,
        observed_at=payload['data_asof'],bank_tenths=1000-sum(p['price_tenths']for p in picked),free_transfers=2,
        squad=[dict(id=p['id'],purchase_price_tenths=p['price_tenths'])for p in picked],chips_used={c:[]for c in CHIPS})
    original=copy.deepcopy(state)
    if unified:
        from service.preview_manager_job import calculate
        result=calculate(payload,state)
    else:result=run_ts(payload,state,include_chips=False)
    if state!=original or not result['ts_ran'] or len(result['plan']['path'])!=len(payload['gws']):raise ValueError('Original TS chain failed or mutated manager state')
    # Public receipt contains no squad, plan, transfers or manager-state hash.
    write(source/'ts-validation.json',dict(ts_ran=True,horizon_gws=len(payload['gws']),validation_only=True,
        actual_user_plan=False,manager_state_unchanged=True,chips_ran=False,ts_code_unchanged=not unified,
        chain_version=payload['model'],forecast_sha256=payload['forecast_sha256'],
        note='Original TS exercised on actual forecast with an explicit synthetic legal regression state; no personal recommendation published.'))
    print('Original TS complete six-GW regression passed',flush=True)
if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);ap.add_argument('--inputs',type=Path);args=ap.parse_args()
    main(args.source,args.inputs)
