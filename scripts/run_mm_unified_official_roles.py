#!/usr/bin/env python3
"""Build and evaluate the agreed unified Minute Model (MM) role history.

Scope is MM only. PM and TS are untouched.

Key changes versus the current combined candidate:
- official PL + Europe + EFL + recovered FA Cup can update q/H;
- non-PL role evidence is accepted only for verified 11-player formations;
- Match Importance weights historical role evidence, especially H;
- q receives a smaller importance weight than H;
- workload keeps the recovered FA Cup additions;
- current performance/substate/duration components are retained and refit on the
  unified feature table so the whole MM is evaluated as one pipeline.

GW16-21 selects only q/H importance strength. GW22-38 remains a reused
diagnostic and cannot be called independent OOS.
"""
from __future__ import annotations
import json,re,sys,unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.special import expit,logit
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.role_history import RoleHistory,summarize_state
from fpl_v1_1_model.role_classifier import ROLES,template,canonical
from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from fpl_v1_1_model.match_importance import (
    BASE_COMPETITION_VALUES,canonical_competition,dynamic_competition_value,
    premier_league_stage_strength,knockout_stage_strength,opponent_strength_from_elo
)
from fpl_v1_1_model.pstart_v2 import match_importance,MatchImportanceParams
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES,normalize_eleven,write_json
from fpl_v1_1_model.minutes_decomposition import component_inputs
from run_v4_performance_rating_experiment import (
    build_perf_ledger,add_features as add_perf_features,fit_offset as fit_perf_offset,
    FAMILIES as PERF_FAMILIES
)
from run_v4_three_state_sequence_experiment import (
    add_sequence_features,fit_q,BASE_Q_FEATURES,SEQ_FEATURES,metrics,write_gzip_csv
)
from run_v4_three_state_duration_experiment import fit_duration

SOURCE=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
OLD=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'
CLASSIFIED=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
FA_DIR=ROOT/'analysis/results/fa-match-importance-20261006-v1'
OUT=ROOT/'analysis/results/mm-unified-official-roles-20261006-v1'
FOTMOB='https://www.fotmob.com/api/data'
PERF_L2=.5;Q_C=4.;Q_ALPHA=.75;RIDGE=80.;SUB_BLEND=.5
PARAM_GRID=[(0.0,0.0),(0.10,0.40),(0.20,0.65),(0.25,0.80),(0.35,1.0)]
MI_PARAMS=MatchImportanceParams(intercept=-1.0,competition_coef=1.0,round_coef=1.0,opponent_coef=1.0,scarcity_eta=.35)

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or ''))
    s=''.join(c for c in s if not unicodedata.combining(c)).lower().replace('&','and')
    return re.sub(r'[^a-z0-9]+','',s)

def read_all(name):
    parts=[pd.read_csv(p) for p in sorted(RAW.glob('GW*/'+name+'.csv'))]
    x=pd.concat(parts,ignore_index=True)
    return x.drop_duplicates()

def structural_roles(formation,group):
    starters=group[group.is_starting.astype(str).str.lower().isin(['true','1','yes'])].copy()
    if len(starters)!=11 or starters.player_uuid.isna().any():return None
    patterns=template(str(formation))
    flat=['GK']+[r for line in patterns for r in line]
    if len(flat)!=11:return None
    pos=starters.position.astype(str).str.upper().tolist()
    if not pos or pos[0] not in ('G','GK'):return None
    return {str(pid):canonical(role) for pid,role in zip(starters.player_uuid.astype(str),flat)}

def base_identity(lines,classified):
    anchors=lines[lines.match_id.str.contains('-prem-') & lines.player_id.notna()]
    aliases={key:set(g.player_id.astype(int)) for key,g in anchors.groupby(['team_code','player_name'])}
    fpl_to_uuid={}
    j=anchors.merge(classified[['match_id','player_uuid','player']].rename(columns={'player':'player_name'}),
                    on=['match_id','player_name'],how='inner')
    for fid,g in j.groupby('player_id'):
        vals=set(g.player_uuid.astype(str))
        if len(vals)==1:fpl_to_uuid[int(fid)]=next(iter(vals))
    for idx,r in lines[lines.player_id.isna() & lines.team_code.notna()].iterrows():
        choices=aliases.get((r.team_code,r.player_name),set())
        if len(choices)==1:lines.loc[idx,'player_id']=next(iter(choices))
    lines['player_uuid']=lines.player_id.map(fpl_to_uuid)
    aligned=lines.merge(classified[['match_id','player_uuid','team_id']].drop_duplicates(),on=['match_id','player_uuid'])
    pairs=aligned[['team_code','team_id']].dropna().drop_duplicates()
    pairs=pairs[~pairs.team_code.duplicated(keep=False)]
    return lines,{int(r.team_code):int(r.team_id) for r in pairs.itertuples()}

