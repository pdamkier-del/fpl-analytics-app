import json,gzip,sqlite3
from pathlib import Path
from collections import defaultdict,Counter
import pandas as pd
import argparse,hashlib
ap=argparse.ArgumentParser();ap.add_argument('--out',default='analysis/results/pm-research-20261015');args=ap.parse_args()
root=Path(__file__).resolve().parents[1];mp={};fid={}
with gzip.open(root/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz','rt') as z:
 for line in z:
  r=json.loads(line)
  if r.get('fpl_fixture_id') is not None and r.get('identity_status')=='mapped':
   mp[str(r['provider_match_id']),str(r['provider_player_id'])]=r['player_uuid'];fid[str(r['provider_match_id'])]=int(r['fpl_fixture_id'])
with sqlite3.connect(root/'work/core.sqlite3') as c:
 fx=pd.read_sql_query("select fixture_uuid,fpl_fixture_id from fixtures where season='2024-25'",c);obs=pd.read_sql_query("select fixture_uuid,player_uuid,xg,goals,minutes from player_fixture_observations where season='2024-25'",c)
fmap=fx.set_index('fpl_fixture_id').fixture_uuid.to_dict();agg=defaultdict(lambda:dict(xg=0.,npxg=0.,npg=0.,pg=0.,shots=0));errors=[];situations=Counter();matches=0;assistpairs=0
for path in (root/'data_v1_1/raw/season_2024_25_v1/fotmob/details').glob('*.json'):
 x=json.loads(path.read_text());g=x.get('general',{})
 if g.get('leagueName')!='Premier League':continue
 mid=str(g.get('matchId'));matches+=1
 for e in x.get('content',{}).get('matchFacts',{}).get('events',{}).get('events',[]):
  if e.get('type')=='Goal' and e.get('assistPlayerId'):assistpairs+=1
 for s in x.get('content',{}).get('shotmap',{}).get('shots',[]):
  situations[s.get('situation')]+=1
  if s.get('isOwnGoal'):continue
  pid=mp.get((mid,str(s.get('playerId'))));fix=fmap.get(fid.get(mid));v=s.get('expectedGoals')
  if pid is None or fix is None or v is None:errors.append(dict(match=mid,player=s.get('playerId'),reason='unmapped or missing xg'));continue
  r=agg[fix,pid];r['xg']+=v;r['shots']+=1
  if s.get('situation')!='Penalty':r['npxg']+=v;r['npg']+=int(s['eventType']=='Goal')
  else:r['pg']+=int(s['eventType']=='Goal')
f=pd.DataFrame([dict(fixture_uuid=k[0],player_uuid=k[1],**v) for k,v in agg.items()]).merge(obs,on=['fixture_uuid','player_uuid'],how='left',suffixes=('_provider','_core'),validate='one_to_one');delta=(f.xg_provider-f.xg_core).abs()
report=dict(classification='RAW_2024_NONPENALTY_SOURCE_AUDIT_NOT_PROVIDER_EQUIVALENCE_CERTIFICATION',matches=matches,shot_players=len(f),shot_situations=dict(situations),unmapped_or_missing=len(errors),missing_core=int(f.xg_core.isna().sum()),max_xg_difference=float(delta.max()),within_001=int(delta.le(.0100001).sum()),larger_005=int(delta.gt(.05).sum()),goal_credit_mismatches=int((f.npg+f.pg).ne(f.goals).sum()),penalty_goals=int(f.pg.sum()),npg=int(f.npg.sum()),nonpen_xg=float(f.npxg.sum()),goal_events_assist_links=assistpairs,credit_discrepancies=f[(f.npg+f.pg).ne(f.goals)].to_dict('records'),large_xg_discrepancy_examples=f.assign(abs_delta=delta).sort_values('abs_delta',ascending=False).head(10).to_dict('records'),source_files_digest=hashlib.sha256(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'data_v1_1/raw/season_2024_25_v1/fotmob/details').glob('*.json'))},sort_keys=True).encode()).hexdigest(),limitations=['Native shotmap npxG can be constructed within this provider in 2024 only','Do not subtract this provider penalty xG from FPL xG without equivalence','Goal assist links are success-selected; no failed-shot creator data','No 2025 verified matching shotmap source recovered in this audit'],locked_model_active=False,promotion_allowed=False)
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
(out/'raw_nonpenalty_source_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['large_xg_discrepancy_examples','source_files']},indent=2))
