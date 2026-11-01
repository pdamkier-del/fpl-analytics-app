"""Rebuild verified historical penalty identities; no inference from xG gaps."""
import sys,pathlib,json,gzip,sqlite3,hashlib,argparse
import pandas as pd
sys.path[:0]=['src','scripts']
from run_shared_penalty_joint import player_penalty_ledger
parser=argparse.ArgumentParser();parser.add_argument('--out',type=pathlib.Path,required=True);parser.add_argument('--roles-source',type=pathlib.Path);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
source_hashes={};matches=set();mapping={};fixtures={}
for line in gzip.open('data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz','rt'):
 r=json.loads(line)
 if r.get('fpl_fixture_id')is not None and r.get('identity_status')=='mapped':mapping[str(r['provider_match_id']),str(r['provider_player_id'])]=r['player_uuid'];fixtures[str(r['provider_match_id'])]=int(r['fpl_fixture_id'])
c=sqlite3.connect('file:work/core.sqlite3?mode=ro',uri=True);h=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,xg,gw FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",c);fx=pd.read_sql_query("SELECT fixture_uuid,fpl_fixture_id FROM fixtures WHERE season='2024-25'",c).set_index('fpl_fixture_id').fixture_uuid.to_dict();rows=[]
for p in pathlib.Path('data_v1_1/raw/season_2024_25_v1/fotmob/details').glob('*.json'):
 d=json.loads(p.read_text());g=d.get('general',{})
 if g.get('leagueName')!='Premier League':continue
 mid=str(g['matchId']);matches.add(mid);source_hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 assert g.get('finished')is True and isinstance(d['content'].get('shotmap'),dict) and 'shots'in d['content']['shotmap']
 for shot in d['content']['shotmap']['shots']:
  if shot.get('situation')=='Penalty':rows.append(dict(season='2024-25',fixture_uuid=fx[fixtures[mid]],player_uuid=mapping[mid,str(shot['playerId'])],attempts=1.))
assert len(matches)==380,'Incomplete 2024 penalty shotmap coverage'
raw_attempts=0.
for gw in range(1,39):
 path=pathlib.Path(f'data_v1_1/raw/all-competitions-2025-26/GW{gw}/playermatchstats.csv');z=pd.read_csv(path);played=z[z.match_id.astype(str).str.contains('-prem-')&pd.to_numeric(z.minutes_played,errors='coerce').gt(0)]
 assert not played[['penalties_scored','penalties_missed']].isna().any().any(),'Unknown penalty observations'
 raw_attempts+=float(played.penalties_scored.sum()+played.penalties_missed.sum())
 source_hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
s,p,t=player_penalty_ledger()
assert s.match_id.nunique()==380 and len(s)==760
assert p.player_uuid.notna().all() and float(p.attempts.sum())==raw_attempts,'Dropped penalty identity'
for r in p.itertuples():rows.append(dict(season='2025-26',fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,attempts=r.attempts))
a=pd.DataFrame(rows).groupby(['season','fixture_uuid','player_uuid'],as_index=False).attempts.sum().merge(h,on=['season','fixture_uuid','player_uuid'],how='left',validate='one_to_one');a['residual']=a.xg-.79*a.attempts
print(a.groupby('season').agg(events=('attempts','sum'),rows=('xg','size'),missing=('xg',lambda x:x.isna().sum()),min_residual=('residual','min')).to_string());print('NEGATIVE',a[a.residual<-.011].to_dict('records'))
assert a.xg.notna().all() and (a.residual>=-.0051).all()
a.to_csv(args.out/'verified-attempts.csv',index=False)
(args.out/'raw-source-hashes.json').write_text(json.dumps(source_hashes,sort_keys=True,indent=2)+'\n')

if args.roles_source:
 from fpl_v1_1_model.role_event_priors import QCOLS
 z=pd.read_csv(args.roles_source,low_memory=False)
 z[['gw','fixture_uuid','player_uuid','team_id','pos','cutoff','max_history_known_at']+QCOLS].to_csv(args.out/'predeadline-roles-2024.csv.gz',index=False,compression={'method':'gzip','mtime':0})
