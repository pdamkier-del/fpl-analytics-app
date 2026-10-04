"""Verify legacy recovery and quantify why it cannot fill v4 forecast gaps."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'analysis/results/legacy-rolling-recovery-v1';m=json.loads((out/'manifest.json').read_text());checks=0
    tables={x['name']:read_frozen_table(out,x['name']) for x in m['outputs']}
    checks+=sum(len(x['parts'])+2 for x in m['outputs'])
    digests={x['name']:x['uncompressed_sha256'] for x in m['outputs']}
    for x in m['members']:
        actual=digests[x['installed']] if x['installed'] in digests else hashlib.sha256((out/x['installed']).read_bytes()).hexdigest()
        assert actual==x['sha256'];checks+=1
    assert hashlib.sha256((ROOT/'scripts/recover_legacy_rolling_forecasts.py').read_bytes()).hexdigest()==m['code_sha256'];checks+=1
    f=tables['player_gw_forecasts'];raw=tables['fixture_forecasts'];audit=tables['original_cutoff_audit']
    keys=['origin_gw','decision_gw','gw','id']
    assert not f[keys].duplicated().any() and not raw[keys+['fixture_uuid']].duplicated().any()
    assert f.decision_gw.eq(f.origin_gw+1).all() and raw.decision_gw.eq(raw.origin_gw+1).all()
    expected={(g,t) for g in range(1,39) for t in range(g,min(38,g+5)+1)}
    assert set(zip(f.decision_gw,f.gw))==expected
    assert f.gw.ge(f.decision_gw).all() and f.gw.le(f.decision_gw+5).all()
    assert np.isfinite(f[['xpts_mean','p_play']].to_numpy()).all()
    assert f.p_play.between(0,1).all() and raw.p_play_fixture.between(0,1).all()
    checks+=6
    grouped=raw.groupby(keys).agg(xpts_fixture=('xpts_fixture','sum'),fixture_count=('fixture_uuid','nunique'),p_no_play=('p_play_fixture',lambda p:float(np.prod(1-p))))
    joined=f.merge(grouped.reset_index(),on=keys,validate='one_to_one')
    assert len(joined)==len(f)
    assert np.allclose(joined.xpts_mean,joined.xpts_fixture,rtol=0,atol=1e-10)
    assert joined.fixtures.eq(joined.fixture_count).all()
    assert np.allclose(joined.p_play,1-joined.p_no_play,rtol=0,atol=1e-12)
    checks+=4
    assert set(audit.origin_gw)==set(range(1,39)) and not audit.origin_gw.duplicated().any();checks+=1
    blocked=read_frozen_table(ROOT/'analysis/results/deadline-player-components-v1','blocked_roster')
    named=pd.read_csv(ROOT/'analysis/results/blocked-roster-bracket-v1/blocked_rows.csv')
    exposure=blocked[['fixture_uuid','player_uuid','gw','cutoff']].merge(named[['fixture_uuid','player_uuid','fpl_element_id','canonical_name']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
    own=f[f.gw==f.decision_gw][['decision_gw','id','xpts_mean','p_play']]
    exposure=exposure.merge(own,left_on=['gw','fpl_element_id'],right_on=['decision_gw','id'],how='left',validate='many_to_one')
    exposure['legacy_current_gw_forecast_present']=exposure.id.notna()
    exposure.to_csv(out/'unverified_roster_exposure.csv',index=False)
    events=read_frozen_table(ROOT/'analysis/results/joint-deadline-snapshots-v1','events').sort_values('observed_at').drop_duplicates('event_id',keep='last')
    comparison=audit.merge(events[['event_id','deadline_time']],left_on='origin_gw',right_on='event_id',validate='one_to_one')
    mismatch=pd.to_datetime(comparison.deadline,utc=True)!=pd.to_datetime(comparison.deadline_time,utc=True)
    comparison['estimated_deadline_matches_recovered_calendar']=~mismatch
    comparison.to_csv(out/'estimated_deadline_comparison.csv',index=False)
    policy=json.loads((ROOT/'analysis/results/season-2025-26-mechanics-v1/verification.json').read_text())['policy_checks']
    for x in policy:assert hashlib.sha256((ROOT/x['path']).read_bytes()).hexdigest()==x['sha256'];checks+=1
    old=ROOT/'analysis/results/deadline-joint-paired-diagnostic-v1'
    read_frozen_table(old,'predictions');checks+=1
    report=dict(integrity_passed=True,checks=checks,player_gw_rows=len(f),fixture_rows=len(raw),
        origins=int(f.decision_gw.nunique()),legacy_origin_target_cells=len(expected),
        v4_origin_target_cells_recovered=0,unverified_roster_rows_with_legacy_forecasts=int(exposure.legacy_current_gw_forecast_present.sum()),
        estimated_deadline_mismatches=int(mismatch.sum()),full_season_ready=False,forecast_inputs_promoted=False,
        derived_outputs=[dict(path=p,sha256=hashlib.sha256((out/p).read_bytes()).hexdigest()) for p in ['unverified_roster_exposure.csv','estimated_deadline_comparison.csv']],policy_checks=policy,
        original_paired_predictions_checksum_verified=True,classification=m['classification'])
    (out/'verification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
