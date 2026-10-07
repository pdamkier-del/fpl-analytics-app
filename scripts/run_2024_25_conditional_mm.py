#!/usr/bin/env python3
"""Conditional 2024/25 locked-MM replay adapter.

This does NOT claim strict historical replay. It preserves the locked MM
mathematics and policy, but feeds them explicitly documented 2024/25 proxies:
- archived deadline candidate cohort/price/status timing is uncertified;
- structural formation/layout role evidence replaces unavailable measured
  average positions;
- provider post-match observations become available at kickoff+4h;
- Team News is UNKNOWN/neutral because no exact predeadline snapshot is certified.

No MM hyperparameter or selection is tuned on this run.
"""
from __future__ import annotations
import argparse,gzip,json,sqlite3,sys,unicodedata,re
from collections import defaultdict
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.minutes import project_minutes
from fpl_v1_1_model.role_classifier import ROLES,template,canonical
from fpl_v1_1_model.role_history import RoleHistory,summarize_state
from fpl_v1_1_model.workload import WorkloadHistory,WORKLOAD_FEATURES
from fpl_v1_1_model.rating_history import build_rating_features
from run_v4_three_state_sequence_experiment import add_sequence_features
from run_v4_performance_rating_experiment import add_features as add_perf_features
from run_mm_v2_team_news_availability_experiment import evaluate_news_variant

POLICY='soft_0.5_0.1'
BASE_ROLE_FIELDS=('fit','h','qmax','evidence')
ROLE_H=1.3150986300759975
DUR_H=0.32192611540889443
LI=0.03186876473704488
LS=0.6645162300313383

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or ''))
    s=''.join(c for c in s if not unicodedata.combining(c)).lower().replace('&','and')
    return re.sub(r'[^a-z0-9]+','',s)

def jsonl_gz(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]

def exact11(frame,p):
    out=np.asarray(p,float).copy()
    for idx in frame.groupby(['fixture_uuid','team_id'],sort=False).indices.values():
        ii=np.asarray(idx,int);x=np.clip(out[ii],1e-8,1-1e-8);z=np.log(x/(1-x));lo,hi=-30.,30.
        for _ in range(80):
            m=(lo+hi)/2;s=(1/(1+np.exp(-(z+m)))).sum()
            if s<11:lo=m
            else:hi=m
        out[ii]=1/(1+np.exp(-(z+(lo+hi)/2)))
    return out