def schedule_records(matches,team_map):
    records=[]
    for r in matches.itertuples(index=False):
        comp=canonical_competition(r.tournament)
        ko=pd.to_datetime(r.kickoff_time,utc=True,errors='coerce')
        if pd.isna(ko):continue
        for side in ('home','away'):
            code=getattr(r,side+'_team')
            if pd.isna(code) or int(code) not in team_map:continue
            opp_side='away' if side=='home' else 'home'
            opp_code=getattr(r,opp_side+'_team')
            opp_elo=getattr(r,opp_side+'_team_elo')
            gf=getattr(r,side+'_score');ga=getattr(r,opp_side+'_score')
            records.append(dict(match_id=str(r.match_id),team_id=team_map[int(code)],competition=comp,
                kickoff=ko,available_at=ko+pd.Timedelta(hours=3),round_name='',
                opponent=str(opp_code),opponent_elo=opp_elo,gf=gf,ga=ga,
                source='frozen-all-competitions'))
    return records

def fetch_fa_roles(session,fa_people):
    # Map only already audited FA identities; never fuzzy-remap here.
    byevent={}
    for (event,team),g in fa_people.groupby(['source_event_id','team_id']):
        d={}
        for r in g.itertuples(index=False):d.setdefault(norm(r.player_name),set()).add(str(r.player_uuid))
        byevent[(int(event),int(team))]=d
    games=pd.read_csv(FA_DIR/'fa_team_games.csv')
    out=[];skipped=[]
    for event,g0 in games.groupby('source_event_id'):
        detail=session.get(f'{FOTMOB}/matchDetails?matchId={int(event)}',timeout=30).json()
        lineup=(detail.get('content') or {}).get('lineup') or {}
        general=detail.get('general') or {}
        home_id=norm((general.get('homeTeam') or {}).get('name') or '')
        for r in g0.itertuples(index=False):
            # identify side by matching audited opponent/team against block names if available;
            # fallback to event side order using team names from lineup metadata.
            chosen=None
            for key in ('homeTeam','awayTeam'):
                b=lineup.get(key) or {}
                names=[x.get('name','') for x in (b.get('starters') or [])]
                amap=byevent.get((int(event),int(r.team_id)),{})
                hits=sum(norm(n) in amap for n in names)
                if hits>=8:chosen=(key,b);break
            if chosen is None:
                skipped.append({'event':int(event),'team_id':int(r.team_id),'reason':'cannot identify lineup side'})
                continue
            key,b=chosen;formation=b.get('formation') or b.get('formationString') or ''
            starters=b.get('starters') or []
            pats=template(str(formation));flat=['GK']+[q for line in pats for q in line]
            if len(starters)!=11 or len(flat)!=11:
                skipped.append({'event':int(event),'team_id':int(r.team_id),'reason':'no verified 11-slot formation'})
                continue
            amap=byevent[(int(event),int(r.team_id))];players=[];ok=True
            for item,role in zip(starters,flat):
                ids=amap.get(norm(item.get('name','')),set())
                if len(ids)!=1:ok=False;break
                uid=next(iter(ids))
                row=fa_people[(fa_people.source_event_id==event)&(fa_people.team_id==r.team_id)&(fa_people.player_uuid==uid)]
                mins=float(row.minutes.iloc[0]) if len(row) else 0.
                players.append({'player_uuid':uid,'role':canonical(role),'started':True,'minutes':mins,'disagreement':False})
            if not ok:
                skipped.append({'event':int(event),'team_id':int(r.team_id),'reason':'starter identity incomplete'})
                continue
            ko=pd.to_datetime(r.kickoff,utc=True)
            out.append(dict(match_id=r.match_id,team_id=int(r.team_id),competition='fa-cup',kickoff=ko,
                available_at=pd.to_datetime(r.available_at,utc=True),round_name=str(r.round_name),
                opponent=str(r.opponent),opponent_elo=np.nan,gf=np.nan,ga=np.nan,
                source='fotmob-fa',players=players))
    return out,pd.DataFrame(skipped)

