#!/usr/bin/env python3
"""Isolated chronological role-MM experiment; no production imports of this module."""
import argparse, gzip, hashlib, json, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from experimental_mm_role_profiles import infer_player_roles
from experimental_individual_role_mm import role_start_probability
from audit_mm_components import load_obs, metrics
from audit_capture_io import write_frame
from fpl_v1_1_model.experimental_mm_research import NUMERIC, start_inputs, project_partition
OUT=ROOT/'analysis/results/individual-mm-20261015'
KEY=['season','fixture_uuid','player_uuid']
ROLE=['role_logit','role_exposure','role_duration','role_cameo','role_cameo_minutes']


def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')


def ledger(db, frames):
    """Postmatch lineup facts are only admitted after kickoff+3/4h, never at target."""
    obs=pd.concat([load_obs(db,s,h).assign(season=s) for s,h in [('2024-25',4),('2025-26',3)]],ignore_index=True)
    obs['pos']=obs.fpl_position.replace({'GKP':'GK','G':'GK'})
    if obs.duplicated(KEY).any():raise ValueError('Duplicate canonical outcome')
    keys=set(map(tuple,obs[KEY].to_numpy()));squad=set();sources=[];fail=[]
    # Stable verified provider identities, not fuzzy names. Ambiguities are rejected.
    source=ROOT/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz'
    midmap={};pidmap={}
    with gzip.open(source,'rt') as z:
        for line in z:
            r=json.loads(line)
            if r.get('identity_status')!='mapped':continue
            pidmap.setdefault(str(r['provider_player_id']),set()).add(str(r['player_uuid']))
            if r.get('fpl_fixture_id') is not None:midmap.setdefault(str(r['provider_match_id']),set()).add(int(r['fpl_fixture_id']))
    with sqlite3.connect(db) as c:
        fx=pd.read_sql_query("SELECT * FROM fixtures WHERE season='2024-25'",c)
        ids=pd.read_sql_query("SELECT external_id,player_uuid FROM player_id_mapping WHERE season='2025-26' AND id_namespace='fpl_element'",c)
    fm=fx.set_index('fpl_fixture_id').fixture_uuid.to_dict()
    lookup=obs.set_index(KEY)
    for path in sorted((ROOT/'data_v1_1/raw/season_2024_25_v1/fotmob/details').glob('*.json')):
        r=json.loads(path.read_text());mid=str(r.get('general',{}).get('matchId'))
        if r.get('general',{}).get('leagueName')!='Premier League':continue
        mapped=midmap.get(mid,set());fid=fm.get(next(iter(mapped))) if len(mapped)==1 else None
        if fid is None:fail.append(dict(source=str(path.relative_to(ROOT)),reason='ambiguous/unmapped fixture'));continue
        lu=r.get('content',{}).get('lineup') or {}
        for side in ['homeTeam','awayTeam']:
            team=lu.get(side) or {};accepted=[];valid=len(team.get('starters',[]))==11
            teams=set()
            for p in team.get('starters',[]):
                pp=pidmap.get(str(p['id']),set());pid=next(iter(pp)) if len(pp)==1 else None;k=('2024-25',fid,pid)
                if k not in keys or lookup.loc[k,'started']!=1:valid=False;break
                teams.add(int(lookup.loc[k,'team_id']))
            if not valid or len(teams)!=1:
                fail.append(dict(source=str(path.relative_to(ROOT)),side=side,reason='starter identity or truth conflict'));continue
            tid=next(iter(teams))
            for p in team.get('starters',[])+team.get('subs',[]):
                pp=pidmap.get(str(p['id']),set());pid=next(iter(pp)) if len(pp)==1 else None;k=('2024-25',fid,pid)
                if k in keys and int(lookup.loc[k,'team_id'])==tid:accepted.append(k)
            squad.update(accepted);sources.append(dict(season='2024-25',fixture_uuid=fid,side=side,rows=len(accepted),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    # 2025 provider lineup IDs are FPL elements. Both ID directions and starter truth must agree.
    pairs=ids.drop_duplicates();pairs=pairs[~pairs.duplicated('external_id',keep=False)&~pairs.duplicated('player_uuid',keep=False)]
    idmap=pairs.set_index('external_id').player_uuid.to_dict()
    cl=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv',usecols=['match_id','fixture_uuid'])
    cl=cl[cl.match_id.str.contains('-prem-')].drop_duplicates()
    if cl.duplicated('match_id').any():raise ValueError('Ambiguous fixture mapping')
    map25=cl.set_index('match_id').fixture_uuid.to_dict()
    for path in sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/lineups.csv')):
        lu=pd.read_csv(path,low_memory=False);lu=lu[lu.match_id.str.contains('-prem-')&lu.lineup_status.eq('confirmed')]
        for (mid,side),g in lu.groupby(['match_id','team_side']):
            fid=map25.get(mid)
            if fid is None:continue
            g=g.drop_duplicates(['player_id','is_starting']);starter=g.is_starting.astype(str).str.lower().isin(['true','1'])
            if starter.sum()!=11:continue
            def pid(v):return idmap.get(str(int(float(v)))) if pd.notna(v) else None
            pids=g.player_id.map(pid);startkeys=[('2025-26',fid,p) for p in pids[starter]]
            if any(k not in keys or lookup.loc[k,'started']!=1 for k in startkeys):
                fail.append(dict(match_id=mid,side=side,reason='starter ID/truth conflict'));continue
            teams={int(lookup.loc[k,'team_id']) for k in startkeys}
            if len(teams)!=1:continue
            tid=next(iter(teams));accepted=[('2025-26',fid,p) for p in pids if ('2025-26',fid,p) in keys and int(lookup.loc[('2025-26',fid,p),'team_id'])==tid]
            squad.update(accepted);sources.append(dict(season='2025-26',fixture_uuid=fid,side=side,rows=len(accepted),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    obs['confirmed_squad']=[k in squad for k in map(tuple,obs[KEY].to_numpy())]
    # A played appearance demonstrates availability in that PAST match. It is not evidence for target availability.
    obs['verified_available']=obs.confirmed_squad | obs.minutes.gt(0) | obs.started.eq(1)
    obs['available']=obs.verified_available.map({True:True,False:None})
    obs['known_at']=obs.known
    audit=dict(seasons={},lineup_sources=sources,rejected=fail,identity_note='Unique season-scoped FPL IDs and exact provider UUID mappings; retrospective identity reconciliation is not a historical roster certification',clock='Postmatch known at kickoff+4h (2024) / +3h (2025), not actual publication timestamps',medical_injury_labels=0,unknown_is_available=False)
    for s,g in obs.groupby('season'):
        f=frames[s];join=f.merge(g[KEY+['started','minutes']],on=KEY,suffixes=('','_truth'),validate='one_to_one',how='left')
        if len(join)!=len(f) or join.minutes_truth.isna().any() or not np.array_equal(join.y,join.started_truth) or not np.array_equal(join.minutes,join.minutes_truth):raise ValueError('Baseline/canonical outcome mismatch')
        if (pd.to_datetime(f.cutoff,utc=True,format='mixed')>=pd.to_datetime(f.kickoff_at,utc=True,format='mixed')).any():raise ValueError('Target already kicked off')
        audit['seasons'][s]=dict(outcomes=len(g),forecast_rows=len(f),squad=int(g.confirmed_squad.sum()),verified_available=int(g.verified_available.sum()),confirmed_unused_bench=int((g.confirmed_squad&g.minutes.eq(0)&g.started.eq(0)).sum()),unknown_availability=int((~g.verified_available).sum()),max_start_news_source_after_cutoff=int((pd.to_datetime(f.get('team_news_source_cutoff',f.cutoff),utc=True,format='mixed')>pd.to_datetime(f.cutoff,utc=True,format='mixed')).sum()))
    return obs,audit


def role_features(frame,obs,half):
    pieces=[];audit=[]
    for cutoff,g in frame.groupby('cutoff',sort=True):
        cut=pd.Timestamp(cutoff);past=obs[obs.known<cut].copy();verified=past[past.verified_available].copy()
        verified['w']=np.exp2(-(cut-verified.known).dt.total_seconds()/86400/half)
        verified['ws']=verified.w*verified.started;verified['wm']=verified.ws*verified.minutes
        verified['wb']=verified.w*(1-verified.started);verified['wc']=verified.w*((verified.started==0)&(verified.minutes>0));verified['wcm']=verified.wc*verified.minutes
        sums=['w','ws','wm','wb','wc','wcm'];pos=verified.groupby('pos')[sums].sum();club=verified.groupby(['season','team_id','pos'])[sums].sum();hist={str(p):v for p,v in verified.groupby('player_uuid')};rows=[]
        for r in g.itertuples():
            pop=pos.loc[r.pos] if r.pos in pos.index else pd.Series(dict.fromkeys(sums,0.))
            pp=float((pop.ws+20*.55)/(pop.w+20));dur=float((pop.wm+20*78)/(pop.ws+20));q=float((pop.wc+20*.45)/(pop.wb+20));cm=float((pop.wcm+20*18)/(pop.wc+20))
            k=(r.season,r.team_id,r.pos)
            if k in club.index:
                t=club.loc[k];pp=(t.ws+40*pp)/(t.w+40);dur=(t.wm+40*dur)/(t.ws+40);q=(t.wc+40*q)/(t.wb+40);cm=(t.wcm+40*cm)/(t.wc+40)
            h=hist.get(str(r.player_uuid),verified.iloc[:0]);h=h[h.pos.eq(r.pos)]
            events=[dict(known_at=v.known,started=bool(v.started),minutes=float(v.minutes),available=True,fixture_uuid=v.fixture_uuid) for v in h.itertuples()]
            profile=infer_player_roles(events,cut,start_prior=pp,prior_exposure=8.,starter_minutes_prior=dur,duration_exposure=5.,half_life_days=half,cameo_prior=q,cameo_minutes_prior=cm)
            check=role_start_probability(events,prior=pp,strength=8.,half_life_days=half,cutoff=cut)
            if not np.isclose(profile['p_start_given_available'],check['role_start_prior']):raise ValueError('Role filter disagreement')
            rows.append(dict(role_logit=float(logit(profile['p_start_given_available'])),role_exposure=profile['effective_start_observations'],role_duration=profile['starter_minutes_mean'],role_cameo=profile['p_cameo_given_bench'],role_cameo_minutes=profile['cameo_minutes_mean'],role_band='regular' if profile['p_start_given_available']>=.8 else 'rotation' if profile['p_start_given_available']>=.4 else 'bench',role_max_known=str(h.known.max()) if len(h) else None))
        pieces.append(pd.concat([g.reset_index(drop=True),pd.DataFrame(rows)],axis=1));audit.append(dict(cutoff=str(cut),rows=len(g),history_rows=len(past),verified_rows=len(verified),maximum_known=str(past.known.max()) if len(past) else None))
    return pd.concat(pieces,ignore_index=True),audit


def fit_role(train,target,C,kind):
    if len(train)<500 or train.y.nunique()<2:return project_partition(target,target.new_p_start.to_numpy())
    if (pd.to_datetime(train.outcome_known_at,utc=True,format='mixed')>=pd.to_datetime(target.cutoff,utc=True,format='mixed').min()).any():raise ValueError('Future fit outcome')
    numeric=NUMERIC+(['role_logit','role_exposure','role_duration','role_cameo','role_cameo_minutes'] if kind=='continuous' else [])
    categories=['pos']+(['role_band'] if kind=='bands' else [])
    pre=ColumnTransformer([('num',StandardScaler(),numeric),('cat',OneHotEncoder(handle_unknown='ignore'),categories)])
    model=make_pipeline(pre,LogisticRegression(C=C,max_iter=1500,tol=1e-7))
    model.fit(start_inputs(train),train.y);p=model.predict_proba(start_inputs(target))[:,1]
    # Same original hard endpoints and news caps in every fitted start arm.
    p=np.where(target.new_p_start.eq(0),0,np.where(target.new_p_start.eq(1),1,p))
    return project_partition(target,p)


def predict(frame,previous,C,kind):
    alltrain=frame if previous is None else pd.concat([previous,frame],ignore_index=True);rows=[]
    for cut,g in frame.groupby('cutoff',sort=True):
        train=alltrain[pd.to_datetime(alltrain.outcome_known_at,utc=True,format='mixed')<pd.Timestamp(cut)]
        r=g.copy();r['p']=fit_role(train,g,C,kind);r['s']=r.new_start_minutes;r['q']=r.new_q_sub;r['c']=r.new_sub_minutes
        r.loc[r.team_news_state.isin(['OUT','SUSPENDED']),['p','q']]=0.
        r['x']=r.p*r.s+(1-r.p)*r.q*r.c;rows.append(r)
    return pd.concat(rows,ignore_index=True)


def arms(start):
    full=start.copy();full['s']=full.role_duration;full['q']=full.get('role_q_calibrated',full.role_cameo);full['c']=full.role_cameo_minutes
    # Preserve frozen hard availability endpoints; no inferred recovery boost.
    full.loc[full.new_p_start.eq(0)&full.new_q_sub.eq(0),['p','q']]=0.
    full.loc[full.team_news_state.isin(['OUT','SUSPENDED']),['p','q']]=0.
    full['x']=full.p*full.s+(1-full.p)*full.q*full.c
    duration=start.copy();duration['s']=duration.role_duration;duration['x']=duration.p*duration.s+(1-duration.p)*duration.q*duration.c
    return {'role_start':start,'role_start_duration':duration,'role_full':full}


def calibrate_cameo(frame,previous=None):
    """Calibrate conditional-squad q into unconditional non-start appearance odds.

    Unknown past squad membership is never treated as availability. Realized
    non-start appearance is nevertheless an observed supervised outcome.
    """
    pool=frame if previous is None else pd.concat([previous,frame],ignore_index=True)
    result=[]
    for cut,g in frame.groupby('cutoff',sort=True):
        train=pool[pd.to_datetime(pool.outcome_known_at,utc=True,format='mixed').lt(pd.Timestamp(cut))&pool.y.eq(0)].copy();g=g.copy()
        train['label']=train.minutes.gt(0).astype(int)
        def inputs(f):
            f=f.copy();f['bench_logit']=logit(np.clip(f.new_q_sub,1e-6,1-1e-6));return f
        if len(train)>=300 and train.label.nunique()==2:
            pre=ColumnTransformer([('num',StandardScaler(),['bench_logit','role_cameo','role_exposure','history_n','days_since_play']),('cat',OneHotEncoder(handle_unknown='ignore'),['pos'])])
            fit=make_pipeline(pre,LogisticRegression(C=.1,max_iter=1000,tol=1e-7));fit.fit(inputs(train),train.label)
            g['role_q_calibrated']=fit.predict_proba(inputs(g))[:,1]
        else:g['role_q_calibrated']=g.new_q_sub
        g.loc[g.team_news_state.isin(['OUT','SUSPENDED']),'role_q_calibrated']=0.
        result.append(g)
    return pd.concat(result,ignore_index=True)


def clustered_ci(g,base,cluster,draws=1000):
    pair=g.merge(base[KEY+['p','x']],on=KEY,validate='one_to_one',suffixes=('','_base'))
    y=pair.y.to_numpy();m=pair.minutes.to_numpy();p=pair.p.to_numpy();p0=pair.p_base.to_numpy();x=pair.x.to_numpy();x0=pair.x_base.to_numpy()
    safe=lambda a:np.clip(a,1e-12,1-1e-12)
    losses=dict(mae=abs(x-m),mse=(x-m)**2,brier=(p-y)**2,log_loss=-(y*np.log(safe(p))+(1-y)*np.log1p(-safe(p))))
    originals=dict(mae=abs(x0-m),mse=(x0-m)**2,brier=(p0-y)**2,log_loss=-(y*np.log(safe(p0))+(1-y)*np.log1p(-safe(p0))))
    groups=pair.groupby(cluster,sort=True).indices;matrix=np.array([[len(idx)]+[losses[k][idx].sum() for k in losses]+[originals[k][idx].sum() for k in originals] for idx in groups.values()]);rng=np.random.default_rng(20261015);b=matrix[rng.integers(len(matrix),size=(draws,len(matrix)))].sum(axis=1);out={}
    for j,k in enumerate(losses):
        a=b[:,j+1]/b[:,0];ref=b[:,j+5]/b[:,0]
        if k=='mse':a=np.sqrt(a);ref=np.sqrt(ref);k='rmse'
        out[k]=dict(delta=float((np.sqrt(losses['mse'].mean())-np.sqrt(originals['mse'].mean())) if k=='rmse' else (losses[k]-originals[k]).mean()),interval95=np.quantile(a-ref,[.025,.975]).tolist())
    return out


def summarize(modes):
    result={};base=modes['original']
    for mode,g in modes.items():
        r=metrics(g,p=g.p,s=g.s,q=g.q,c=g.c)
        r['paired']={k:clustered_ci(g,base,k) for k in ['fixture_uuid','team_id']}
        if mode.startswith('role_'):
            r['paired_vs_same_logistic_without_role']={k:clustered_ci(g,modes['same_logistic_without_role'],k) for k in ['fixture_uuid','team_id']}
        masks={k:g.player_type.eq(v) for k,v in [('regular','regular'),('rotation','rotation_or_short_history'),('reserve','reserve')]}
        masks['returned_available_not_verified_injury']=g.team_news_state.eq('RETURNED_AVAILABLE')
        masks['verified_prior_injury']=np.zeros(len(g),dtype=bool)
        masks['long_gap_not_medical']=g.long_gap_proxy.astype(bool)
        r['groups']={k:metrics(g.loc[v],p=g.loc[v].p,s=g.loc[v].s,q=g.loc[v].q,c=g.loc[v].c) if np.any(v) else dict(rows=0,status='Not Available: no verified medical labels') for k,v in masks.items()}
        r['xi']=dict(max_expected_start_error=float(abs(g.groupby(['fixture_uuid','team_id']).p.sum()-11).max()),max_keeper_error=float(abs(g[g.pos.isin(['GK','GKP'])].groupby(['fixture_uuid','team_id']).p.sum()-1).max()))
        result[mode]=r
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',default='work/core.sqlite3');ap.add_argument('--out',default=str(OUT));a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    frames={s:pd.read_csv(ROOT/f'analysis/results/mm-research-20261014/{s}_features.csv.gz') for s in ['2024-25','2025-26']}
    obs,audit=ledger(a.db,frames);write_frame(out/'availability_ledger.csv.gz',obs);save(out/'data_audit.json',audit)
    features={};logs={};devscores={};candidates={}
    # Feature generation is causal at every row; selection uses only earlier 2024 GWs.
    for half in [42.,180.]:
        features[half],logs[str(half)]=role_features(frames['2024-25'],obs,half)
        write_frame(out/f'2024-25_roles_h{half}.csv.gz',features[half])
        for kind in ['continuous','bands']:
            for C in [.1,1.]:
                label=f'{kind}_h{half}_C{C}';pred=predict(features[half],None,C,kind);candidates[label]=pred;write_frame(out/(label+'_development_predictions.csv.gz'),pred)
                dev=pred[pred.gw.between(11,21)];devscores[label]=dict(start=metrics(dev,p=dev.p,s=dev.s,q=dev.q,c=dev.c)['start'],arms={k:metrics(v,p=v.p,s=v.s,q=v.q,c=v.c)['minutes'] for k,v in arms(dev).items()},half=half,C=C,kind=kind)
                print('Development',label,devscores[label]['start']['log_loss'],flush=True)
    chosen=min(devscores,key=lambda k:devscores[k]['start']['log_loss']);cfg=devscores[chosen]
    candidates[chosen]=calibrate_cameo(candidates[chosen])
    dev=candidates[chosen][candidates[chosen].gw.between(11,21)]
    cfg['calibrated_arms']={k:metrics(v,p=v.p,s=v.s,q=v.q,c=v.c)['minutes'] for k,v in arms(dev).items()}
    chosen_arm=min(cfg['calibrated_arms'],key=lambda k:cfg['calibrated_arms'][k]['mae'])
    protocol=dict(development='2024-25 GW11-21',evaluation=['2024-25 GW22-38','2025-26 GW6-38'],selected=chosen,selected_arm=chosen_arm,objective='Start log-loss then all-row minute MAE among selected start/duration/bench arms',grid=devscores,selection_before_2025_predictions=True,independent_holdout=False,locked_model_active=False,promotion_allowed=False)
    save(out/'selection.json',protocol)
    f25,log25=role_features(frames['2025-26'],obs,cfg['half']);p25=calibrate_cameo(predict(f25,features[cfg['half']],cfg['C'],cfg['kind']),candidates[chosen]);logs['2025-26']=log25
    predictions={};report={}
    for season,start in [('2024-25',candidates[chosen]),('2025-26',p25)]:
        f=frames[season].copy();f['p']=f.new_p_start;f['s']=f.new_start_minutes;f['q']=f.new_q_sub;f['c']=f.new_sub_minutes;f['x']=f.new_xmins
        modes={'original':f,**arms(start)};part=f.copy();part['p']=project_partition(part,part.p);part['x']=part.p*part.s+(1-part.p)*part.q*part.c;modes['partition_only']=part
        gate=f.copy();gate.loc[gate.team_news_state.isin(['OUT','SUSPENDED']),['p','q']]=0.;gate['x']=gate.p*gate.s+(1-gate.p)*gate.q*gate.c;modes['availability_only']=gate
        old=pd.read_csv(ROOT/f'analysis/results/mm-research-20261014/{season}_candidates.csv.gz');modes['previous_start_survival']=old[old['mode'].eq('combined')].copy()
        # Same-feature baseline logistic ablation: extra role features alone differ.
        baseline=predict(features[cfg['half']] if season=='2024-25' else f25,None if season=='2024-25' else features[cfg['half']],cfg['C'],'none');modes['same_logistic_without_role']=baseline
        pred=pd.concat([v.assign(mode=k) for k,v in modes.items()],ignore_index=True);write_frame(out/f'{season}_candidates.csv.gz',pred);predictions[season]=pred
        evaluated={k:v[v.gw.ge(22)] if season=='2024-25' else v for k,v in modes.items()};report[season]=summarize(evaluated)
    save(out/'report.json',dict(protocol=protocol,results=report,fit_audit=logs,locked_model_active=False,promotion_allowed=False,limitations=['Reused research periods, not pristine holdouts','Postmatch availability based on actual historical squad/played status; not target news','No medically verified return labels; RETURNED_AVAILABLE is news state only','Only PL histories; no validated rest correction or complete future squad/price schedule snapshots']))
    print(json.dumps({s:{k:dict(minutes=v['minutes'],start={j:v['start'][j] for j in ['brier','log_loss','ece10']}) for k,v in r.items()}for s,r in report.items()},indent=2))

if __name__=='__main__':main()