def build_baseline(con,season,deadlines):
    allobs=pd.read_sql_query("""select season,gw,fixture_uuid,player_uuid,team_id,opponent_team_id,was_home,
      fpl_position,started,minutes,kickoff_at from player_fixture_observations
      where season in ('2023-24','2024-25') and is_final=1
      order by season,gw,kickoff_at,team_id,player_uuid""",con)
    allobs['started']=allobs.started.fillna(0).astype(int);allobs['minutes']=allobs.minutes.fillna(0.).astype(float)
    rows=[];hist=defaultdict(list)
    for ss in ['2023-24','2024-25']:
      sdf=allobs[allobs.season.eq(ss)]
      for gw in sorted(sdf.gw.dropna().astype(int).unique()):
       g=sdf[sdf.gw.eq(gw)]
       for r in g.itertuples(index=False):
        h=hist[(ss,str(r.player_uuid))]
        def wavg(which,half,default=.25):
          if not h:return default
          vals=[];ws=[]
          for pgw,st,mins in h:
           w=2**(-max(1,gw-pgw)/half);ws.append(w);vals.append(st if which=='start' else mins/90.)
          return float(np.average(vals,weights=ws))
        fast=wavg('start',3.);slow=wavg('start',10.);recent=wavg('mins',3.)
        prev=[x for x in h if x[0]==gw-1]
        last_start=float(np.mean([x[1] for x in prev])) if prev else fast
        last_mins=float(np.mean([x[2] for x in prev]))/90. if prev else recent
        rows.append(dict(season=ss,gw=int(gw),fixture_uuid=r.fixture_uuid,player_uuid=str(r.player_uuid),
          team_id=int(r.team_id),opponent_team_id=int(r.opponent_team_id),was_home=bool(r.was_home),
          pos=str(r.fpl_position),y=int(r.started),minutes=float(r.minutes),kickoff_at=r.kickoff_at,
          fast=fast,slow=slow,recent_mins=recent,last_start=last_start,last_mins=last_mins))
       for r in g.itertuples(index=False):hist[(ss,str(r.player_uuid))].append((int(gw),int(r.started),float(r.minutes)))
    x=pd.DataFrame(rows)
    feat=['fast','slow','recent_mins','last_start','last_mins']
    X=pd.concat([x[feat],pd.get_dummies(x.pos,prefix='pos',dtype=float)],axis=1)
    for c in ['pos_DEF','pos_FWD','pos_GK','pos_GKP','pos_MID']:
        if c not in X:X[c]=0.
    frozen=json.loads((ROOT/'analysis/results/v2-reproduced/metrics.json').read_text())['coefficients']
    cols=['fast','slow','recent_mins','last_start','last_mins','pos_DEF','pos_FWD','pos_GK','pos_MID','pos_GKP']
    t=x[x.season.eq(season)].copy().reset_index(drop=True)
    Xt=X.loc[x.season.eq(season),cols].reset_index(drop=True)
    z=np.full(len(t),float(frozen['intercept']))
    for col in cols:z+=Xt[col].to_numpy(float)*float(frozen.get(col,0.0))
    t['p_start_v2_raw']=1/(1+np.exp(-z))
    t['p_start_v2']=exact11(t,t.p_start_v2_raw)
    # Locked conditional duration/cameo decomposition, current-season history only.
    obs=allobs[allobs.season.eq(season)].copy()
    by={str(pid):g.sort_values(['gw','kickoff_at'])[['gw','started','minutes']].to_dict('records') for pid,g in obs.groupby('player_uuid')}
    sm=[];cm=[];pc=[];xm=[]
    for r in t.itertuples(index=False):
      h=[z for z in by.get(str(r.player_uuid),[]) if int(z['gw'])<int(r.gw)]
      p=project_minutes(h,role_half_life=ROLE_H,duration_half_life=DUR_H,start_logit_intercept=LI,start_logit_slope=LS,availability=1.)
      ps=float(r.p_start_v2);sm.append(p.expected_minutes_given_start);cm.append(p.expected_minutes_given_cameo);pc.append(p.p_cameo_given_bench)
      xm.append(ps*p.expected_minutes_given_start+(1-ps)*p.p_cameo_given_bench*p.expected_minutes_given_cameo)
    t['start_minutes_mean']=sm;t['cameo_minutes_mean']=cm;t['p_cameo_given_bench']=pc;t['expected_minutes_v2']=xm
    t['base_logit']=logit(np.clip(t.p_start_v2,1e-6,1-1e-6))
    t['cutoff']=t.gw.map(deadlines)
    t['outcome_known_at']=(pd.to_datetime(t.kickoff_at,utc=True)+pd.Timedelta(hours=4)).astype(str)
    names=dict(con.execute('select player_uuid,canonical_name from players'))
    t['player']=t.player_uuid.map(names).fillna(t.player_uuid);t['team']=t.team_id.astype(str)
    return t,frozen,cols

def team_name_map(cands):
    d=defaultdict(set)
    for r in cands:
      if r.get('team') is not None and r.get('team_id') is not None:d[norm(r['team'])].add(int(r['team_id']))
    return {k:next(iter(v)) for k,v in d.items() if len(v)==1}

