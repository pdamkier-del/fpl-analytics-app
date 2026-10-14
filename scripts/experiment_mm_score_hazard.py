#!/usr/bin/env python3
"""Observed 2024 goal paths train hazard; forecast paths always simulated, never actual."""
import argparse,gzip,hashlib,json,sqlite3,sys
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records
from audit_mm_components import metrics,score
NUM=['duration_h6','start_share6','team_rest_days','minutes_14d','season_progress']
SCORE=['lead','trail','lead_late','regular_lead_late']

def score_features(frame,diff,time):
    f=frame.copy();f['bin']=np.asarray(time)//5;f['season_progress']=f.gw/38.
    f['lead']=np.clip(diff,0,3);f['trail']=np.clip(-np.asarray(diff),0,3);f['lead_late']=f.lead*(np.asarray(time)>=60);f['regular_lead_late']=f.lead_late*f.start_share6
    return f

def prepare(out):
    f=pd.read_csv(out/'2024-25_features.csv.gz');lookup=f.set_index(['fixture_uuid','player_uuid']);raw=ROOT/'data_v1_1/raw/season_2024_25_v1/fotmob/details'
    with sqlite3.connect(ROOT/'work/core.sqlite3') as con:fx=pd.read_sql_query("SELECT * FROM fixtures WHERE season='2024-25'",con)
    matchmap={};pidmap={}
    with gzip.open(ROOT/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz','rt') as z:
        for line in z:
            r=json.loads(line)
            if r.get('fpl_fixture_id') is None or r.get('identity_status')!='mapped':continue
            mid=str(r['provider_match_id']);fid=int(r['fpl_fixture_id']);matchmap.setdefault(mid,set()).add(fid);pidmap[mid,str(r['provider_player_id'])]=str(r['player_uuid'])
    mapofficial=fx.set_index('fpl_fixture_id').fixture_uuid.to_dict();rows=[];fail=[];matches=[]
    for path in sorted(raw.glob('*.json')):
        r=json.loads(path.read_text());general=r.get('general',{});mid=str(general.get('matchId'))
        if general.get('leagueName')!='Premier League':continue
        mapped=matchmap.get(mid,set())
        if len(mapped)!=1:fail.append(dict(match=mid,reason='No unique verified FPL fixture mapping'));continue
        fid=mapofficial.get(next(iter(mapped)))
        if fid is None:fail.append(dict(match=mid,reason='No Core fixture'));continue
        content=r.get('content') or {};facts=content.get('matchFacts') or {};events=(facts.get('events') or {}).get('events',[]);lineup=content.get('lineup') or {}
        goals=[];previous=[0,0];valid=True
        for event in events:
            if event.get('type')!='Goal' or event.get('isPenaltyShootoutEvent'):continue
            new=event.get('newScore');time=event.get('time')
            if not isinstance(new,list) or len(new)!=2 or time is None or sum(new)-sum(previous)!=1 or any(a<b for a,b in zip(new,previous)):valid=False;break
            goals.append((float(time),new));previous=new
        header=r.get('header',{}).get('teams',[])
        final=[int(t['score']) for t in header] if len(header)==2 and all(t.get('score') is not None for t in header) else None
        if not valid or final!=previous:fail.append(dict(match=mid,reason='Goal path cannot reconcile final score'));continue
        startercount=0;coachcount=0
        for side in ['homeTeam','awayTeam']:
            team=lineup.get(side) or {};home=side=='homeTeam';coachcount+=int(bool(team.get('coach',{}).get('id')))
            for player in team.get('starters',[]):
                pid=pidmap.get((mid,str(player['id'])));key=(fid,pid)
                if key not in lookup.index:continue
                rr=lookup.loc[key]
                if rr.y!=1:continue
                startercount+=1;m=float(rr.minutes)
                for t in np.arange(0,90,5):
                    if m<t:break
                    current=[0,0]
                    # Equal-minute ordering is unknown: exclude that minute conservatively.
                    for when,new in goals:
                        if when<t:current=new
                    diff=(current[0]-current[1])*(1 if home else -1)
                    rec=rr.to_dict();rec.update(fixture_uuid=fid,player_uuid=pid,bin=int(t//5),time=float(t),score_diff=float(diff),exit=int(m<90 and t<=m<t+5),coach_id=(team.get('coach') or {}).get('id'),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest());rows.append(rec)
        matches.append(dict(fixture_uuid=fid,provider_match=mid,starters=startercount,coach_sides=coachcount,goals=len(goals)))
    risk=pd.DataFrame(rows);risk=score_features(risk,risk.score_diff.to_numpy(),risk.time.to_numpy());risk.to_csv(out/'score_hazard_risk.csv.gz',index=False,compression='gzip')
    report=dict(classification='VERIFIED_RAW_GOAL_PATH_EXTRACTION_WITH_CONDITIONAL_PUBLICATION_CLOCK',mapped_matches=len(matches),risk_rows=len(risk),mapped_starter_fixture_rows=sum(m['starters'] for m in matches),coach_sides=sum(m['coach_sides'] for m in matches),failures=fail,matches=matches,availability='kickoff+4h proxy; extraction performed later, actual historical publication uncertified',equal_minute_event_order='excluded from pre-bin score',coaches='Observed match coaches recorded for audit only; not assumed known at forecast cutoff',prediction_rule='Actual target goals/lineups are never used in forecast contexts')
    (out/'score_hazard_source_audit.json').write_text(json.dumps(report,indent=2)+'\n');return risk

def fit(risk,C,use_score):
    cats=['pos','bin'];num=NUM+(SCORE if use_score else [])
    pre=ColumnTransformer([('num',StandardScaler(),num),('cat',OneHotEncoder(handle_unknown='ignore'),cats)])
    model=make_pipeline(pre,LogisticRegression(C=C,max_iter=1000,solver='lbfgs',tol=1e-7));model.fit(risk,risk.exit)
    return model

def expected(model,g,record,paths=128):
    if record is None:raise ValueError('Missing cutoff-generated goal forecast')
    # Shared score scenarios for every player, with fixed pre-cutoff total team lambdas.
    inp=record['input'];seed=int.from_bytes(hashlib.sha256((str(record['origin'])+record['fixture']).encode()).digest()[:4],'big');rng=np.random.default_rng(seed)
    home=np.cumsum(rng.poisson(inp['lambda_home_goals']*5/90,size=(paths,18)),axis=1);away=np.cumsum(rng.poisson(inp['lambda_away_goals']*5/90,size=(paths,18)),axis=1)
    diffs=np.column_stack([np.zeros(paths),home[:,:-1]-away[:,:-1]])
    cols=[k for k in NUM if k!='season_progress']+['gw','pos']
    x=g[cols].iloc[np.repeat(np.arange(len(g)),paths*18)].reset_index(drop=True)
    sign=np.where(g.team_id.to_numpy()==record['home'],1,-1)
    diff=(sign[:,None,None]*diffs[None,:,:]).ravel()
    time=np.tile(np.arange(0,90,5),len(g)*paths)
    x=score_features(x,diff,time);h=model.predict_proba(x)[:,1].reshape(len(g),paths,18)
    before=np.concatenate([np.ones((len(g),paths,1)),np.cumprod(1-h,axis=2)[:,:,:-1]],axis=2)
    # Five-minute quadrature: exits occur at bin midpoint in the mathematical model.
    return (before*5*(1-h/2)).sum(axis=2).mean(axis=1)

def predict(frame,risk,records,C,use_score):
    rows=[];cache={};audit=[]
    for gw,g in frame.groupby('gw'):
        cut=pd.to_datetime(g.cutoff,utc=True).min();train=risk[pd.to_datetime(risk.outcome_known_at,utc=True)<cut]
        if len(train)<1000:model=None
        else:
            signature=(len(train),str(train.outcome_known_at.max()))
            if signature not in cache:cache[signature]=fit(train,C,use_score)
            model=cache[signature]
        audit.append(dict(gw=int(gw),risk_training_rows=len(train),max_training_known=str(pd.to_datetime(train.outcome_known_at,utc=True).max()) if len(train) else None))
        for fid,fx in g.groupby('fixture_uuid'):
            r=records.get((int(gw),str(fid)));s=fx.new_start_minutes.to_numpy() if model is None else expected(model,fx,r)
            part=fx.copy();part['s']=s;part['x']=part.new_p_start*s+(1-part.new_p_start)*part.new_q_sub*part.new_sub_minutes;rows.append(part)
        print('Score hazard prefix',frame.season.iloc[0],gw,C,use_score,flush=True)
    return pd.concat(rows,ignore_index=True),audit

def mapping(path,db,season):
    with sqlite3.connect(db) as con:fx=pd.read_sql_query('SELECT fixture_uuid,home_team_id,away_team_id FROM fixtures WHERE season=?',con,params=[season])
    sides={(int(r.home_team_id),int(r.away_team_id)):r.fixture_uuid for r in fx.itertuples()};records=checked_records(path)
    if len(records)!=330:raise ValueError('Complete baseline captures required')
    return {(r['origin'],sides[r['home'],r['away']]):r for r in records}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--out',default='analysis/results/mm-research-20261014');ap.add_argument('--inputs2024',default='work/mm-candidate-pm2024/inputs.jsonl.gz');ap.add_argument('--inputs2025',default='work/mm-pm2025/inputs.jsonl.gz');a=ap.parse_args();out=Path(a.out);risk=prepare(out)
    if a.prepare_only:print('Verified raw goal paths',len(risk));return
    f24=pd.read_csv(out/'2024-25_features.csv.gz');r24=mapping(a.inputs2024,'work/core.sqlite3','2024-25');grid=[];preds={};fitlogs={}
    for use_score in [False,True]:
        for C in [.1,1.]:
            mode=('context_' if use_score else 'flat_hazard_')+str(C);p,log=predict(f24,risk,r24,C,use_score);preds[mode]=p;fitlogs[mode]=log;dev=p[p.gw.between(11,21)&p.y.eq(1)];grid.append(dict(mode=mode,C=C,use_score=use_score,**score(dev.minutes,dev.s)))
    chosen=min(grid,key=lambda r:r['rmse']);(out/'score_hazard_selection.json').write_text(json.dumps(dict(selection='2024 GW11-21 starter-duration RMSE only',chosen=chosen,grid=grid),indent=2)+'\n')
    f25=pd.read_csv(out/'2025-26_features.csv.gz');r25=mapping(a.inputs2025,'work/core.sqlite3','2025-26');p25,log25=predict(f25,risk,r25,chosen['C'],chosen['use_score'])
    p24=preds[chosen['mode']];report=dict(classification='PREKICKOFF_SCORE_SCENARIO_HAZARD_EXPERIMENT',selection=chosen,results={},fit_audit={'2024-25':fitlogs[chosen['mode']],'2025-26':log25},scenario_paths=128,locked_model_active=False,promotion_allowed=False,limitations=['Only 2024 raw match goal paths verified; 2025 fits retain known 2024 hazard training, while player features and goal forecasts update','Five-minute risk bins and midpoint integration; not exact exit seconds','Substitution/red-card/injury causes not separated; this is all-cause departure','Coach observations are not used as unverified future coach assignments','Historical source clocks remain proxies; frozen baseline previously used both seasons','PM/TS impact requires a separate full component replay; no production promotion'])
    for label,p in [('2024-25_GW22-38',p24[p24.gw.ge(22)]),('2025-26_GW6-38',p25)]:
        report['results'][label]=dict(original=metrics(p),candidate=metrics(p,s=p.s.to_numpy()))
    p24.to_csv(out/'2024-25_context_candidate.csv.gz',index=False,compression='gzip');p25.to_csv(out/'2025-26_context_candidate.csv.gz',index=False,compression='gzip');(out/'score_hazard_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:{m:v['minutes'] for m,v in r.items()} for k,r in report['results'].items()},indent=2))
if __name__=='__main__':main()
