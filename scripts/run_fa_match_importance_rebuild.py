#!/usr/bin/env python3
"""Recover 2025/26 FA Cup workload, rebuild workload features, and audit Match Importance.

This is a historical reconstruction experiment. FA Cup match/lineup data are
retrieved from FotMob's public JSON endpoints. FPL player IDs and team IDs
are anchored to a pinned FPL-Core-Insights snapshot. Match outcomes are made
available at kickoff+3h, matching the existing historical workload proxy.

Match Importance is NOT added as a common player intercept. It only interacts
with role hierarchy H through competition-value, stage and opponent-strength
terms, as specified by the model design.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy.special import expit, logit
from scipy.optimize import brentq
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from fpl_v1_1_model.workload import WorkloadHistory,WORKLOAD_FEATURES
from fpl_v1_1_model.match_importance import (
    BASE_COMPETITION_VALUES,canonical_competition,dynamic_competition_value,
    premier_league_stage_strength,opponent_strength_from_elo,hierarchy_interactions
)
from fpl_v1_1_model.minutes_decomposition import compose_expected_minutes
from build_reproducible_role_benchmark import (
    BASE_FEATURES,ROLE_FEATURES,write_json,write_prediction_csv
)

OUT=ROOT/'analysis/results/fa-match-importance-20261006-v1'
SOURCE_COMMIT='1c9191ab6b0c191378ea27f257fdab2bae63caba'
SOURCE_REPO='olbauday/FPL-Core-Insights'
FOTMOB_FA_LEAGUE=132
FOTMOB='https://www.fotmob.com/api/data'
FA_COMP='fa-cup'

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or ''))
    s=''.join(c for c in s if not unicodedata.combining(c)).lower()
    s=s.replace('&','and')
    return re.sub(r'[^a-z0-9]+','',s)

def get_json(url,session,tries=4):
    err=None
    for _ in range(tries):
        try:
            r=session.get(url,timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            err=e
    raise RuntimeError(f'GET failed {url}: {err}')

def get_csv(path,session):
    url=f'https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_COMMIT}/{path}'
    r=session.get(url,timeout=30);r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))

def fotmob_minutes(value):
    """Recursively find a FotMob per-player minutes field."""
    if isinstance(value,dict):
        for k,v in value.items():
            nk=norm(k)
            if nk in ('minutesplayed','minsplayed') and isinstance(v,(int,float)):
                return float(v)
            if nk in ('minutesplayed','minsplayed') and isinstance(v,dict):
                for kk in ('value','stat'):
                    z=v.get(kk)
                    if isinstance(z,(int,float)): return float(z)
            z=fotmob_minutes(v)
            if z is not None:return z
    elif isinstance(value,list):
        for v in value:
            z=fotmob_minutes(v)
            if z is not None:return z
    return None

def team_aliases(teams):
    aliases={}
    for r in teams.itertuples(index=False):
        vals=[getattr(r,'name',None),getattr(r,'short_name',None),getattr(r,'fotmob_name',None)]
        if int(r.id)==4: vals+=['Bournemouth','AFC Bournemouth']
        if int(r.id)==16: vals+=['Nottingham Forest',"Nott'm Forest"]
        if int(r.id)==18: vals+=['Tottenham','Tottenham Hotspur','Spurs']
        if int(r.id)==20: vals+=['Wolves','Wolverhampton','Wolverhampton Wanderers']
        if int(r.id)==13: vals+=['Manchester City','Man City']
        if int(r.id)==14: vals+=['Manchester United','Man Utd']
        for v in vals:
            if v: aliases[norm(v)]=r
    return aliases

def player_indexes(players):
    by_team={};global_full={}
    for r in players.itertuples(index=False):
        full=norm(f'{r.first_name} {r.second_name}')
        web=norm(r.web_name);second=norm(r.second_name)
        keys={full,web}
        d=by_team.setdefault(int(r.team_code),{})
        for k in keys:
            if k:d.setdefault(k,set()).add(int(r.player_id))
        if second:d.setdefault('second:'+second,set()).add(int(r.player_id))
        if full:global_full.setdefault(full,set()).add(int(r.player_id))
    return by_team,global_full

def map_player(name,team_code,by_team,global_full):
    k=norm(name);d=by_team.get(int(team_code),{})
    ids=d.get(k,set())
    if len(ids)==1:return next(iter(ids)),'team_exact'
    ids=global_full.get(k,set())
    if len(ids)==1:return next(iter(ids)),'global_full_exact'
    bits=re.findall(r'[A-Za-zÀ-ÿ]+',str(name or ''))
    if bits:
        ids=d.get('second:'+norm(bits[-1]),set())
        if len(ids)==1:return next(iter(ids)),'team_unique_surname'
    return None,'unresolved'

def recover_fa(session,teams,players):
    aliases=team_aliases(teams);by_team,global_full=player_indexes(players)
    url=f'{FOTMOB}/leagues?id={FOTMOB_FA_LEAGUE}&season=2025%2F2026'
    league=get_json(url,session)
    fixtures=(league.get('fixtures') or {}).get('allMatches') or []
    games=[];people=[];unresolved=[];used=[]
    for e in fixtures:
        status=e.get('status') or {}
        if not status.get('finished'):continue
        home=e.get('home') or {};away=e.get('away') or {}
        mapped=[]
        for side,t in [('home',home),('away',away)]:
            local=aliases.get(norm(t.get('name') or t.get('shortName')))
            if local is not None:mapped.append((side,t,local))
        if not mapped:continue
        match_id_raw=str(e.get('id') or '')
        if not match_id_raw:continue
        ko=pd.to_datetime(status.get('utcTime'),utc=True,errors='coerce')
        if pd.isna(ko):continue
        known=ko+pd.Timedelta(hours=3)
        detail=get_json(f'{FOTMOB}/matchDetails?matchId={match_id_raw}',session)
        content=detail.get('content') or {}
        lineup=content.get('lineup') or {}
        pstats=content.get('playerStats') or {}
        round_name=str(e.get('roundName') or e.get('round') or (detail.get('general') or {}).get('matchRound') or '')
        reason=(status.get('reason') or {}).get('short','')
        max_minutes=120.0 if reason in ('AET','Pen') else 90.0
        used.append(e)
        for side,t,local in mapped:
            block=lineup.get(side+'Team') or {}
            starters=block.get('starters') or []
            subs=block.get('subs') or []
            rows=[(x,True) for x in starters]+[(x,False) for x in subs]
            mapped_n=0;missing_starters=0
            mid=f'fa-fotmob-{match_id_raw}'
            for item,started in rows:
                pname=item.get('name') or ''
                pid=item.get('id')
                statrow=pstats.get(str(pid),{}) if isinstance(pstats,dict) else {}
                mins=fotmob_minutes(statrow)
                if mins is None:mins=fotmob_minutes(item)
                if mins is None:
                    on=item.get('timeSubbedOn');off=item.get('timeSubbedOff')
                    if started:
                        if isinstance(off,(int,float)):mins=float(off)
                        else:mins=max_minutes
                    else:
                        if isinstance(on,(int,float)):mins=max(0.0,max_minutes-float(on))
                        else:mins=0.0
                mins=float(mins)
                if not np.isfinite(mins) or mins<0 or mins>120:
                    if started:missing_starters+=1
                    continue
                fpl_id,rule=map_player(pname,int(local.code),by_team,global_full)
                if fpl_id is None:
                    unresolved.append(dict(event_id=int(match_id_raw),team_id=int(local.id),team=str(local.name),
                                           player=pname,started=started,minutes=mins))
                    if started:missing_starters+=1
                    continue
                mapped_n+=1
                people.append(dict(match_id=mid,source_event_id=int(match_id_raw),team_id=int(local.id),
                                   team_code=int(local.code),fpl_player_id=int(fpl_id),player_name=pname,
                                   kickoff=ko.isoformat(),available_at=known.isoformat(),competition=FA_COMP,
                                   started=started,minutes=mins,mapping_rule=rule,round_name=round_name))
            games.append(dict(match_id=mid,source_event_id=int(match_id_raw),team_id=int(local.id),
                              team_code=int(local.code),competition=FA_COMP,kickoff=ko.isoformat(),
                              available_at=known.isoformat(),mapped_players=mapped_n,
                              complete_player_stats=(missing_starters==0 and len(starters)==11),
                              missing_starter_stats=missing_starters,round_name=round_name,
                              opponent=str((away if side=='home' else home).get('name') or ''),
                              source='FotMob public JSON; historical kickoff+3h availability proxy'))
    g=pd.DataFrame(games)
    p=pd.DataFrame(people)
    u=pd.DataFrame(unresolved)
    if g.empty or p.empty:raise RuntimeError('FA Cup recovery produced no PL-club workload')
    g=g.drop_duplicates(['match_id','team_id']).sort_values(['kickoff','match_id','team_id'])
    p=p.drop_duplicates(['match_id','team_id','fpl_player_id']).sort_values(['kickoff','match_id','team_id','fpl_player_id'])
    return g,p,u,used

def build_fpl_uuid_map():
    cls=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv')
    line=[]
    for gw in range(1,39):
        f=ROOT/f'data_v1_1/raw/fpl-core-2025-26/GW{gw}/lineups.csv'
        if f.exists():
            x=pd.read_csv(f);x=x[x.is_starting.astype(str).str.lower().isin(['true','1','yes'])].copy()
            line.append(x[['match_id','player_id','player_name']])
    raw=pd.concat(line,ignore_index=True).dropna(subset=['player_id'])
    name_col='player' if 'player' in cls.columns else 'player_name'
    j=raw.merge(cls[['match_id','player_uuid',name_col]],left_on=['match_id','player_name'],
                right_on=['match_id',name_col],how='inner')
    pairs=j[['player_id','player_uuid']].drop_duplicates()
    bad=pairs.groupby('player_id').player_uuid.nunique()
    bad=set(bad[bad>1].index)
    pairs=pairs[~pairs.player_id.isin(bad)]
    return {int(r.player_id):str(r.player_uuid) for r in pairs.itertuples(index=False)}

def rebuild_workload_features(fa_games,fa_people,uuid_map):
    base=ROOT/'analysis/results/workload-recovered-v4'
    coverage=pd.read_csv(base/'team_match_coverage.csv')
    people=pd.read_csv(base/'official_player_minutes.csv')
    history=WorkloadHistory()
    pgroups={(m,int(t)):g for (m,t),g in people.groupby(['match_id','team_id'])}
    seen=set()
    for r in coverage.itertuples(index=False):
        key=(str(r.match_id),int(r.team_id))
        if key in seen:continue
        seen.add(key);group=pgroups.get(key,people.iloc[:0])
        players={str(x.player_uuid):{'minutes':float(x.minutes),
                 'started':None if pd.isna(x.started) else bool(x.started)} for x in group.itertuples(index=False)}
        history.add_game(int(r.team_id),str(r.match_id),str(r.kickoff),str(r.available_at),
                         canonical_competition(r.competition),players,bool(r.complete_player_stats))
    mapped=[];missing_uuid=0
    for r in fa_people.itertuples(index=False):
        uid=uuid_map.get(int(r.fpl_player_id))
        if uid is None:
            missing_uuid+=1;continue
        mapped.append({**r._asdict(),'player_uuid':uid})
    fm=pd.DataFrame(mapped)
    fgroups={(m,int(t)):g for (m,t),g in fm.groupby(['match_id','team_id'])} if len(fm) else {}
    for r in fa_games.itertuples(index=False):
        key=(str(r.match_id),int(r.team_id));group=fgroups.get(key,pd.DataFrame())
        pp={}
        if len(group):
            for x in group.itertuples(index=False):
                pp[str(x.player_uuid)]={'minutes':float(x.minutes),'started':bool(x.started)}
        history.add_game(int(r.team_id),str(r.match_id),str(r.kickoff),str(r.available_at),
                         FA_COMP,pp,bool(r.complete_player_stats))
    frame=pd.read_csv(base/'all_features.csv.gz')
    cache={};records=[]
    for r in frame.itertuples(index=False):
        key=(int(r.team_id),str(r.cutoff))
        if key not in cache:cache[key]=history.state(int(r.team_id),str(r.cutoff))
        state,default,known=cache[key]
        vals=state.get(str(r.player_uuid),default).copy()
        vals['work_max_history_known_at_fa']=known.isoformat() if known else ''
        records.append(vals)
    rec=pd.DataFrame(records)
    for c in WORKLOAD_FEATURES:frame[c]=rec[c].to_numpy()
    frame['work_max_history_known_at_fa']=rec['work_max_history_known_at_fa']
    return frame,fm,missing_uuid

def source_schedule(session,teams,fa_games):
    # Use the audited frozen all-GW source already stored in this repository.
    # Those 38 folders form the historical season ledger used by workload;
    # relying on one remote GW snapshot could silently omit earlier cups/Europe.
    parts=[]
    raw=ROOT/'data_v1_1/raw/all-competitions-2025-26'
    for p in sorted(raw.glob('GW*/matches.csv')):
        parts.append(pd.read_csv(p))
    sched=pd.concat(parts,ignore_index=True)
    if sched.match_id.duplicated().any():
        raise ValueError('Frozen all-competition schedule contains duplicate match IDs')
    sched['competition']=sched.tournament.map(canonical_competition)
    sched['kickoff']=pd.to_datetime(sched.kickoff_time,utc=True,errors='coerce')
    code_to_id={int(r.code):int(r.id) for r in teams.itertuples(index=False)}
    rows=[]
    for r in sched.itertuples(index=False):
        for side in ('home','away'):
            code=getattr(r,side+'_team')
            if pd.isna(code) or int(code) not in code_to_id:continue
            opp=getattr(r,('away' if side=='home' else 'home')+'_team')
            opp_elo=getattr(r,('away' if side=='home' else 'home')+'_team_elo')
            rows.append(dict(match_id=str(r.match_id),team_id=code_to_id[int(code)],
                             competition=str(r.competition),kickoff=r.kickoff,
                             opponent_elo=opp_elo,gameweek=r.gameweek))
    x=pd.DataFrame(rows)
    # FA rows supply active-competition timing; opponent Elo is unavailable here.
    add=fa_games[['match_id','team_id','competition','kickoff']].copy()
    add['kickoff']=pd.to_datetime(add.kickoff,utc=True);add['opponent_elo']=np.nan;add['gameweek']=np.nan
    return pd.concat([x,add],ignore_index=True)

def add_match_importance(frame,schedule,cls,eta):
    matchmap=cls[['fixture_uuid','match_id']].drop_duplicates()
    if matchmap.fixture_uuid.duplicated().any():raise ValueError('fixture->match mapping ambiguous')
    frame=frame.merge(matchmap,on='fixture_uuid',how='left',validate='many_to_one')
    target=schedule[schedule.competition.eq('prem')][['match_id','team_id','opponent_elo']].drop_duplicates(['match_id','team_id'])
    frame=frame.merge(target,on=['match_id','team_id'],how='left',validate='many_to_one')
    # Season-start opportunity sets are qualification facts, not future outcomes.
    participation={int(t):set(g.competition) for t,g in schedule.groupby('team_id')}
    last=schedule.dropna(subset=['kickoff']).groupby(['team_id','competition']).kickoff.max().to_dict()
    compvals=[];stages=[];opps=[];counts=[];euro=[]
    for r in frame.itertuples(index=False):
        cut=pd.Timestamp(r.cutoff)
        active=[]
        for c in participation.get(int(r.team_id),{'prem','fa-cup','efl-cup'}):
            end=last.get((int(r.team_id),c))
            if end is None or cut < end+pd.Timedelta(hours=3):active.append(c)
        # PL, FA Cup and EFL Cup participation is known for every PL club.
        for c in ('prem','fa-cup','efl-cup'):
            end=last.get((int(r.team_id),c))
            if c not in active and (end is None or cut < end+pd.Timedelta(hours=3)):active.append(c)
        cv=dynamic_competition_value('prem',active,BASE_COMPETITION_VALUES,eta=eta)
        compvals.append(cv);stages.append(premier_league_stage_strength(int(r.gw)))
        opps.append(opponent_strength_from_elo(r.opponent_elo));counts.append(len(set(active)))
        euro.append(int(any(c in active for c in ('champions-league','europa-league','conference-league'))))
    frame['mi_competition_value']=compvals;frame['mi_stage_strength']=stages
    frame['mi_opponent_strength']=opps;frame['mi_active_competitions']=counts;frame['mi_europe_active']=euro
    ints=[hierarchy_interactions(hf,hs,cv,st,op) for hf,hs,cv,st,op in zip(
        frame.role_h_fast,frame.role_h_slow,compvals,stages,opps)]
    inter=pd.DataFrame(ints,index=frame.index)
    for c in inter:frame[c]=inter[c]
    return frame

def normalize11(frame,p):
    out=np.asarray(p,float).copy()
    for idx in frame.groupby(['fixture_uuid','team_id'],sort=False).indices.values():
        z=logit(np.clip(out[idx],1e-7,1-1e-7))
        shift=brentq(lambda b:expit(z+b).sum()-11,-40,40)
        out[idx]=expit(z+shift)
    return out

def metrics(frame,p):
    y=frame.y.to_numpy(float);mins=frame.minutes.to_numpy(float)
    p=np.clip(np.asarray(p,float),1e-9,1-1e-9)
    xm=compose_expected_minutes(p,frame.start_minutes_mean,frame.p_cameo_given_bench,frame.cameo_minutes_mean)
    e=xm-mins
    return dict(n=len(frame),brier=float(np.mean((p-y)**2)),
      log_loss=float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),
      xmins_mae=float(np.mean(np.abs(e))),xmins_rmse=float(np.sqrt(np.mean(e**2))),
      xmins_bias=float(np.mean(e)))

def fit_eval(frame,train,test,features):
    model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=2000,random_state=0))
    model.fit(frame.loc[train,features],frame.loc[train,'y'])
    p=normalize11(frame,model.predict_proba(frame[features])[:,1])
    return p[test],metrics(frame.loc[test],p[test]),model

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (FPL historical model audit)'})
    teams=get_csv('data/2025-2026/By Gameweek/GW38/teams.csv',s)
    players=get_csv('data/2025-2026/By Gameweek/GW38/players.csv',s)
    fa_games,fa_people,unresolved,events=recover_fa(s,teams,players)
    fa_games.to_csv(OUT/'fa_team_games.csv',index=False);fa_people.to_csv(OUT/'fa_player_minutes.csv',index=False)
    unresolved.to_csv(OUT/'fa_unresolved_players.csv',index=False)
    uuid_map=build_fpl_uuid_map()
    frame,mapped_fa,missing_uuid=rebuild_workload_features(fa_games,fa_people,uuid_map)
    mapped_fa.to_csv(OUT/'fa_player_minutes_uuid.csv',index=False)
    cls=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv')
    schedule=source_schedule(s,teams,fa_games)
    schedule.to_csv(OUT/'competition_schedule_for_importance.csv',index=False)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev_test=frame.gw.between(16,21);dev_cut=pd.to_datetime(frame.loc[dev_test,'cutoff'],utc=True).min()
    dev_train=frame.gw.between(6,15)&(known<dev_cut)
    final_test=frame.gw.between(22,38);final_cut=pd.to_datetime(frame.loc[final_test,'cutoff'],utc=True).min()
    final_train=frame.gw.between(6,21)&(known<final_cut)
    base=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
    mi_cols=['mi_h_fast_comp','mi_h_fast_stage','mi_h_fast_opp','mi_h_slow_comp','mi_h_slow_stage','mi_h_slow_opp']

    candidates=[]
    frames={}
    for eta in (0.20,0.35,0.50):
        f=add_match_importance(frame.copy(),schedule,cls,eta)
        _,control,_=fit_eval(f,dev_train,dev_test,base)
        _,mi,_=fit_eval(f,dev_train,dev_test,base+mi_cols)
        candidates.append(dict(eta=eta,control_log_loss=control['log_loss'],mi_log_loss=mi['log_loss'],
                               control_xmins_rmse=control['xmins_rmse'],mi_xmins_rmse=mi['xmins_rmse'],
                               delta_log_loss=mi['log_loss']-control['log_loss'],
                               delta_xmins_rmse=mi['xmins_rmse']-control['xmins_rmse']))
        frames[eta]=f
    cand=pd.DataFrame(candidates).sort_values(['mi_log_loss','mi_xmins_rmse'])
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    eta=float(cand.iloc[0].eta);f=frames[eta]
    pc,mc,_=fit_eval(f,final_train,final_test,base)
    pm,mm,_=fit_eval(f,final_train,final_test,base+mi_cols)
    evalf=f.loc[final_test].copy();evalf['control_p_start']=pc;evalf['mi_p_start']=pm
    evalf['control_xmins']=compose_expected_minutes(pc,evalf.start_minutes_mean,evalf.p_cameo_given_bench,evalf.cameo_minutes_mean)
    evalf['mi_xmins']=compose_expected_minutes(pm,evalf.start_minutes_mean,evalf.p_cameo_given_bench,evalf.cameo_minutes_mean)
    keep=['fixture_uuid','player_uuid','team_id','team','player','gw','pos','y','minutes',
          'control_p_start','mi_p_start','control_xmins','mi_xmins','mi_competition_value',
          'mi_stage_strength','mi_opponent_strength','mi_active_competitions','mi_europe_active']+WORKLOAD_FEATURES
    write_prediction_csv(evalf[keep],OUT/'diagnostic_predictions.csv.gz')
    write_prediction_csv(f,OUT/'all_features_fa_mi.csv.gz')
    slices=[]
    for label,mask in [
        ('all',np.ones(len(evalf),dtype=bool)),
        ('europe_active',evalf.mi_europe_active.eq(1).to_numpy()),
        ('no_europe_active',evalf.mi_europe_active.eq(0).to_numpy()),
        ('3plus_active_comps',evalf.mi_active_competitions.ge(3).to_numpy()),
        ('2_or_fewer_active_comps',evalf.mi_active_competitions.le(2).to_numpy()),
        ('recent_nonpl',evalf.work_team_nonpl_matches_7d.gt(0).to_numpy())]:
        g=evalf.loc[mask]
        if g.empty:continue
        slices.append(dict(slice=label,arm='control',**metrics(g,g.control_p_start)))
        slices.append(dict(slice=label,arm='match_importance',**metrics(g,g.mi_p_start)))
    pd.DataFrame(slices).to_csv(OUT/'diagnostic_slices.csv',index=False)
    summary=dict(
      classification='FA Cup workload + hierarchy-modulated Match Importance exploratory rebuild',
      source=dict(fpl_core_commit=SOURCE_COMMIT,fotmob_fa_league=FOTMOB_FA_LEAGUE,
                  historical_availability='kickoff+3h proxy, same convention as existing workload'),
      fa_cup=dict(events_seen=len(events),pl_team_games=len(fa_games),player_rows=len(fa_people),
                  mapped_uuid_rows=len(mapped_fa),unresolved_rows=len(unresolved),missing_uuid_after_fpl_mapping=missing_uuid,
                  complete_team_games=int(fa_games.complete_player_stats.sum())),
      match_importance=dict(
        design='competition value + stage + opponent strength; interactions with role hierarchy only; no additive team-wide player intercept',
        base_values=BASE_COMPETITION_VALUES,selected_eta=eta,development=cand.to_dict(orient='records'),
        reused_diagnostic={'control':mc,'match_importance':mm,
          'delta':{k:mm[k]-mc[k] for k in ('brier','log_loss','xmins_mae','xmins_rmse','xmins_bias')}}),
      promoted=False,
      warning='GW22-38 is reused diagnostic. Establishes data/implementation and diagnoses effect; independent validation remains required before production promotion.')
    write_json(OUT/'summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