def build_histories(derived,cands):
    tmap=team_name_map(cands)
    obs=jsonl_gz(derived/'all_competition_player_observations.jsonl.gz')
    bymatch=defaultdict(dict)
    for r in obs:
      if not r.get('player_uuid'):continue
      bymatch[(str(r['match_id']),str(r['player_uuid']))]=r
    role=RoleHistory()
    role_rows=jsonl_gz(derived/'raw_role_inputs.jsonl.gz')
    groups=defaultdict(list)
    for r in role_rows:
      tid=tmap.get(norm(r.get('team')))
      if tid is not None and r.get('player_uuid'):groups[(str(r['match_id']),tid,str(r.get('formation') or ''))].append(r)
    role_games=0
    for (mid,tid,formation),g in groups.items():
      g=sorted(g,key=lambda z:int(z.get('lineup_slot') or 0))
      pats=template(formation);flat=['GK']+[canonical(q) for line in pats for q in line]
      if len(g)!=11 or len(flat)!=11:continue
      players=[]
      for rr,rl in zip(g,flat):
        o=bymatch.get((mid,str(rr['player_uuid'])),{})
        mins=float(o.get('minutes') or 0.)
        players.append({'player_uuid':str(rr['player_uuid']),'role':rl,'started':True,'minutes':mins,'disagreement':False})
      known=pd.to_datetime(g[0]['available_at_proxy'],utc=True)
      role.add_game(tid,known,mid,players,importance=1.0,competition=str(g[0].get('competition') or 'prem'))
      role_games+=1
    work=WorkloadHistory();wg=defaultdict(list)
    for r in obs:
      tid=tmap.get(norm(r.get('team')))
      if tid is None:continue
      wg[(str(r['match_id']),tid)].append(r)
    work_games=0
    for (mid,tid),g in wg.items():
      players={}
      for r in g:
        if not r.get('player_uuid') or r.get('minutes') is None:continue
        players[str(r['player_uuid'])]={'minutes':float(r['minutes']),'started':bool(r.get('started'))}
      if not players:continue
      ko=str(g[0]['kickoff']);known=str(g[0]['available_at_proxy']);comp=str(g[0].get('competition') or 'prem')
      work.add_game(tid,mid,ko,known,comp,players,False);work_games+=1
    return role,work,obs,role_games,work_games

def add_role_work(frame,role,work):
    out=[];cache={}
    for r in frame.itertuples(index=False):
      cut=pd.to_datetime(r.cutoff,utc=True);key=(int(r.team_id),str(cut))
      if key not in cache:
        cache[key]=({s:role.state(int(r.team_id),cut,h) for s,h in [('fast',3),('slow',10)]},work.state(int(r.team_id),cut))
      rs,ws=cache[key];rec={}
      for speed in ('fast','slow'):
        states,caps,games=rs[speed];st=states.get(str(r.player_uuid),{});sm=summarize_state(st,caps)
        for f in BASE_ROLE_FIELDS:rec[f'role_{f}_{speed}']=float(sm.get('role_'+f,0.))
        for fld in ('q','H'):
          vals=st.get(fld,{})
          for role_name in ROLES:rec[f'{fld}_{role_name}_{speed}']=float(vals.get(role_name,0.))
        if speed=='slow':
          q=st.get('q',{});rec['expected_role']=max(sorted(q),key=q.get) if q else 'UNKNOWN'
          rec['role_started_last_gw']=float(bool(games and any(str(p['player_uuid'])==str(r.player_uuid) and p.get('started') for p in games[-1]['players'])))
          rec['max_history_known_at']=games[-1]['known_at'].isoformat() if games else ''
      state,default,known=ws;rec.update(state.get(str(r.player_uuid),default));rec['work_max_history_known_at']=known.isoformat() if known else ''
      out.append(rec)
    return pd.concat([frame.reset_index(drop=True),pd.DataFrame(out)],axis=1)

