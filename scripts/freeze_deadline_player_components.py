"""Freeze a common deadline player-component experiment with explicit blocked rows.

No fitting or target evaluation. Original forecast files and Core are read-only.
Historical outcome availability uses a declared kickoff+3h guard, not fabricated
authoritative publication timestamps. Its minimum margin is reported.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from fpl_v1_1_model.deadline_components import player_components_at_deadline
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',type=Path,default=ROOT/'work/core.sqlite3')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/deadline-player-components-v1')
    a=ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Use a new immutable component output directory')
    p=ROOT/'analysis/results/joint-component-recovery-v1'
    parameter_paths=[p/'player_attack_fit.json',p/'defcon_fit.json',p/'negative_events_fit.json']
    parameters=dict(attack=json.loads(parameter_paths[0].read_text()),
        dc=json.loads(parameter_paths[1].read_text())['selected'],
        discipline=json.loads(parameter_paths[2].read_text())['recommended_for_joint_model'])
    bpath=ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    vpath=ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    b=pd.read_csv(bpath,usecols=['gw','fixture_uuid','player_uuid','team_id','pos','expected_minutes_v2'])
    b=b[b.gw>=22].rename(columns={'expected_minutes_v2':'expected_minutes'})
    v=pd.read_csv(vpath,usecols=['fixture_uuid','player_uuid','cutoff'])
    b=b.merge(v,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    state_path=ROOT/'analysis/results/joint-deadline-snapshots-v1'
    state=read_frozen_table(state_path,'states')
    b=b.merge(state[['gw','player_uuid','team_id','position','observed_at']],on=['gw','player_uuid'],
        how='left',validate='many_to_one',suffixes=('','_snapshot'))
    valid=b.observed_at.notna() & (b.team_id==b.team_id_snapshot) & (b.pos==b.position)
    blocked=b[~valid].copy();blocked['reason']='Missing matching predeadline FPL team/position evidence'
    r=b[valid].copy().rename(columns={'observed_at':'evidence_at'})
    con=sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro',uri=True)
    fixtures=pd.read_sql_query("SELECT fixture_uuid,home_team_id,away_team_id FROM fixtures WHERE season='2025-26'",con)
    r=r.merge(fixtures,on='fixture_uuid',validate='many_to_one')
    if not ((r.team_id==r.home_team_id)|(r.team_id==r.away_team_id)).all():
        raise ValueError('Roster team differs from fixture')
    r['opponent_team_id']=np.where(r.team_id==r.home_team_id,r.away_team_id,r.home_team_id)
    result=[];history_summary=[]
    fields=['minutes','xg','xa','defcon_count','yellow_cards','fpl_red_cards']
    for (gw,cutoff),group in r.groupby(['gw','cutoff'],sort=True):
        h=pd.read_sql_query('''SELECT season,fixture_uuid,player_uuid,team_id,opponent_team_id,
            kickoff_at,fpl_position,minutes,xg,xa,defcon_count,yellow_cards,fpl_red_cards
            FROM player_fixture_observations WHERE season='2025-26'
            AND julianday(kickoff_at)+3.0/24.0<=julianday(?)''',con,params=[cutoff])
        keys=['fixture_uuid','player_uuid']
        if h.groupby(keys)[fields+['team_id','opponent_team_id','kickoff_at','fpl_position']].nunique(dropna=False).max().max()>1:
            raise ValueError('Conflicting logical historical observations')
        h=h.drop_duplicates(keys)
        h['available_at']=pd.to_datetime(h.kickoff_at,utc=True)+pd.Timedelta(hours=3)
        x=player_components_at_deadline(h,group,cutoff,**parameters)
        x=x.merge(group[['fixture_uuid','player_uuid','gw','team_id','pos','expected_minutes','evidence_at']],
            on=keys,validate='one_to_one')
        result.append(x)
        latest=pd.to_datetime(h.kickoff_at,utc=True).max()
        history_summary.append(dict(gw=int(gw),cutoff=cutoff,history_rows=len(h),
            history_fixtures=int(h.fixture_uuid.nunique()),latest_source_kickoff=latest.isoformat(),
            latest_guard_available_at=h.available_at.max().isoformat(),
            minimum_kickoff_to_cutoff_hours=(pd.Timestamp(cutoff)-latest).total_seconds()/3600))
        print(json.dumps(dict(gw=int(gw),forecast_rows=len(x),cold_starts=int(x.cold_start.sum()))),flush=True)
    con.close()
    all_components=pd.concat(result,ignore_index=True).sort_values(['gw','fixture_uuid','player_uuid'])
    a.out.mkdir(parents=True)
    outputs=[]
    for name,frame in [('components',all_components),('blocked_roster',blocked),('history_summary',pd.DataFrame(history_summary))]:
        raw=frame.to_csv(index=False,lineterminator='\n').encode();packed=gzip.compress(raw,mtime=0);parts=[]
        for i,start in enumerate(range(0,len(packed),32768)):
            data=packed[start:start+32768];path=f'{name}.csv.gz.part-{i:04d}'
            (a.out/path).write_bytes(data);parts.append(dict(path=path,bytes=len(data),sha256=sha(data)))
        outputs.append(dict(name=name,rows=len(frame),uncompressed_sha256=sha(raw),compressed_sha256=sha(packed),parts=parts))
    paths=parameter_paths+[bpath,vpath,state_path/'manifest.json',ROOT/'src/fpl_v1_1_model/deadline_components.py',Path(__file__)]
    manifest=dict(parent_checkpoint='229784dc6f1670cceb3c5dca39a1bdff6f09400e',
        classification='reused_diagnostic_player_input_experiment',season='2025-26',
        common_player_component_rows=len(all_components),verified_first_entry_rows=int(all_components.cold_start.sum()),
        blocked_roster_rows=len(blocked),blocked_fixtures=int(blocked.fixture_uuid.nunique()),
        target_evaluation_performed=False,parameters_refit=False,full_roster_replay_ready=False,
        full_season_replay_ready=False,team_goal_keeper_inputs_rebuilt=False,
        source_history_availability=dict(method='explicit conservative kickoff+3h outcome-availability guard',
            authoritative_publication_timestamps=False,
            minimum_prior_kickoff_to_cutoff_hours=min(x['minimum_kickoff_to_cutoff_hours'] for x in history_summary)),
        outputs=outputs,sources=[dict(path=str(path.relative_to(ROOT)),sha256=sha(path.read_bytes())) for path in paths],
        database_sha256=sha(a.db.read_bytes()),
        contract='Only matching predeadline snapshot team/position rows forecast. Blocked rows preserved explicitly; no silent partial team replay. Same player rates for both minute arms.',
        unchanged='Original adapter/simulator, Core, old forecasts/paired results, transfer/chip strategy')
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:manifest[k] for k in ['common_player_component_rows','verified_first_entry_rows','blocked_roster_rows','blocked_fixtures','source_history_availability']},indent=2))


if __name__=='__main__':
    main()
