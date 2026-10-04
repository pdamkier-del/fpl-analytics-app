"""Audit origin/target coverage without relabelling future forecasts as past."""
import argparse,hashlib,json
from pathlib import Path
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/season-replay-coverage-v1')
    a=ap.parse_args()
    if a.out.exists():raise FileExistsError('Use a new immutable output directory')
    bp=ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    vp=ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    b=pd.read_csv(bp,usecols=['gw']);v=pd.read_csv(vp,usecols=['gw','cutoff'])
    events=read_frozen_table(ROOT/'analysis/results/joint-deadline-snapshots-v1','events')
    revisions=events.groupby('event_id').deadline_time.nunique()
    # Latest recovered metadata is an audit calendar, not a historical as-of
    # schedule. Earlier snapshots legitimately contain revised future deadlines.
    deadline=events.sort_values('observed_at').drop_duplicates('event_id',keep='last')
    dates=dict(zip(deadline.event_id.astype(int),pd.to_datetime(deadline.deadline_time,utc=True)))
    if set(dates)!=set(range(1,39)):raise ValueError('Need all official season deadlines')
    inverse={d:gw for gw,d in dates.items()}
    origins=pd.to_datetime(v.cutoff,utc=True).map(inverse)
    if origins.isna().any():raise ValueError('Forecast cutoff not an official deadline')
    cells=set(zip(origins.astype(int),v.gw.astype(int)))
    joint=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','inputs')
    blocked=read_frozen_table(ROOT/'analysis/results/deadline-player-components-v1','blocked_roster')
    states=read_frozen_table(ROOT/'analysis/results/joint-deadline-snapshots-v1','states')
    rows=[]
    for gw in range(1,39):
        required=set(range(gw,min(38,gw+5)+1))
        observed={target for origin,target in cells if origin==gw}
        rows.append(dict(gw=gw,deadline=dates[gw].isoformat(),control_target_gw_present=gw in set(b.gw),
            v4_origin_present=any(origin==gw for origin,_ in cells),
            required_six_gw_window=';'.join(map(str,sorted(required))),
            stored_target_gws_at_origin=';'.join(map(str,sorted(observed))),
            missing_target_gws_at_origin=';'.join(map(str,sorted(required-observed))),
            missing_origin_target_cells=len(required-observed),
            joint_complete_cohort_fixtures=int(joint[joint.gw==gw].fixture_uuid.nunique()),
            unresolved_roster_rows=int((blocked.gw==gw).sum()),
            predeadline_price_snapshot_present=bool((states.gw==gw).any())))
    coverage=pd.DataFrame(rows)
    assert len(coverage)==38 and not coverage.gw.duplicated().any()
    assert cells=={(gw,gw) for gw in range(22,39)}
    assert coverage.missing_origin_target_cells.sum()==196
    required_count=sum(min(6,39-gw) for gw in range(1,39))
    a.out.mkdir(parents=True);coverage.to_csv(a.out/'deadline_coverage.csv',index=False)
    gates=[dict(id='roster',kind='data',ready=False,detail='32 original rows / 26 fixtures lack verified predeadline listing/team/position evidence; retain bounded 144-fixture cohort'),
        dict(id='forecasts',kind='data/model_generation',ready=False,detail='V4 origin coverage only GW22-38, all 17 origin/target pairs diagonal; GW1-21 origins and 196 of 213 required six-GW origin/target cells absent'),
        dict(id='historical_prices',kind='data',ready=False,detail='Recovered verified predeadline price snapshots cover GW22-38; GW1-21 snapshots not yet recovered'),
        dict(id='mechanics',kind='integration',ready=False,unit_tests_ready=True,detail='125 suite tests pass; opt-in 2025/26 FT/chip accounting is not yet applied by archived season orchestration'),
        dict(id='scoring',kind='data/model_integration',ready=False,detail='Original simulator uses inherited 2026/27 BPS on 2025/26; historical exact bonus event coverage is incomplete; preserved diagnostic is bonus-neutral'),
        dict(id='schedule',kind='data/integration',ready=False,detail='Past official event deadlines recovered, but future BGW/DGW schedules must be evidenced as known at each origin, not taken from final season fixtures')]
    manifest=dict(parent_checkpoint='aab3a841346f28ba97552b17e96b8529094816b0',classification='replay_readiness_audit_not_new_holdout',
        full_season_ready=False,bounded_paired_diagnostic_complete=True,required_horizon_gameweeks=6,
        required_origin_target_cells=required_count,present_origin_target_cells=len(cells),missing_origin_target_cells=int(coverage.missing_origin_target_cells.sum()),
        missing_v4_origins=coverage.loc[~coverage.v4_origin_present,'gw'].tolist(),missing_control_targets=coverage.loc[~coverage.control_target_gw_present,'gw'].tolist(),
        missing_verified_price_snapshots=coverage.loc[~coverage.predeadline_price_snapshot_present,'gw'].tolist(),gates=gates,
        recovered_deadline_revision_events=revisions[revisions>1].index.astype(int).tolist(),
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [bp,vp,ROOT/'analysis/results/deadline-joint-inputs-v1/manifest.json',ROOT/'analysis/results/joint-deadline-snapshots-v1/manifest.json',ROOT/'analysis/results/season-2025-26-mechanics-v1/verification.json',Path(__file__)]],
        output_sha256=hashlib.sha256((a.out/'deadline_coverage.csv').read_bytes()).hexdigest(),
        interpretation='Presence means a stored coverage cell only, not full roster readiness. Required horizon matches existing six-GW forecast/decision visibility. Later-cutoff forecasts cannot fill earlier-origin cells.',
        unchanged='Core, all forecasts/results, original adapter/simulator/scoring and transfer/chip strategy')
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:manifest[k] for k in ['full_season_ready','required_origin_target_cells','present_origin_target_cells','missing_origin_target_cells','missing_v4_origins','missing_control_targets']},indent=2))
if __name__=='__main__':main()