def perf_ledger(obs):
    def val(stats,*names):
      for n in names:
        v=(stats or {}).get(n)
        if v is not None:
          try:return float(v)
          except:return 0.
      return 0.
    rows=[]
    for r in obs:
      if not r.get('player_uuid') or r.get('minutes') is None:continue
      s=r.get('stats') or {};mins=float(r['minutes'] or 0.)
      goals=val(s,'goals');ass=val(s,'assists','goal_assist');xg=val(s,'expected_goals','xg');xa=val(s,'expected_assists','xa')
      de=val(s,'tackles_won')+val(s,'interceptions')+val(s,'recoveries')+val(s,'blocks')+val(s,'clearances')
      saves=val(s,'saves');gp=val(s,'goals_prevented');gc=val(s,'goals_conceded');disp=val(s,'dispossessed')
      rating=val(s,'rating_title','rating')
      rows.append(dict(player_uuid=str(r['player_uuid']),match_id=str(r['match_id']),available_at=pd.to_datetime(r['available_at_proxy'],utc=True),
        tournament=str(r.get('competition') or ''),minutes_played=mins,goal_assist=goals+ass,xgi=xg+xa,
        shots_on_target=val(s,'shots_on_target'),chances_created=val(s,'chances_created','key_passes'),
        successful_dribbles=val(s,'successful_dribbles'),def_actions=de,accurate_passes_percent=val(s,'accurate_passes_percent'),
        gk_actions=saves,goals_prevented=gp,goals_conceded=gc,dispossessed=disp,rating_proxy=rating))
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--derived',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();derived=Path(a.derived);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    deadlines={int(r['gw']):pd.to_datetime(r['cutoff'],utc=True) for r in json.loads((derived/'deadlines.json').read_text())}
    cands=jsonl_gz(derived/'deadline_player_candidates.jsonl.gz')
    con=sqlite3.connect(Path(a.db));frame,base_model,base_cols=build_baseline(con,'2024-25',deadlines);con.close()
    role,work,obs,role_games,work_games=build_histories(derived,cands)
    frame=add_role_work(frame,role,work)
    frame=add_sequence_features(frame)
    ledger=perf_ledger(obs)
    if len(ledger):frame=add_perf_features(frame,ledger)
    else:raise ValueError('no performance ledger')
    ratings=pd.read_csv(derived/'player_match_ratings.csv.gz')
    frame=build_rating_features(frame,ratings)
    # Exact Team News is unavailable: locked policy treats UNKNOWN as neutral.
    frame['team_news_state']='UNKNOWN';frame['team_news_scoped_chance']=np.nan
    frame['team_news_known']=0;frame['team_news_hard_out']=0;frame['team_news_age_hours']=np.nan;frame['team_news_source']='UNAVAILABLE_2024_25'
    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    rows=[];audit=[]
    for gw in range(6,39):
      val=frame.gw.eq(gw).to_numpy()
      if not val.any():raise ValueError(f'missing GW{gw}')
      cut=pd.to_datetime(frame.loc[val,'cutoff'],utc=True).min()
      train=((frame.gw<gw)&(known<cut)).to_numpy()
      feat,p_locked,x_locked,p_pre,p_news,x_news,q,sub,met=evaluate_news_variant(frame,train,val,POLICY)
      part=feat.loc[val,['fixture_uuid','player_uuid','team_id','gw','team','player','pos','cutoff','outcome_known_at',
        'start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench','y','minutes']].copy()
      part['new_p_start']=np.asarray(p_news)[val];part['new_xmins']=np.asarray(x_news)[val]
      part['new_q_sub']=np.asarray(q)[val];part['new_sub_minutes']=np.asarray(sub)[val];part['new_start_minutes']=part.start_minutes_mean.astype(float)
      rows.append(part);audit.append(dict(gw=gw,cutoff=str(cut),train_rows=int(train.sum()),target_rows=int(val.sum()),
        state_log_loss=float(met['state_log_loss']),xmins_rmse=float(met['xmins_rmse'])))
      print(f'GW{gw}: train={train.sum()} target={val.sum()}',flush=True)
    pred=pd.concat(rows,ignore_index=True);pred.to_csv(out/'locked_mm_predictions.csv.gz',index=False,compression='gzip')
    frame.to_csv(out/'conditional_feature_frame.csv.gz',index=False,compression='gzip')
    pd.DataFrame(audit).to_csv(out/'walkforward_audit.csv',index=False)
    summary=dict(classification='CONDITIONAL_ROBUSTNESS_REPLAY_MM_NOT_STRICT',season='2024-25',policy=POLICY,
      model_math_changed=False,retuned=False,role_geometry_proxy='formation structural slots; measured average positions unavailable',
      team_news='UNKNOWN neutral; exact predeadline timing unavailable',history_timing='kickoff+4h proxy',
      baseline_training_overlap='Frozen P(start) coefficients were originally fit on 2023-24 + 2024-25; replay does not refit them, but this is not independent OOS',
      role_games=int(role_games),workload_team_games=int(work_games),rows=int(len(pred)),forecast_gws=[6,38])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
