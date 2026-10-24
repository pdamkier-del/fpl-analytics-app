"""Read-only, public season history export; never creates forecast inputs."""
import argparse,hashlib,json,sqlite3
from pathlib import Path

import pandas as pd
from collect_player_match_context import norm

ROOT=Path(__file__).resolve().parents[1]
SEASONS=('2022-23','2023-24','2024-25','2025-26')


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    body=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    path.write_bytes(body);return hashlib.sha256(body).hexdigest()


def number(value):return float(value)if pd.notna(value)else None


def build(db,out,current,workload):
    out=Path(out);keys=['season','fixture_uuid','player_uuid']
    identities_path=ROOT/'data_v1_1/curated/history-archive-identities.json'
    identities=json.loads(identities_path.read_text())
    with sqlite3.connect(f'file:{Path(db).resolve()}?mode=ro',uri=True)as con:
        frame=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,opponent_team_id,gw,was_home,kickoff_at,minutes,goals,fpl_assists,xg,xa,total_points,fpl_position FROM player_fixture_observations WHERE is_final=1 AND season IN ('2022-23','2023-24','2024-25','2025-26')",con)
        team=pd.read_sql_query("SELECT season,fixture_uuid,team_id,opponent_team_id,gw,was_home,kickoff_at,gf,ga,source_name FROM team_fixture_observations WHERE season IN ('2022-23','2023-24','2024-25','2025-26')",con)
        codes=pd.read_sql_query("SELECT DISTINCT season,player_uuid,external_id FROM player_id_mapping WHERE id_namespace='fpl_element' AND season IN ('2022-23','2023-24','2024-25','2025-26') AND confidence=1",con)
        names=pd.read_sql_query('SELECT player_uuid,canonical_name FROM players',con).set_index('player_uuid').canonical_name.to_dict()
        receipts=pd.read_sql_query("SELECT source_url,payload_sha256 FROM raw_fetch_manifest WHERE source_url LIKE '%teams.csv' OR source_url LIKE '%players_raw.csv'",con)
    for r in identities['source_files']:
        match=receipts[receipts.source_url.str.endswith('/'+r['season']+'/'+r['file'])]
        if len(match)!=1 or match.payload_sha256.iloc[0]!=r['sha256']:raise ValueError('Archive identity differs from original Core source')
    team_key=['season','fixture_uuid','team_id']
    if (team.groupby(team_key)[['gf','ga','opponent_team_id','was_home']].nunique(dropna=False)>1).any().any():
        raise ValueError('Conflicting archived result sources')
    # Core retains both FPL and independent result observations. Use the
    # historical FPL row after checking their scorelines agree; never count
    # both observations as two games.
    team=team[team.source_name.eq('vaastav_historical_core')].copy()
    if frame.duplicated(keys).any()or team.duplicated(team_key).any():raise ValueError('Duplicate archived match identity')
    if frame.minutes.isna().any()or not frame.minutes.between(0,90).all():raise ValueError('Missing/invalid archived minutes')
    # Canonical club names are verified by player + exact PL kickoff; no fuzzy
    # player/team joins or end-of-season registration backfills are used.
    recorded=pd.read_csv(workload,low_memory=False)
    pl=recorded[recorded.competition.eq('Premier League')&recorded.season.isin(SEASONS)].copy()
    pl['kick']=pd.to_datetime(pl.kickoff,utc=True,format='mixed')
    frame['kick']=pd.to_datetime(frame.kickoff_at,utc=True,format='mixed')
    joined=frame[['season','player_uuid','team_id','kick']].merge(pl[['season','player_uuid','kick','club']],on=['season','player_uuid','kick'],how='left',validate='one_to_one')
    clubs=joined[['season','team_id','club']].dropna().drop_duplicates()
    if clubs.duplicated(['season','team_id']).any():raise ValueError('Ambiguous historical club name')
    club={(s,int(t)):r['name']for s,data in identities['seasons'].items()for t,r in data['teams'].items()}
    if any(norm(r.club)!=norm(club[r.season,int(r.team_id)])for r in clubs.itertuples()):raise ValueError('Archived club ID differs between independent sources')
    if any((r.season,int(r.team_id))not in club or (r.season,int(r.opponent_team_id))not in club for r in team.itertuples()):raise ValueError('Missing historical club identity')
    codes['fpl_code']=[identities['seasons'][r.season]['players'].get(str(int(r.external_id)))for r in codes.itertuples()]
    if codes.duplicated(['season','player_uuid']).any()or codes.duplicated(['season','fpl_code']).any():raise ValueError('Ambiguous archived stable code')
    frame=frame.merge(codes[['season','player_uuid','fpl_code']],on=['season','player_uuid'],how='left',validate='many_to_one')
    missing_codes=int(frame.loc[frame.fpl_code.isna(),['season','player_uuid']].drop_duplicates().shape[0])
    # Pair scorelines once so each player's view uses its actual historical
    # club, including transferred players, rather than today's registration.
    frame=frame.merge(team[['season','fixture_uuid','team_id','gf','ga']],on=['season','fixture_uuid','team_id'],how='left',validate='many_to_one')
    if frame.gf.isna().any()or frame.ga.isna().any():raise ValueError('Missing archived scoreline')
    for (season,fx),g in team.groupby(['season','fixture_uuid']):
        if len(g)!=2 or g.gf.iloc[0]!=g.ga.iloc[1]or g.ga.iloc[0]!=g.gf.iloc[1]:raise ValueError('Non-reciprocal archived result')
    catalogue=json.loads(Path(current).read_text())['documents']['current-players.json']
    forecast=json.loads((Path(current).parent/'forecast.json').read_text())
    official={p['id']:p for p in catalogue['players']}
    current_players={p['player_uuid']:str(official[p['id']]['code'])for p in forecast['players']}
    current_teams={str(t['id']):norm(t['name'])for t in catalogue['teams'].values()}
    seasons=[];counts={}
    for season in SEASONS:
        f=frame[frame.season.eq(season)];ts=team[team.season.eq(season)]
        if ts.fixture_uuid.nunique()!=380:raise ValueError('Incomplete archived PL season: '+season)
        players=[];teams=[]
        for uuid,g in f.groupby('player_uuid',sort=True):
            raw_code=g.fpl_code.iloc[0];code=int(raw_code)if pd.notna(raw_code)else None
            g=g.sort_values(['kickoff_at','fixture_uuid'],ascending=False)
            rows=[dict(fixture_id=r.fixture_uuid,gw=int(r.gw),kickoff=r.kickoff_at,
                team_id=int(r.team_id),club=club[season,int(r.team_id)],opponent=club[season,int(r.opponent_team_id)],
                home=bool(r.was_home),gf=int(r.gf),ga=int(r.ga),minutes=int(r.minutes),points=number(r.total_points),
                goals=number(r.goals),assists=number(r.fpl_assists),xg=number(r.xg),xa=number(r.xa))for r in g.itertuples()]
            def summary(group):
                return {label:float(group[col].sum())if group[col].notna().all()else None for label,col in
                        [('minutes','minutes'),('points','total_points'),('goals','goals'),('assists','fpl_assists'),('xg','xg'),('xa','xa')]}
            record=dict(code=code,player_uuid=uuid,name=names.get(uuid,uuid),position=str(g.fpl_position.iloc[0]),
                clubs=sorted({club[season,int(t)]for t in g.team_id}),rows=len(rows),
                **summary(g),by_club={club[season,int(t)]:summary(sub)for t,sub in g.groupby('team_id')})
            identity=str(code)if code is not None else 'uuid-'+str(uuid)
            filename=f'{season}/players/{identity}.json';digest=write(out/filename,dict(season=season,player=record,matches=rows))
            players.append(dict(**record,file=filename,sha256=digest))
        for tid,g in ts.groupby('team_id',sort=True):
            rows=[]
            for r in g.sort_values(['kickoff_at','fixture_uuid'],ascending=False).itertuples():
                roster=f[f.fixture_uuid.eq(r.fixture_uuid)&f.team_id.eq(tid)&f.minutes.gt(0)]
                # Unknown per-player xG is never displayed as a zero team xG.
                xg=float(roster.xg.sum())if len(roster)>=11 and roster.xg.notna().all()else None
                opp=f[f.fixture_uuid.eq(r.fixture_uuid)&f.team_id.eq(r.opponent_team_id)&f.minutes.gt(0)]
                xga=float(opp.xg.sum())if len(opp)>=11 and opp.xg.notna().all()else None
                rows.append(dict(fixture_id=r.fixture_uuid,gw=int(r.gw),kickoff=r.kickoff_at,
                    opponent=club[season,int(r.opponent_team_id)],home=bool(r.was_home),gf=int(r.gf),ga=int(r.ga),xg=xg,xga=xga))
            def total_row(key):return sum(r[key]for r in rows)if all(r[key]is not None for r in rows)else None
            record=dict(team_id=int(tid),name=club[season,int(tid)],key=norm(club[season,int(tid)]),matches=len(rows),
                wins=sum(r['gf']>r['ga']for r in rows),draws=sum(r['gf']==r['ga']for r in rows),losses=sum(r['gf']<r['ga']for r in rows),
                points=sum(3 if r['gf']>r['ga']else 1 if r['gf']==r['ga']else 0 for r in rows),
                goals=total_row('gf'),conceded=total_row('ga'),xg=total_row('xg'),xga=total_row('xga'))
            filename=f'{season}/teams/{int(tid)}.json';digest=write(out/filename,dict(season=season,team=record,matches=rows))
            teams.append(dict(**record,file=filename,sha256=digest))
        filename=f'{season}/index.json';digest=write(out/filename,dict(season=season,players=players,teams=teams))
        seasons.append(dict(season=season,file=filename,sha256=digest,players=len(players),teams=len(teams),fixtures=380))
        counts[season]=dict(player_match_rows=len(f),players=len(players),team_match_rows=len(ts),fixtures=380)
    receipt=dict(schema='fpl-public-history-archive-v1',seasons=seasons,current_players=current_players,current_teams=current_teams,
        current_player_ids={str(p['code']):p['id']for p in catalogue['players']},
        current_identity_forecast_sha256=forecast['forecast_sha256'],counts=counts,
        source=dict(core_sha256=hashlib.sha256(Path(db).read_bytes()).hexdigest(),identity_sha256=hashlib.sha256(identities_path.read_bytes()).hexdigest(),club_identity_sha256=hashlib.sha256(Path(workload).read_bytes()).hexdigest(),
                    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        missing_stable_code_player_seasons=missing_codes,
        notes=['Public completed Premier League match statistics; historical numeric IDs are not current registrations.',
               'Players without a verified stable code remain browsable under their canonical historical UUID; no current identity is guessed.',
               'Historical data is retrospective; archive ingestion times do not certify predeadline knowledge.',
               'Team xG is the sum of available played-player xG; incomplete sums remain null.',
               'Missing values remain null, never invented zero; no historical predictions are reconstructed.'],
        forecast_inputs_changed=False,production_changed=False)
    write(out/'index.json',receipt);return receipt


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--db',type=Path,default=ROOT/'work/core.sqlite3')
    ap.add_argument('--out',type=Path,default=ROOT/'app/mm-preview/history-archive')
    ap.add_argument('--current',type=Path,default=ROOT/'app/mm-preview/current/existing-app-data.json')
    a=ap.parse_args();r=build(a.db,a.out,a.current,ROOT/'analysis/results/mm-match-importance-20261016/individual_recorded_workload.csv.gz');print(json.dumps(r['counts'],indent=2))