def build_role_games():
    classified=pd.read_csv(CLASSIFIED)
    actual=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/all_feature_predictions.csv.gz')[['fixture_uuid','player_uuid','minutes']].drop_duplicates()
    classified=classified.merge(actual,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    classified['kickoff']=pd.to_datetime(classified.kickoff,utc=True)
    matches=read_all('matches');lines=read_all('lineups')
    lines,team_map=base_identity(lines,classified)
    meta={x['match_id']+'|'+str(x['team_id']):x for x in schedule_records(matches,team_map)}

    workload=pd.read_csv(ROOT/'analysis/results/workload-recovered-v4/official_player_minutes.csv')
    wmins={(str(r.match_id),int(r.team_id),str(r.player_uuid)):float(r.minutes) for r in workload.itertuples(index=False)}
    games=[]
    # Preserve audited PL roles exactly.
    for (mid,team),g in classified.groupby(['match_id','team_id'],sort=False):
        key=str(mid)+'|'+str(int(team));m=meta.get(key)
        if m is None:continue
        players=[{'player_uuid':str(x.player_uuid),'role':canonical(x.final_role),'started':True,
                  'minutes':float(x.minutes) if pd.notna(x.minutes) else 0.0,
                  'disagreement':bool(x.disagreement)} for x in g.itertuples(index=False)]
        games.append({**m,'players':players})

    # Verified structural roles for cup/Europe source.
    nonpl=matches[matches.tournament!='prem']
    for m in nonpl.itertuples(index=False):
        lg=lines[lines.match_id==m.match_id]
        for side in ('home','away'):
            g=lg[lg.team_side==side].copy()
            codes=g.team_code.dropna().unique()
            if len(codes)!=1 or int(codes[0]) not in team_map:continue
            team=team_map[int(codes[0])]
            if g.empty:continue
            formation=str(g.formation.dropna().iloc[0]) if g.formation.notna().any() else ''
            roles=structural_roles(formation,g)
            if roles is None:continue
            players=[]
            for x in g[g.is_starting.astype(str).str.lower().isin(['true','1','yes'])].itertuples(index=False):
                uid=str(x.player_uuid);role=roles.get(uid)
                if not role:continue
                mins=wmins.get((str(m.match_id),int(team),uid))
                if mins is None:continue
                players.append({'player_uuid':uid,'role':role,'started':True,'minutes':float(mins),'disagreement':False})
            if len(players)!=11:continue
            md=meta.get(str(m.match_id)+'|'+str(team))
            if md:games.append({**md,'players':players})

    fa=pd.read_csv(FA_DIR/'fa_player_minutes_uuid.csv')
    s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (FPL MM audit)'})
    faroles,skipped=fetch_fa_roles(s,fa)
    games.extend(faroles)
    return games,skipped,classified

def add_importance(games):
    # Participation is a season-start/competition-entry fact; no target outcomes.
    participation=defaultdict(lambda:{'prem','fa-cup','efl-cup'})
    for g in games:participation[int(g['team_id'])].add(canonical_competition(g['competition']))
    active={t:set(v) for t,v in participation.items()}
    out=[];series=defaultdict(list)
    for g in sorted(games,key=lambda z:(z['kickoff'],z['match_id'],z['team_id'])):
        team=int(g['team_id']);comp=canonical_competition(g['competition'])
        aset=active[team]
        cv=dynamic_competition_value(comp,sorted(aset|{comp}),BASE_COMPETITION_VALUES,eta=.35)
        if comp=='prem':
            # Map date to a conservative league-progress stage without using future result.
            stage=max(.2,min(1.,.2+.8*((g['kickoff'].month-8)%12)/10.))
        else:
            stage=knockout_stage_strength(g.get('round_name'),g['kickoff'].month)
        opp=opponent_strength_from_elo(g.get('opponent_elo'))
        mi=match_importance(competition=comp,active_competitions=sorted(aset|{comp}),
            round_strength=stage,opponent_strength=opp,base_values=BASE_COMPETITION_VALUES,params=MI_PARAMS)
        z={**g,'importance':mi,'competition_value':cv,'stage_strength':stage,'opponent_strength':opp}
        out.append(z)
        # Cutoff-safe elimination updates only when the just-finished result is definitive.
        gf,ga=g.get('gf'),g.get('ga')
        lost=pd.notna(gf) and pd.notna(ga) and float(gf)<float(ga)
        if comp=='fa-cup' and lost:
            active[team].discard(comp)
        elif comp=='efl-cup' and lost:
            # Semis are two-legged; only declare elimination on a second Jan/Feb meeting.
            if g['kickoff'].month not in (1,2):active[team].discard(comp)
            else:
                k=(team,comp,str(g.get('opponent')))
                series[k].append((float(gf),float(ga)))
                if len(series[k])>=2:
                    F=sum(a for a,b in series[k]);A=sum(b for a,b in series[k])
                    if F<A:active[team].discard(comp)
        elif comp in ('champions-league','europa-league','conference-league') and lost and g['kickoff'].month>=2:
            k=(team,comp,str(g.get('opponent')))
            series[k].append((float(gf),float(ga)))
            if g['kickoff'].month>=5 and len(series[k])==1:active[team].discard(comp)
            elif len(series[k])>=2:
                F=sum(a for a,b in series[k]);A=sum(b for a,b in series[k])
                if F<A:active[team].discard(comp)
    return out

def role_features(frame,games,qscale,hscale):
    hist=RoleHistory()
    for g in games:
        hist.add_game(g['team_id'],g['available_at'],g['match_id'],g['players'],
                      importance=g['importance'],competition=g['competition'])
    cache={};rows=[]
    for r in frame.itertuples(index=False):
        cutoff=pd.to_datetime(r.cutoff,utc=True);key=(int(r.team_id),str(cutoff))
        if key not in cache:
            cache[key]={speed:hist.state(int(r.team_id),cutoff,half,q_importance_scale=qscale,
                       h_importance_scale=hscale,importance_floor=.35)
                        for speed,half in [('fast',3),('slow',10)]}
        rec={}
        for speed in ('fast','slow'):
            states,caps,known=cache[key][speed];st=states.get(str(r.player_uuid),{})
            sm=summarize_state(st,caps)
            for k,v in sm.items():
                if k.startswith('role_'):rec[f'{k}_{speed}']=v
            for fld in ('q','H'):
                vals=st.get(fld,{})
                for role in ROLES:rec[f'{fld}_{role}_{speed}']=vals.get(role,0.)
            if speed=='slow':
                q=st.get('q',{});rec['expected_role']=max(sorted(q),key=q.get) if q else 'UNKNOWN'
                rec['role_started_last_gw']=float(bool(known and any(
                    str(p['player_uuid'])==str(r.player_uuid) and p.get('started') for p in known[-1]['players'])))
        rows.append(rec)
    out=frame.copy();rf=pd.DataFrame(rows,index=out.index)
    for c in rf:out[c]=rf[c]
    for c in ROLE_FEATURES:
        if c not in out:out[c]=0.
    return out

def fit_base(frame,train):
    cols=BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES
    m=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0))
    m.fit(frame.loc[train,cols],frame.loc[train,'y'])
    return normalize_eleven(frame,m.predict_proba(frame[cols])[:,1])

