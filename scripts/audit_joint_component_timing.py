"""Audit original sequential component state ordering against frozen GW cutoffs.

Counts structural exposure; does not regenerate or fit any forecast.
Postdeadline kickoff exposure is a conservative lower bound on unavailable
results, since even some earlier kickoffs can still be in progress at cutoff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',type=Path,default=ROOT/'work/core.sqlite3')
    ap.add_argument('--archives',type=Path,default=ROOT.parent/'recovery-inputs')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/joint-component-timing-audit-v1')
    a=ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Use a new immutable audit directory')
    # Verify the exact original experiment sources before interpreting their ordering.
    evidence=json.loads((ROOT/'analysis/results/joint-cold-start-audit-v1/original-rule-evidence.json').read_text())
    source_bytes=[];source_info=[]
    for row in evidence['sources'][:3]:
        archive=a.archives/row['archive']
        if archive.exists():
            if digest(archive.read_bytes())!=row['archive_sha256']:
                raise ValueError('Original archive changed')
            with zipfile.ZipFile(archive) as z:
                raw=z.read(row['member'])
        else:
            preserved=ROOT/'analysis/results/joint-component-timing-audit-v1'/Path(row['member']).name
            raw=preserved.read_bytes()
        if digest(raw)!=row['member_sha256']:
            raise ValueError('Original experiment changed')
        source_bytes.append((Path(row['member']).name,raw))
        source_info.append(dict(row, preserved_source=Path(row['member']).name))
    bpath=ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    vpath=ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    b=pd.read_csv(bpath);b=b[b.gw>=22][['fixture_uuid','player_uuid','gw','team_id']]
    v=pd.read_csv(vpath)[['fixture_uuid','player_uuid','cutoff']]
    b=b.merge(v,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    con=sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro',uri=True)
    h=pd.read_sql_query("SELECT DISTINCT fixture_uuid,player_uuid,team_id,kickoff_at FROM player_fixture_observations WHERE season='2025-26'",con)
    con.close()
    times=h[['fixture_uuid','kickoff_at']].drop_duplicates()
    if times.fixture_uuid.duplicated().any():
        raise ValueError('Conflicting fixture times')
    b=b.merge(times,on='fixture_uuid',validate='many_to_one')
    b['target_time']=pd.to_datetime(b.kickoff_at,utc=True)
    b['deadline']=pd.to_datetime(b.cutoff,utc=True)
    times['time']=pd.to_datetime(times.kickoff_at,utc=True)
    fixture_rows=[]
    for r in b[['fixture_uuid','gw','cutoff','kickoff_at','target_time','deadline']].drop_duplicates().itertuples(index=False):
        earlier=(times.time<r.target_time)|((times.time==r.target_time)&(times.fixture_uuid<r.fixture_uuid))
        late=times[earlier & (times.time>=r.deadline)]
        fixture_rows.append(dict(fixture_uuid=r.fixture_uuid,gw=r.gw,cutoff=r.cutoff,kickoff_at=r.kickoff_at,
            postdeadline_fixtures_in_original_league_state=len(late),
            latest_unavailable_source_kickoff=late.kickoff_at.max() if len(late) else None))
    fixtures=pd.DataFrame(fixture_rows).sort_values(['gw','kickoff_at','fixture_uuid'])
    # Player-local updates matter particularly for a second DGW fixture.
    joined=b.merge(h[['player_uuid','fixture_uuid','kickoff_at']],on='player_uuid',suffixes=('','_history'),validate='many_to_many')
    ht=pd.to_datetime(joined.kickoff_at_history,utc=True)
    earlier=(ht<joined.target_time)|((ht==joined.target_time)&(joined.fixture_uuid_history<joined.fixture_uuid))
    late=joined[earlier & (ht>=joined.deadline)]
    counts=late.groupby(['fixture_uuid','player_uuid']).size().rename('postdeadline_player_fixtures_in_original_state')
    player_rows=b.drop(columns=['target_time','deadline']).merge(counts,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    player_rows['postdeadline_player_fixtures_in_original_state']=player_rows.postdeadline_player_fixtures_in_original_state.fillna(0).astype(int)
    affected=player_rows[player_rows.postdeadline_player_fixtures_in_original_state>0]
    a.out.mkdir(parents=True)
    for name,raw in source_bytes:
        (a.out/name).write_bytes(raw)
    outputs=[]
    for name,frame in [('fixture_timing',fixtures),('player_history_after_deadline',affected)]:
        path=a.out/(name+'.csv');frame.to_csv(path,index=False,lineterminator='\n')
        outputs.append(dict(path=path.name,rows=len(frame),sha256=digest(path.read_bytes())))
    result=dict(parent_checkpoint='33f99cf4205e4853f9e8a31af91651310d95476b',
        classification='structural_timing_audit_not_new_holdout',season='2025-26',
        fixtures=len(fixtures),control_rows=len(b),
        fixtures_with_postdeadline_league_state=int((fixtures.postdeadline_fixtures_in_original_league_state>0).sum()),
        player_rows_with_postdeadline_player_history=len(affected),
        fixtures_with_postdeadline_player_history=int(affected.fixture_uuid.nunique()),
        max_postdeadline_league_fixtures=int(fixtures.postdeadline_fixtures_in_original_league_state.max()),
        original_experiment_sources=source_info,outputs=outputs,
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for p in
            [bpath,vpath,ROOT/'analysis/results/joint-cold-start-audit-v1/original-rule-evidence.json',Path(__file__)]],
        database_sha256=digest(a.db.read_bytes()),deadline_replay_component_inputs_ready=False,
        findings=[
            'Original attack position/assist priors and discipline position priors update after each fixture in kickoff/fixture-ID order.',
            'Those sequential states can contain results from fixtures after the common GW cutoff, including other fixtures starting simultaneously.',
            'DC population/opponent states and team-goal contexts are also fixture-sequential; exact numerical forecast reproduction is not claimed here.',
            'A first-entry extension must use a common predeadline population snapshot, not merely fill the archived omissions.',
            'Counts are structural exposure from original ordering, not an estimate of the numerical impact on MAE/RMSE.',
            'The old paired comparison remains a reused mechanistic diagnostic; it is not a certified deadline-safe decision backtest.'],
        required='Generate a separately versioned deadline-batched common component input using frozen parameters and completed predeadline history; resolve remaining roster evidence before full replay.',
        unchanged='Original adapter/simulator, frozen component forecasts, paired diagnostic, Core database and transfer/chip policy')
    (a.out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['fixtures','fixtures_with_postdeadline_league_state','player_rows_with_postdeadline_player_history','fixtures_with_postdeadline_player_history','deadline_replay_component_inputs_ready']},indent=2))


if __name__=='__main__':
    main()
