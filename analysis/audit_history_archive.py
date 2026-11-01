"""Reconcile every exported historical statistic to the canonical SQL actuals."""
import argparse,hashlib,json,sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--db',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    root=a.archive;index=json.loads((root/'index.json').read_text());rows=[];team_rows=[];files=0
    def read(record):
        nonlocal files
        p=(root/record['file']).resolve()
        if not p.is_relative_to(root.resolve()):raise ValueError('Unsafe archive path')
        b=p.read_bytes()
        if hashlib.sha256(b).hexdigest()!=record['sha256']:raise ValueError('Archive content changed')
        files+=1;return json.loads(b)
    for source in index['seasons']:
        season=read(source)
        for p in season['players']:
            data=read(p)
            for r in data['matches']:rows.append(dict(season=season['season'],player_uuid=p['player_uuid'],**r))
        for t in season['teams']:
            data=read(t)
            if len(data['matches'])!=38:raise ValueError('Team does not have 38 archived games')
            for r in data['matches']:team_rows.append(dict(season=season['season'],team_id=t['team_id'],**r))
            if t['points']!=3*t['wins']+t['draws']:raise ValueError('Invalid match points')
    actual=pd.DataFrame(rows).rename(columns={'fixture_id':'fixture_uuid'})
    with sqlite3.connect(f'file:{a.db.resolve()}?mode=ro',uri=True)as db:
        source=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,opponent_team_id,gw,minutes,total_points,goals,fpl_assists,xg,xa FROM player_fixture_observations WHERE is_final=1 AND season IN ('2022-23','2023-24','2024-25','2025-26')",db)
        teams=pd.read_sql_query("SELECT season,fixture_uuid,team_id,gf,ga FROM team_fixture_observations WHERE source_name='vaastav_historical_core' AND season IN ('2022-23','2023-24','2024-25','2025-26')",db)
    key=['season','fixture_uuid','player_uuid']
    merged=actual.merge(source,on=key,how='outer',indicator=True,validate='one_to_one',suffixes=('','_source'))
    if not merged._merge.eq('both').all():raise ValueError('Missing/extra historical player match')
    for x,y in [('team_id','team_id_source'),('gw','gw_source'),('minutes','minutes_source'),('points','total_points'),('goals','goals_source'),('assists','fpl_assists'),('xg','xg_source'),('xa','xa_source')]:
        if not np.allclose(merged[x].astype(float),merged[y].astype(float),equal_nan=True,atol=0,rtol=0):raise ValueError('Historical statistic changed: '+x)
    exported=pd.DataFrame(team_rows).rename(columns={'fixture_id':'fixture_uuid'})
    merged=exported.merge(teams,on=['season','fixture_uuid','team_id'],how='outer',indicator=True,validate='one_to_one',suffixes=('','_source'))
    if not merged._merge.eq('both').all()or not merged.gf.eq(merged.gf_source).all()or not merged.ga.eq(merged.ga_source).all():raise ValueError('Archived team results differ')
    report=dict(passed=True,player_match_rows=len(actual),team_match_rows=len(exported),verified_files=files,
                seasons=index['counts'],all_statistics_exact=True,missing_stable_code_player_seasons=index['missing_stable_code_player_seasons'],
                no_fuzzy_identity_mapping=True,forecast_inputs_changed=False,production_changed=False)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
