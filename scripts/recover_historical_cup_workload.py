#!/usr/bin/env python3
"""Recover original cup observations from frozen pre-deadline source versions.

No current overwritten statistic is relabelled. Unknown start intervals remain
unknown. Source Git timestamp is a recorded version boundary, not ingestion
certification. Fixtures must independently match pair, score and calendar date.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
import pandas as pd
from audit_independent_europe_fixtures import normalize
from build_reproducible_role_benchmark import ROOT,sha,write_json


def match_archive_fixture(row, inventory, source_at):
    a,b=row.match_id.removeprefix('25-26-'+row.tournament+'-').split('-vs-')
    a,b=normalize(a),normalize(b)
    ko=pd.to_datetime(row.kickoff_time,utc=True,errors='coerce')
    source_at=pd.to_datetime(source_at,utc=True)
    if pd.isna(ko) or ko>=source_at:raise ValueError('Archive precedes fixture outcome or lacks kickoff')
    hits=inventory[(inventory.competition==row.tournament)&(inventory.date==str(ko.date()))&
      (((inventory.home==a)&(inventory.away==b)&(inventory.home_score==row.home_score)&(inventory.away_score==row.away_score))|
       ((inventory.home==b)&(inventory.away==a)&(inventory.home_score==row.away_score)&(inventory.away_score==row.home_score)))]
    if len(hits)!=1:raise ValueError('Archive fixture identity is not unique')
    hit=hits.iloc[0]
    if 'kickoff_candidate' in hit and pd.notna(hit.kickoff_candidate):
        if ko!=pd.to_datetime(hit.kickoff_candidate,utc=True):raise ValueError('CL archive clock disagrees with independent inventory')
    return hit,ko,max(ko+pd.Timedelta(hours=3),source_at)


def start_labels(stats):
    """Interval endpoints can label a complete XI; all-zero source is unknown."""
    good=stats.start_min.between(0,120) & stats.finish_min.between(0,150) & (stats.finish_min>0) & (stats.finish_min>=stats.start_min)
    clear=bool(good.all() and ((stats.start_min==0)&(stats.minutes_played>0)).sum()==11)
    return [(bool(r.start_min==0) if clear else None) for r in stats.itertuples()],clear


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--db',required=True)
    ap.add_argument('--out',default=str(ROOT/'analysis/results/historical-cup-recovery-v1'))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    raw=ROOT/'data_v1_1/raw/deadline-cup-source-2025-26'
    manifest=json.loads((raw/'SOURCE_MANIFEST.json').read_text())
    for entry in manifest['files']:
        b=(raw/entry['path']).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==entry['git_blob_sha']
    indexed={r['path']:r for r in manifest['files']}
    el=ROOT/'data_v1_1/raw/independent-cup-inventory/uefa-el-conference-2025-26.csv'
    cl=ROOT/'analysis/results/independent-cl-audit/independent_inventory.csv'
    inventory=pd.read_csv(el)
    cl_frame=pd.read_csv(cl);cl_frame['competition']='champions-league'
    cl_frame['date']=pd.to_datetime(cl_frame.kickoff_candidate,utc=True).dt.strftime('%Y-%m-%d')
    inventory=pd.concat([inventory,cl_frame],ignore_index=True)
    for side in ('home','away'):inventory[side]=inventory[side].map(normalize)
    quarantine=ROOT/'analysis/results/independent-europe-audit/workload_quarantine.csv'
    targets=set(pd.read_csv(quarantine).match_id)
    classified=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
    current=ROOT/'data_v1_1/raw/all-competitions-2025-26'
    line_paths=sorted(current.glob('GW*/lineups.csv'))
    lines=pd.concat([pd.read_csv(p) for p in line_paths],ignore_index=True)
    con=sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro',uri=True)
    mapping={int(k):v for k,v in con.execute("SELECT external_id,player_uuid FROM player_id_mapping WHERE season='2025-26' AND id_namespace='fpl_element'")}
    lines=lines[lines.match_id.str.contains('-prem-')].copy();lines['player_uuid']=lines.player_id.map(mapping)
    aligned=lines.merge(pd.read_csv(classified)[['match_id','player_uuid','team_id']].drop_duplicates(),on=['match_id','player_uuid'])
    pairs=aligned[['team_code','team_id']].dropna().drop_duplicates()
    assert not pairs.team_code.duplicated().any()
    teams=dict(zip(pairs.team_code.astype(int),pairs.team_id.astype(int)))
    coverage=[];observations=[];excluded=[]
    for p in sorted(raw.rglob('matches.csv')):
        frame=pd.read_csv(p);stat_path=p.with_name('playermatchstats.csv');stats=pd.read_csv(stat_path)
        meta=indexed[str(stat_path.relative_to(raw))]
        source_at=pd.to_datetime(meta['source_commit_at'],utc=True)
        assert source_at<pd.to_datetime(meta['lookup_upper_bound'],utc=True)
        for r in frame[frame.match_id.isin(targets)].itertuples():
            try:
                if str(r.finished).lower()!='true':raise ValueError('Archive outcome unfinished')
                hit,ko,known=match_archive_fixture(r,inventory,source_at)
                codes=[int(c) for c in (r.home_team,r.away_team) if pd.notna(c) and int(c) in teams]
                if len(codes)!=1:raise ValueError('Recovery requires exactly one identified PL team')
                team=teams[codes[0]];g=stats[stats.match_id==r.match_id].copy()
                if len(g)<11 or g.player_id.duplicated().any():raise ValueError('Incomplete or duplicate archive player statistics')
                if g.minutes_played.isna().any() or not g.minutes_played.between(0,120).all():raise ValueError('Invalid archive minutes')
                if not g.player_id.map(mapping).notna().all():raise ValueError('Archive player identity unmapped')
                labels,complete=start_labels(g)
                key=f'restored-{r.tournament}-{hit.date}-{hit.home}-vs-{hit.away}'
                provenance={'source_match_id':r.match_id,'source_commit':meta['source_commit'],
                  'source_version_at':source_at.isoformat(),'stats_path':str(stat_path.relative_to(ROOT)),
                  'match_id':key,'team_id':team,'competition':r.tournament,'kickoff':ko.isoformat(),'available_at':known.isoformat()}
                coverage.append({**provenance,'mapped_players':len(g),'complete_player_stats':complete,
                  'unknown_start_labels':0 if complete else len(g),'minutes_sum':float(g.minutes_played.sum()),
                  'source':'Original pre-deadline Git payload; independent fixture identity matched'})
                for player,label in zip(g.itertuples(),labels):
                    observations.append({**provenance,'player_uuid':mapping[int(player.player_id)],
                      'minutes':float(player.minutes_played),'started':label})
            except ValueError as e:excluded.append({'source_match_id':r.match_id,'reason':str(e)})
    # Keep the earliest valid frozen version per original fixture, including
    # publication after a Friday deadline when no earlier complete payload exists.
    chosen={}
    for row in sorted(coverage,key=lambda r:(r['available_at'],r['source_commit'])):
        chosen.setdefault(row['match_id'],row)
    coverage=list(chosen.values())
    observations=[r for r in observations if r['source_commit']==chosen[r['match_id']]['source_commit']]
    assert len(coverage)==7 and len({r['match_id'] for r in coverage})==7
    assert len(observations)==104
    pd.DataFrame(coverage).sort_values('match_id').to_csv(out/'restored_team_games.csv',index=False)
    pd.DataFrame(observations).sort_values(['match_id','player_uuid']).to_csv(out/'restored_player_minutes.csv',index=False)
    pd.DataFrame(excluded,columns=['source_match_id','reason']).to_csv(out/'excluded_archive_rows.csv',index=False)
    write_json(out/'summary.json',{'restored_team_games':len(coverage),'restored_player_observations':len(observations),
      'unknown_start_observations':sum(r['started'] is None for r in observations),
      'known_availability_rule':'max(kickoff+3h, frozen source Git version timestamp)',
      'source_ingestion_certified':False,'no_current_payload_relabelling':True,
      'missing_original_case':'Palace/AEK Larnaca absent from the bounded source snapshots; not recovered',
      'lineups':'Old lineup files absent; valid intervals recover six complete XIs; Manchester City intervals all zero, all 15 start labels unknown'})
    inputs=[Path(a.db).resolve(),el,cl,quarantine,classified,raw/'SOURCE_MANIFEST.json',*sorted(raw.rglob('*.csv')),*line_paths]
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
      'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [Path(__file__),ROOT/'scripts/audit_independent_europe_fixtures.py',ROOT/'scripts/audit_independent_cl_fixtures.py']],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json']})
    print(json.loads((out/'summary.json').read_text()))


if __name__=='__main__':main()
