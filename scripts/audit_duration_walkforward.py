#!/usr/bin/env python3
"""General duration half-life sensitivity; conditional starter component only.
No player-specific patches; original project_minutes and constants remain frozen.
"""
from pathlib import Path
import sys,json,gzip,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from build_locked_live_v2_baseline import exact_frozen_duration_constants
OUT=ROOT/'analysis/results/full-model-audit-20261012'
H=exact_frozen_duration_constants()['DUR_H'];GRID=[H,1.,2.,3.,6.,10.]
def load(season):
 rows=[];sources=[];missing=0
 if season=='2024-25':
  p=ROOT/'data_v1_1/derived/season_2024_25_v1/existing_core_player_fixture_observations.jsonl.gz';sources=[p]
  with gzip.open(p,'rt') as z:
   for line in z:
    r=json.loads(line)
    if any(r.get(c) is None for c in ['started','minutes','kickoff_at','gw','player_uuid']):missing+=1;continue
    rows.append(dict(fixture=r['fixture_uuid'],player=str(r['player_uuid']),gw=int(r['gw']),kickoff=r['kickoff_at'],started=int(r['started']),minutes=float(r['minutes'])))
  dp=ROOT/'data_v1_1/derived/season_2024_25_v1/deadlines.json'
 else:
  for folder in sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*')):
   files=[folder/n for n in ['matches.csv','lineups.csv','playermatchstats.csv']];sources+=files
   match=pd.read_csv(files[0],low_memory=False);lineup=pd.read_csv(files[1],low_memory=False);stats=pd.read_csv(files[2],low_memory=False)
   match=match[match.match_id.astype(str).str.startswith('25-26-prem-')].drop_duplicates('match_id')
   lineup=lineup[lineup.match_id.isin(match.match_id)]
   if lineup.duplicated(['match_id','player_id']).any() or stats.duplicated(['match_id','player_id']).any():raise ValueError('Duplicate provider identities')
   joined=lineup.merge(stats[['match_id','player_id','minutes_played']],on=['match_id','player_id'],how='left',validate='one_to_one').merge(match[['match_id','gameweek','kickoff_time']],on='match_id',validate='many_to_one')
   for r in joined.itertuples():
    if pd.isna(r.minutes_played) or pd.isna(r.is_starting):missing+=1;continue
    val=str(r.is_starting).lower()
    if val not in ['true','false','1','0']:raise ValueError('Unknown starting-state encoding')
    rows.append(dict(fixture=r.match_id,player=str(r.player_id),gw=int(r.gameweek),kickoff=r.kickoff_time,started=int(val in ['true','1']),minutes=float(r.minutes_played)))
  dp=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2/deadlines.json'
 sources.append(dp);d={int(r['gw']):pd.Timestamp(r['cutoff']) for r in json.loads(dp.read_text())};f=pd.DataFrame(rows).drop_duplicates(['fixture','player']);f['available']=pd.to_datetime(f.kickoff,utc=True)+pd.Timedelta(hours=4)
 if not f.minutes.between(0,90).all():raise ValueError('Minutes outside model physical support')
 return f,d,dict(rows=len(f),missing_not_imputed=missing,sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
def predictions(f,d):
 rows=[]
 for pid,g in f.groupby('player'):
  g=g.sort_values(['available','fixture'])
  for r in g[g.started.eq(1)&g.gw.ge(6)].itertuples():
   cutoff=d[r.gw]
   if pd.Timestamp(r.kickoff)<=cutoff:continue
   past=g[g.available.lt(cutoff)];mask=past.started.to_numpy()==1
   # No cold-start comparison: do not invent or tune missing player history.
   if not mask.any():continue
   lag=np.arange(len(past)-1,-1,-1)[mask];mins=past.minutes.to_numpy()[mask]
   for half in GRID:
    w=np.exp2(-lag/half);pred=float(w@mins/w.sum());rows.append(dict(fixture=r.fixture,player=pid,gw=r.gw,half=half,actual=r.minutes,pred=pred,mae=abs(pred-r.minutes),squared=(pred-r.minutes)**2))
 return pd.DataFrame(rows)
def score(p):
 return p.groupby('half').agg(rows=('actual','size'),mae=('mae','mean'),mse=('squared','mean')).reset_index().to_dict('records')
def current_focus(selected):
 from fpl_v1_1_model.minutes import project_minutes
 base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
 f=pd.read_csv(base/'player_fixture_observations.csv.gz');inputs=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False);rows=[]
 for pid in [411,12]:
  past=f[f.fpl_element.eq(pid)].sort_values('kickoff_at').to_dict('records');r=inputs[inputs.fpl_element.eq(pid)&inputs.target_gw.eq(7)].iloc[0]
  before=project_minutes(past,duration_half_life=H).expected_minutes_given_start;after=project_minutes(past,duration_half_life=selected).expected_minutes_given_start
  rows.append(dict(player=r.player,original_start_minutes=before,candidate_start_minutes=after,original_mm_xmins=float(r.xmins),candidate_component_xmins_fixed_p_start=float(r.p_start*after+(1-r.p_start)*r.p_cameo_given_bench*r.cameo_minutes_mean),p_start_unchanged=float(r.p_start),xp_after='Not Available: full PM rerun with this duration candidate has not been validated'))
 return rows

def main():
 frames={};coverage={}
 for season in ['2024-25','2025-26']:
  f,d,coverage[season]=load(season);frames[season]=predictions(f,d)
 dev=pd.DataFrame(score(frames['2024-25'].query('gw<=21')));selected=float(dev.sort_values(['mae','mse']).iloc[0].half);results={};rng=np.random.default_rng(20261012)
 for name,p in [('2024-25_GW22-38',frames['2024-25'].query('gw>=22')),('2025-26_GW6-38',frames['2025-26'])]:
  pair=p[np.isclose(p.half,H)].merge(p[np.isclose(p.half,selected)],on=['fixture','player','gw'],suffixes=('_baseline','_candidate'),validate='one_to_one');pair['delta']=pair.mae_candidate-pair.mae_baseline
  block=pair.groupby('fixture').agg(total=('delta','sum'),n=('delta','size')).to_numpy();idx=rng.integers(len(block),size=(4000,len(block)));b=block[idx].sum(axis=1)
  results[name]=dict(scores=score(p),paired_mae_delta=float(pair.delta.mean()),fixture_block_bootstrap_95_ci=np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist())
 report=dict(classification='CONDITIONAL_STARTER_DURATION_ONLY_NOT_FULL_MM',original_half_life=H,selected_half_life=selected,selection='2024-25 GW6-21 minimum MAE then MSE',coverage=coverage,results=results,promotion_allowed=False,current_focus_component_only=current_focus(selected),limitations=['Conditional starter duration only: no refit of start probabilities, workload, medical or roles','2025 lineup/playerstats coverage differs from full registered-roster MM ledger; missing minutes excluded, never assumed zero','Historical availability uses kickoff+4h proxy','Frozen baseline was already trained partly on 2024; this is not independent whole-model certification','No PM or six-GW TS acceptance test for this parameter candidate'])
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'duration_walkforward_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='coverage'}))
if __name__=='__main__':main()
