"""Verify frozen common inputs and minute-only paired contracts before replay."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import build_pair, read_frozen_table

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'analysis/results/deadline-joint-inputs-v1'
    m=json.loads((folder/'manifest.json').read_text());checks=0
    for source in m['sources']:
        assert hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest()==source['sha256'],source['path']
        checks+=1
    tables={o['name']:read_frozen_table(folder,o['name']) for o in m['outputs']}
    checks+=sum(len(o['parts'])+2 for o in m['outputs'])
    f=tables['inputs'];excluded=tables['excluded_fixtures'];keys=['fixture_uuid','player_uuid']
    b=pd.read_csv(ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv')
    b=b[b.gw>=22].rename(columns={'p_start_v2':'control_p_start','expected_minutes_v2':'control_xmins'})
    union=pd.concat([f[keys],excluded[keys],tables['low_exposure_exclusions'][keys]])
    assert not union.duplicated().any()
    assert union.merge(b[keys],on=keys,how='outer',indicator=True)._merge.eq('both').all()
    blocked=read_frozen_table(ROOT/'analysis/results/deadline-player-components-v1','blocked_roster')
    assert set(excluded.fixture_uuid)==set(blocked.fixture_uuid)
    assert not set(f.fixture_uuid)&set(excluded.fixture_uuid)
    merged=f.merge(b,on=keys,suffixes=('','_original'),validate='one_to_one')
    for col in ['control_p_start','control_xmins','start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench']:
        assert np.allclose(merged[col],merged[col+'_original'],rtol=0,atol=1e-12),col
    v=pd.read_csv(ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz')
    merged=f.merge(v,on=keys,suffixes=('','_original'),validate='one_to_one')
    for col in ['workload_start_p_start','workload_start_xmins','start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench']:
        original=col+'_original' if col in f.columns else col
        assert np.allclose(merged['v4_'+col],merged[original],rtol=0,atol=1e-12),col
    checks+=14
    allowed={'p_start','p_cameo_given_bench','start_minutes_mean','cameo_minutes_mean'}
    for _,g in f.groupby('fixture_uuid'):
        control,candidate=build_pair(g)
        ca=asdict(control);va=asdict(candidate)
        cp=ca.pop('players');vp=va.pop('players');assert ca==va
        for x,y in zip(cp,vp):
            assert {k:z for k,z in x.items() if k not in allowed}=={k:z for k,z in y.items() if k not in allowed}
        for team,t in g.groupby('team_id'):
            lam=t.lambda_home_goals.iloc[0] if team==t.home_team_id.iloc[0] else t.lambda_away_goals.iloc[0]
            assert np.isclose(t.goal_mu.sum(),lam,rtol=0,atol=1e-10)
            assert np.isclose(t.assist_mu.sum(),lam*t.assist_probability_per_goal.iloc[0],rtol=0,atol=1e-10)
            assert t.lambda_saves.nunique()==1
        checks+=1+len(cp)+6
    timing=tables['team_keeper_timing']
    assert timing.unavailable_latent_source_rows.eq(0).all()
    assert (pd.to_datetime(timing.latest_keeper_guard_available_at,utc=True)<=pd.to_datetime(timing.cutoff,utc=True)).all()
    assert len(tables['targets'])==len(f) and not tables['targets'][keys].duplicated().any()
    checks+=3
    report=dict(integrity_passed=True,checks=checks,paired_fixtures=int(f.fixture_uuid.nunique()),paired_rows=len(f),
        complete_fixture_paired_replay_technically_ready=True,full_roster_period_ready=False,full_season_replay_ready=False,
        unverified_roster_rows=len(blocked),excluded_whole_fixtures=int(excluded.fixture_uuid.nunique()),
        classification=m['classification'],history_availability=m['availability'])
    (folder/'verification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
