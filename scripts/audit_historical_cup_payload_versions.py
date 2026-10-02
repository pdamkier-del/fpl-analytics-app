#!/usr/bin/env python3
"""Compare saved original cup player payloads with the quarantined latest IDs."""
from pathlib import Path
import pandas as pd
from build_reproducible_role_benchmark import ROOT,write_json,sha
from recover_historical_cup_workload import start_labels


def main():
    recovery=ROOT/'analysis/results/historical-cup-recovery-v1/restored_team_games.csv'
    games=pd.read_csv(recovery)
    paths=sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/playermatchstats.csv'))
    current=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
    raw=ROOT/'data_v1_1/raw/all-competitions-2025-26'
    lineup_paths=sorted(raw.glob('GW*/lineups.csv'))
    lines=pd.concat([pd.read_csv(p) for p in lineup_paths],ignore_index=True)
    resolution=ROOT/'analysis/results/workload-quality-v3/exact_identity_resolutions.csv'
    resolved=pd.read_csv(resolution).rename(columns={'resolved_fpl_id':'resolved_id'})
    lines=lines.merge(resolved[['match_id','team_code','player_name','resolved_id']],
      on=['match_id','team_code','player_name'],how='left',validate='many_to_one')
    lines['player_id']=lines.player_id.fillna(lines.resolved_id)
    assert not current.duplicated(['match_id','player_id']).any()
    rows=[];summary=[];original_paths=[]
    for game in games.itertuples():
        path=ROOT/game.stats_path;original_paths.append(path)
        old=pd.read_csv(path);old=old[old.match_id==game.source_match_id]
        new=current[current.match_id==game.source_match_id]
        labels,clear=start_labels(old)
        old=old.copy();old['started_original']=labels
        latest=lines[(lines.match_id==game.source_match_id)&lines.player_id.notna()][['player_id','is_starting']].copy()
        assert not latest.player_id.duplicated().any()
        diff=old[['player_id','minutes_played','goals']].merge(new[['player_id','minutes_played','goals']],
          on='player_id',how='outer',suffixes=('_original','_current'),indicator=True)
        diff['source_match_id']=game.source_match_id
        diff['source_commit_original']=game.source_commit
        diff['original_fixture_kickoff']=game.kickoff
        starts=old[['player_id','started_original']].merge(latest,on='player_id',how='outer')
        starts['is_starting']=starts.is_starting.map(lambda v:None if pd.isna(v) else str(v).lower()=='true')
        comparable=starts.started_original.notna()&starts.is_starting.notna()
        changed_starts=int((starts.loc[comparable,'started_original']!=starts.loc[comparable,'is_starting']).sum())
        diff['player_membership_changed']=diff['_merge']!='both'
        diff['minutes_changed']=(diff['_merge']=='both')&(diff.minutes_played_original!=diff.minutes_played_current)
        diff['goals_changed']=(diff['_merge']=='both')&(diff.goals_original!=diff.goals_current)
        rows.append(diff.rename(columns={'_merge':'payload_membership'}))
        summary.append({'source_match_id':game.source_match_id,'original_fixture_kickoff':game.kickoff,
          'original_players':len(old),'current_players':len(new),'changed_player_membership':int(diff.player_membership_changed.sum()),
          'changed_common_player_minutes':int(diff.minutes_changed.sum()),'changed_common_player_goals':int(diff.goals_changed.sum()),
          'original_start_labels_known':clear,'changed_common_start_labels':changed_starts,
          'original_starters_missing_latest_lineup':int((starts.started_original==True).mul(starts.is_starting.isna()).sum()),
          'payload_changed':bool(diff[['player_membership_changed','minutes_changed','goals_changed']].any().any())})
    out=ROOT/'analysis/results/cup-payload-version-audit';out.mkdir(parents=True,exist_ok=True)
    pd.concat(rows,ignore_index=True).sort_values(['source_match_id','player_id']).to_csv(out/'player_payload_diffs.csv',index=False)
    pd.DataFrame(summary).to_csv(out/'fixture_payload_diffs.csv',index=False)
    write_json(out/'summary.json',{'compared_original_fixtures':len(summary),'changed_payloads':sum(r['payload_changed'] for r in summary),
      'changed_common_start_labels':sum(r['changed_common_start_labels'] for r in summary),
      'meaning':'Measures original versus current player/minute/goal payload and lineup labels under identical source keys. Unchanged stats combined with changed match metadata indicate mixed versions; this does not prove future player-minute contamination.'})
    inputs=[recovery,resolution,*paths,*lineup_paths,*sorted(set(original_paths))]
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
      'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [Path(__file__),ROOT/'scripts/recover_historical_cup_workload.py']],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json']})
    print(summary)


if __name__=='__main__':main()