def compose(frame,p,q,sub):
    return p*frame.start_minutes_mean.to_numpy(float)+(1-p)*q*np.asarray(sub,float)

def full_mm(frame,train):
    p0=fit_base(frame,train)
    p,perf=fit_perf_offset(frame,p0,train,PERF_FAMILIES['last'],PERF_L2)
    q0=np.clip(frame.p_cameo_given_bench.to_numpy(float),1e-6,1-1e-6)
    qhat,qm=fit_q(frame,train,BASE_Q_FEATURES+SEQ_FEATURES,Q_C)
    q=expit((1-Q_ALPHA)*logit(q0)+Q_ALPHA*logit(np.clip(qhat,1e-6,1-1e-6)))
    X=component_inputs(frame)
    for c in WORKLOAD_FEATURES+SEQ_FEATURES:X[c]=frame[c].to_numpy(float)
    for c in X:
        if c not in frame:frame[c]=X[c]
    subhat,sm=fit_duration(frame,train,'sub',list(X.columns),RIDGE)
    sub=(1-SUB_BLEND)*frame.cameo_minutes_mean.to_numpy(float)+SUB_BLEND*subhat
    xm=compose(frame,p,q,sub)
    return p,q,sub,xm,{'performance':perf,'q':qm,'sub_duration':sm}

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    frame=pd.read_csv(SOURCE).reset_index(drop=True)
    frame=add_sequence_features(frame)
    ledger=build_perf_ledger();frame=add_perf_features(frame,ledger)
    games,fa_skipped,classified=build_role_games()
    games=add_importance(games)
    pd.DataFrame([{k:v for k,v in g.items() if k!='players'}|{'role_players':len(g['players'])} for g in games]).to_csv(OUT/'official_role_games.csv',index=False)
    fa_skipped.to_csv(OUT/'fa_role_skipped.csv',index=False)

    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    dev=frame.gw.between(16,21).to_numpy();devcut=pd.to_datetime(frame.loc[dev,'cutoff'],utc=True).min()
    tr=(frame.gw.between(6,15)&(known<devcut)).to_numpy()
    candidates=[];dev_frames={}
    for qs,hs in PARAM_GRID:
        f=role_features(frame.copy(),games,qs,hs)
        p,q,sub,xm,_=full_mm(f,tr)
        met=metrics(f,dev,p,q,xm)
        candidates.append({'q_importance_scale':qs,'h_importance_scale':hs,**met})
        dev_frames[(qs,hs)]=f
    cand=pd.DataFrame(candidates).sort_values(['xmins_rmse','start_log_loss','xmins_mae'])
    cand.to_csv(OUT/'development_candidates.csv',index=False)
    best=cand.iloc[0];qs=float(best.q_importance_scale);hs=float(best.h_importance_scale)

    test=frame.gw.between(22,38).to_numpy();cut=pd.to_datetime(frame.loc[test,'cutoff'],utc=True).min()
    finaltr=(frame.gw.between(6,21)&(known<cut)).to_numpy()
    f=role_features(frame.copy(),games,qs,hs)
    p,q,sub,xm,models=full_mm(f,finaltr)
    met=metrics(f,test,p,q,xm)

    old=pd.read_csv(OLD)
    keys=['fixture_uuid','player_uuid','team_id','gw']
    ft=f.loc[test].reset_index(drop=True)
    old=ft[keys].merge(old[keys+['combined_p_start','combined_q_sub','combined_xmins']],on=keys,validate='one_to_one')
    oldmet=metrics(ft,np.ones(len(ft),dtype=bool),old.combined_p_start.to_numpy(float),
                   old.combined_q_sub.to_numpy(float),old.combined_xmins.to_numpy(float))
    # Compare exact same rows; state metrics use old q while xMins uses old saved xMins.
    delta={k:met[k]-oldmet[k] for k in met if k in oldmet and isinstance(met[k],(int,float))}

    pred=f.loc[test,['fixture_uuid','player_uuid','team_id','gw','team','player','pos','y','minutes','expected_role']].copy()
    pred['mm_p_start']=p[test];pred['mm_q_sub']=q[test];pred['mm_sub_minutes']=sub[test];pred['mm_xmins']=xm[test]
    write_gzip_csv(pred,OUT/'reused_diagnostic_predictions.csv.gz')

    by=[]
    for label,mask in [
      ('all',test),('europe_recent',test&(f.work_team_nonpl_matches_7d.to_numpy()>0)),
      ('uncertain_pstart',test&(p>=.2)&(p<=.8)),
      ('role_changed_recently',test&(f.role_started_last_gw.to_numpy()>0))]:
        if not mask.any():continue
        by.append({'slice':label,**metrics(f,mask,p,q,xm)})
    pd.DataFrame(by).to_csv(OUT/'diagnostic_slices.csv',index=False)

    comp=pd.DataFrame([{**{k:v for k,v in g.items() if k not in ('players',)},'players':len(g['players'])} for g in games])
    coverage=comp.groupby('competition').agg(team_games=('match_id','size'),role_player_rows=('players','sum')).reset_index()
    coverage.to_csv(OUT/'role_coverage_by_competition.csv',index=False)
    result={
      'classification':'unified official-club-match MM candidate; GW22-38 reused diagnostic only',
      'selected_importance_weights':{'q':qs,'H':hs,'importance_floor':.35},
      'development_candidates':cand.to_dict(orient='records'),
      'role_coverage':coverage.to_dict(orient='records'),
      'fa_role_sides_skipped':int(len(fa_skipped)),
      'reused_diagnostic':{'old_combined':oldmet,'unified_mm':met,'delta_unified_minus_old':delta},
      'architecture':{
        'official_matches':'PL + verified CL/EL/Conference/EFL + verified FA role sides',
        'q':'recency-weighted role minutes with mild Match Importance weighting',
        'H':'recency-weighted role hierarchy with stronger Match Importance weighting',
        'match_importance':'dynamic competition value + stage + opponent strength on historical role evidence',
        'p_start':'role+workload logistic + retained last-match performance residual',
        'substate':'retained sequence-aware q model C=4, 75% logit blend',
        'start_duration':'retained frozen conditional starter duration',
        'sub_duration':'retained 50/50 frozen+sequence Ridge(alpha=80)',
        'exact_11':True},
      'promoted':False,
      'lock_rule':'Do not lock from reused diagnostic alone; this run establishes the agreed architecture and checks whether it behaves sensibly.'
    }
    write_json(OUT/'result.json',result);write_json(OUT/'frozen_models.json',models)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
