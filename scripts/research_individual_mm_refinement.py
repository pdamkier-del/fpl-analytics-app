#!/usr/bin/env python3
"""MM-only nested prequential refinement of existing frozen PR4/8 forecasts.

No production edits, health inference, probability floor or point simulation.
"""
from pathlib import Path
from collections import defaultdict
import gzip,hashlib,json,sqlite3,inspect
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression,Ridge
from individual_mm_evidence import load_frame,encode_frame
from experimental_role_injury_mm import bounded_news
from validate_mm_all_clubs import metrics,temporal_ci,combined_ci,component_problem
from validate_mm_probability_robustness import probability_scores

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'analysis/results/role-injury-mm-20261016'
OUT=ROOT/'analysis/results/individual-mm-refinement-20261016'
KEY=['season','fixture_uuid','player_uuid']
REFERENCE='role_chance_return_duration'
NUM=['logit_p','logit_q','normal_p','stable_p','starter_mean','cameo_mean',
     'history_n','start_n','cameo_n','last_start_minutes','last_started',
     'rest_days','team_rest_days','minutes_7d','minutes_14d','role_jump']


def before(clock,cutoff):
    return pd.notna(clock)and pd.Timestamp(clock)<pd.Timestamp(cutoff)


def compose(f):
    f=f.copy();f['x']=f.p*f.s+(1-f.p)*f.q*f.c
    if not np.isfinite(f[['p','q','s','c','x']].to_numpy(float)).all():raise ValueError('Nonfinite MM output')
    if not f[['p','q']].ge(0).all().all()or not f[['p','q']].le(1+1e-9).all().all():raise ValueError('Invalid probability')
    if not f[['s','c','x']].ge(0).all().all()or not f[['s','c','x']].le(90+1e-8).all().all():raise ValueError('Invalid minute support')
    return f


def project(f):
    """Reuse existing caps and exact GK/outfield projection; never soften hard news."""
    result=bounded_news(f,chance=True,project=True)
    if result.projection_infeasible.any():raise ValueError('Infeasible candidate roster')
    if not np.allclose(result.groupby(['season','fixture_uuid','team_id']).p.sum(),11,atol=1e-6):raise ValueError('Not exact11')
    hard=f.news_eligible&f.news_state.isin(['OUT','SUSPENDED'])
    if not result.loc[hard,['p','q','x']].eq(0).all().all():raise ValueError('Hard source override')
    return compose(result)


def build_features(base,role,core):
    """Known-at joins only. Unknown medical absence never updates normal role."""
    f=base.merge(role[KEY+['p']],on=KEY,validate='one_to_one',suffixes=('','_role'))
    core=core.copy();core['kickoff_at']=pd.to_datetime(core.kickoff_at,utc=True,format='mixed')
    core['known_at']=core.kickoff_at+pd.to_timedelta(np.where(core.season.eq('2024-25'),4,3),unit='h')
    keys=base[KEY+['news_eligible','news_state']].copy()
    verified=core.merge(keys,on=KEY,how='left',validate='one_to_one')
    verified['role_available']=verified.news_eligible.eq(True)&verified.news_state.isin(['AVAILABLE','RETURNED_AVAILABLE'])
    histories={(s,p,int(t)):g.sort_values(['known_at','fixture_uuid'])for(s,p,t),g in verified.groupby(['season','player_uuid','team_id'])}
    role_history=base.copy();role_history['cutoff']=pd.to_datetime(role_history.cutoff,utc=True,format='mixed')
    role_history=role_history[role_history.news_eligible&role_history.news_state.isin(['AVAILABLE','RETURNED_AVAILABLE'])]
    role_groups={(s,p,int(t)):g.sort_values('cutoff')for(s,p,t),g in role_history.groupby(['season','player_uuid','team_id'])}
    teamhist={(s,int(t)):g[['fixture_uuid','kickoff_at','known_at']].drop_duplicates().sort_values('known_at')for(s,t),g in core.groupby(['season','team_id'])}
    current=core[KEY+['kickoff_at','known_at','started','minutes','team_id','gw']]
    check=f.merge(current,on=KEY,validate='one_to_one',suffixes=('','_core'))
    for a,b in [('y','started'),('minutes','minutes_core'),('team_id','team_id_core'),('gw','gw_core')]:
        if not np.array_equal(check[a],check[b]):raise ValueError('Canonical identity/truth mismatch '+a)
    f=f.merge(core[KEY+['kickoff_at','known_at']],on=KEY,validate='one_to_one')
    f['cutoff']=pd.to_datetime(f.cutoff,utc=True,format='mixed')
    if not f.kickoff_at.gt(f.cutoff).all():raise ValueError('Cutoff not before target')
    features=[];start_hist=[];cameo_hist=[]
    for number,r in enumerate(f.itertuples()):
        if number%2000==0:print('Prior-only features',number,'/',len(f),flush=True)
        cut=r.cutoff;h=histories[(r.season,r.player_uuid,int(r.team_id))];past=h[h.known_at.lt(cut)];av=past[past.role_available]
        starters=av[av.started.eq(1)];cameos=av[av.started.eq(0)&av.minutes.gt(0)]
        w=np.exp2(-(cut-av.known_at).dt.total_seconds().to_numpy()/86400/180)
        normal=float(r.normal_role_p)if pd.notna(r.normal_role_p)else float(r.p_role)
        stable=(8*normal+float(w@av.started.to_numpy()))/(8+w.sum())
        def hist(g):
            ww=np.exp2(-(cut-g.known_at).dt.total_seconds().to_numpy()/86400/180)
            return np.bincount(g.minutes.to_numpy(int),weights=ww,minlength=91).astype(float)
        hs,hc=hist(starters),hist(cameos);start_hist.append(hs);cameo_hist.append(hc)
        played=past[past.minutes.gt(0)];team=teamhist[(r.season,int(r.team_id))];team=team[team.known_at.lt(cut)]
        latest=av.iloc[-1]if len(av)else None
        previous_role=role_groups.get((r.season,r.player_uuid,int(r.team_id)))
        previous_role=previous_role[previous_role.cutoff.lt(cut)]if previous_role is not None else None
        previous=previous_role.iloc[-1]if previous_role is not None and len(previous_role)else None
        sm=float(hs@np.arange(91)/hs.sum())if hs.sum()else np.nan;cm=float(hc@np.arange(91)/hc.sum())if hc.sum()else np.nan
        starts=starters.minutes.tolist();last6=past.tail(6)
        group='regular'if len(last6)>=6 and last6.started.eq(1).all()else'reserve'if len(last6)>=3 and last6.started.mean()<=.2 else'rotation_or_short_history'
        features.append(dict(normal_p=normal,stable_p=stable,history_n=float(w.sum()),start_n=float(hs.sum()),cameo_n=float(hc.sum()),
            starter_mean=sm,cameo_mean=cm,last_start_minutes=float(starts[-1])if starts else np.nan,
            last_started=float(latest.started)if latest is not None else np.nan,
            rest_days=(cut-played.kickoff_at.iloc[-1]).total_seconds()/86400 if len(played)else np.nan,
            team_rest_days=(cut-team.kickoff_at.iloc[-1]).total_seconds()/86400 if len(team)else np.nan,
            minutes_7d=float(past.loc[past.kickoff_at.gt(cut-pd.Timedelta(days=7)),'minutes'].sum()),
            minutes_14d=float(past.loc[past.kickoff_at.gt(cut-pd.Timedelta(days=14)),'minutes'].sum()),
            role_jump=normal-float(previous.p)if previous is not None else 0.,
            prior_three_full_starts=len(starts)>=3 and all(v==90 for v in starts[-3:]),
            single_short_after_three_full=len(starts)>=4 and all(v==90 for v in starts[-4:-1])and starts[-1]<60,
            prior_type=group,max_history_known_at=past.known_at.max()if len(past)else pd.NaT))
    f=pd.concat([f.reset_index(drop=True),pd.DataFrame(features)],axis=1)
    f['logit_p']=logit(np.clip(f.p,1e-6,1-1e-6));f['logit_q']=logit(np.clip(f.q,1e-6,1-1e-6))
    # Preserve an explicit episode from prior sourced medical OUT or suspension.
    f['return_prior_p']=np.nan;f['return_prior_s']=np.nan;f['return_prior_games']=np.nan;f['return_kind']='none';f['return_active']=False
    for _,g in f.groupby(['season','player_uuid'],sort=False):
        latent=None;episode=None;origin=None;club=None
        for cut,rows in g.sort_values(['cutoff','fixture_uuid']).groupby('cutoff',sort=True):
            r=rows.iloc[0]
            if club!=r.team_id:latent=None;episode=None;origin=None
            club=r.team_id
            if r.news_eligible and(r.news_medical_out or r.news_state=='SUSPENDED'):
                episode='medical_selection'if r.news_medical_out else'suspension_selection';origin=None
            elif r.news_eligible and r.news_state in ['AVAILABLE','RETURNED_AVAILABLE']:
                if episode and latent is not None:
                    if origin is None:origin=cut
                    ph=histories[(r.season,r.player_uuid,int(r.team_id))]
                    n=int((ph.known_at.lt(cut)&ph.kickoff_at.ge(origin)).sum())
                    if n<3:
                        f.loc[rows.index,'return_prior_p']=latent['p'];f.loc[rows.index,'return_prior_s']=latent['s']
                        f.loc[rows.index,'return_prior_games']=n;f.loc[rows.index,'return_active']=True;f.loc[rows.index,'return_kind']=episode
                    else:episode=None;origin=None
                if episode is None:latent=dict(p=float(r.p),s=float(r.s),cutoff=cut)
    f['max_history_known_at']=pd.to_datetime(f.max_history_known_at,utc=True,format='mixed')
    legal=f.max_history_known_at.isna()|f.max_history_known_at.lt(f.cutoff)
    if not legal.all():raise ValueError('History leakage')
    return f,np.stack(start_hist),np.stack(cameo_hist)


def design(f):
    a=f[NUM].to_numpy(float);missing=~np.isfinite(a);a=np.nan_to_num(a,nan=0.)
    pos=np.c_[f.pos.isin(['GK','GKP']),f.pos.eq('DEF'),f.pos.eq('MID'),f.pos.eq('FWD')].astype(float)
    return np.c_[a,missing.astype(float),pos]


def duration_distribution(mean,residual_counts,personal_counts,*,cameo=False):
    """Discrete bounded posterior mixture; strength5 reused from existing duration prior."""
    low=1 if cameo else 0
    residuals=np.arange(-90,91);locations=np.clip(mean+residuals,low,90)
    lower=np.floor(locations).astype(int);upper=np.minimum(lower+1,90);fraction=locations-lower
    prior=np.bincount(lower,weights=residual_counts*(1-fraction),minlength=91)+np.bincount(upper,weights=residual_counts*fraction,minlength=91)
    if prior.sum()==0:raise ValueError('Empty duration prior')
    prior/=prior.sum();n=personal_counts.sum();pmf=(5*prior+personal_counts)/(5+n)
    if not np.isclose(pmf.sum(),1)or np.any(pmf<0):raise ValueError('Invalid duration PMF')
    support=np.arange(91);mu=float(pmf@support);sd=float(np.sqrt(max(pmf@(support**2)-mu**2,0)))
    cdf=np.cumsum(pmf);quant=[int(np.searchsorted(cdf+1e-10,v))for v in [.1,.9]]
    return mu,sd,quant[0],quant[1],float(pmf[90]),float(pmf[1:16].sum())


def prequential(f,hs,hc):
    """Fit only outcomes known before each origin; no current fold truth used."""
    x=design(f);out={};fitlog=[]
    for a in [.1,1.,10.]:out['B:'+str(a)]=f.p.to_numpy(float).copy()
    for a in [1.,10.,100.]:
        out['C_s:'+str(a)]=f.s.to_numpy(float).copy();out['C_c:'+str(a)]=f.c.to_numpy(float).copy()
        for k in ['s_sd','s_q10','s_q90','s_p90','c_sd','c_q10','c_q90','c_p1_15']:out[k+':'+str(a)]=np.full(len(f),np.nan)
    for cut,ix in f.groupby('cutoff',sort=True).indices.items():
        ix=np.asarray(ix);train=np.flatnonzero(f.known_at.lt(cut).to_numpy())
        interior=train[(f.iloc[train].p.to_numpy()>0)&(f.iloc[train].p.to_numpy()<1)]
        for alpha in [.1,1.,10.]:
            if len(interior)<200 or f.iloc[interior].y.nunique()<2:continue
            model=make_pipeline(StandardScaler(),LogisticRegression(C=1/alpha,max_iter=3000,tol=1e-8))
            model.fit(x[interior],f.iloc[interior].y)
            if model[-1].n_iter_[0]>=3000:raise ValueError('Start calibration not converged')
            raw=model.predict_proba(x[ix])[:,1];new=f.iloc[ix].copy();new['p']=raw
            # All hard zeros/source caps are imposed by the existing projection.
            fixed=f.iloc[ix].p.eq(0)&f.iloc[ix].q.eq(0)
            new.loc[fixed,'p']=0.
            out['B:'+str(alpha)][ix]=project(new).p.to_numpy()
        for alpha in [1.,10.,100.]:
            for mode,target,hist,condition,minimum in [('s','s',hs,f.y.eq(1),100),('c','c',hc,f.y.eq(0)&f.minutes.gt(0),50)]:
                ids=train[condition.iloc[train].to_numpy()]
                if len(ids)<minimum:continue
                model=make_pipeline(StandardScaler(),Ridge(alpha=alpha,solver='lsqr',tol=1e-12))
                model.fit(x[ids],f.iloc[ids].minutes-f.iloc[ids][target])
                residual=np.clip(f.iloc[ids].minutes.to_numpy()-f.iloc[ids][target].to_numpy()-model.predict(x[ids]),-90,90)
                pools={}
                for pos in f.pos.unique():
                    mask=f.iloc[ids].pos.eq(pos).to_numpy();v=residual[mask]if mask.any()else residual
                    lo=np.floor(v+90).astype(int);hi=np.minimum(lo+1,180);frac=v+90-lo
                    pools[pos]=np.bincount(lo,weights=1-frac,minlength=181)+np.bincount(hi,weights=frac,minlength=181)
                pred=np.clip(f.iloc[ix][target].to_numpy()+model.predict(x[ix]),1 if mode=='c'else 0,90)
                for i,mu in zip(ix,pred):
                    stats=duration_distribution(mu,pools[f.iloc[i].pos],hist[i],cameo=mode=='c')
                    out['C_'+mode+':'+str(alpha)][i]=stats[0]
                    for k,val in zip(([mode+'_sd',mode+'_q10',mode+'_q90','s_p90']if mode=='s'else['c_sd','c_q10','c_q90','unused','c_p1_15']),stats[1:]if mode=='s'else stats[1:]):
                        if k!='unused':out[k+':'+str(alpha)][i]=val
        fitlog.append(dict(cutoff=str(cut),training_rows=len(train),target_rows=len(ix),latest_label_known_at=str(f.iloc[train].known_at.max())if len(train)else None,properly_before=not len(train)or bool(f.iloc[train].known_at.lt(cut).all())))
        print('MM origin',str(cut),'past rows',len(train),'targets',len(ix),flush=True)
    return out,pd.DataFrame(fitlog)


def change(f,kind,parameter,raw=None,context=None):
    g=f.copy()
    if kind=='A':
        has=g.history_n.gt(0);g.loc[has,'p']=(1-parameter)*g.loc[has,'p']+parameter*g.loc[has,'stable_p']
        g=project(g)
    elif kind=='B':g['p']=raw['B:'+str(parameter)];g=project(g)
    elif kind=='C':
        alpha,weight=parameter
        g['s']=(1-weight)*g.s+weight*raw['C_s:'+str(alpha)]
        g['c']=(1-weight)*g.c+weight*raw['C_c:'+str(alpha)]
    elif kind=='D':
        use=g.return_active;weight=parameter/(1+g.loc[use,'return_prior_games'])
        g.loc[use,'p']=(1-weight)*g.loc[use,'p']+weight*g.loc[use,'return_prior_p']
        g.loc[use,'s']=(1-weight)*g.loc[use,'s']+weight*g.loc[use,'return_prior_s']
        g=project(g)
    return compose(g)


def select(f,raw):
    valid=f.season.eq('2024-25')&f.gw.between(14,21)
    vf=f.loc[valid].reset_index(drop=True);vr={k:v[valid.to_numpy()]for k,v in raw.items()}
    grid={'A':[.25,.5,1.],'B':[.1,1.,10.],'C':[(a,1.)for a in [1.,10.,100.]],'D':[.25,.5,1.]}
    rows=[];selected={}
    for kind,params in grid.items():
        for parameter in params:
            arm=change(vf,kind,parameter,raw=vr)
            score=metrics(arm);loss=score['start_brier']if kind=='B'else score['minute_mae']
            rows.append(dict(component=kind,parameter=json.dumps(parameter),validation_loss=loss,validation_minute_mae=score['minute_mae'],validation_start_brier=score['start_brier']))
        options=[r for r in rows if r['component']==kind];winner=min(options,key=lambda r:r['validation_loss']);selected[kind]=json.loads(winner['parameter'])
    return selected,pd.DataFrame(rows)


def get_groups(f):
    return dict(all=np.ones(len(f),bool),regular=f.prior_type.eq('regular'),rotation=f.prior_type.eq('rotation_or_short_history'),reserve=f.prior_type.eq('reserve'),
        actual_starters_evaluation_only=f.y.eq(1),actual_cameos_evaluation_only=f.y.eq(0)&f.minutes.gt(0),
        source_unknown=~f.news_eligible,source_medical_return=f.news_medical_return,source_medical_out=f.news_medical_out,
        documented_return_1=f.return_active&f.return_prior_games.eq(0),documented_return_2=f.return_active&f.return_prior_games.eq(1),documented_return_3=f.return_active&f.return_prior_games.eq(2),
        documented_suspension_return=f.return_active&f.return_kind.eq('suspension_selection'),
        false_zero_reference_evaluation_only=f.p.eq(0)&f.q.eq(0)&f.minutes.gt(0),
        short_rest=f.rest_days.le(3),normal_rest=f.rest_days.gt(3)&f.rest_days.le(7),long_rest=f.rest_days.gt(7),rest_unknown=f.rest_days.isna(),
        prior_three_full_starts=f.prior_three_full_starts,single_short_after_three_full=f.single_short_after_three_full)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=load_frame(BASE/'predictions.npz');base=frozen[frozen['mode'].eq(REFERENCE)].copy().reset_index(drop=True)
    role=frozen[frozen['mode'].eq('role')].copy();original=frozen[frozen['mode'].eq('original')].copy()
    with sqlite3.connect(ROOT/'work/core.sqlite3')as db:
        core=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,gw,kickoff_at,started,minutes FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
        names=dict(db.execute('SELECT player_uuid,canonical_name FROM players'))
    cache=ROOT/'work/mm-refinement-prefix.npz'
    signature=hashlib.sha256((hashlib.sha256((BASE/'predictions.npz').read_bytes()).hexdigest()+inspect.getsource(build_features)+str(pd.util.hash_pandas_object(core,index=False).sum())).encode()).hexdigest()
    if cache.exists():
        with np.load(cache,allow_pickle=False)as z:
            hit=str(z['signature'])==signature
            if hit:
                f=load_frame(z['frame'].tobytes());hs=z['hs'];hc=z['hc']
                for col in ['cutoff','kickoff_at','known_at','max_history_known_at']:f[col]=pd.to_datetime(f[col],utc=True,format='mixed')
    else:hit=False
    if not hit:
        f,hs,hc=build_features(base,role,core)
        with cache.with_suffix('.tmp').open('wb')as output:np.savez_compressed(output,signature=np.asarray(signature),frame=np.frombuffer(encode_frame(f),dtype=np.uint8),hs=hs,hc=hc)
        cache.with_suffix('.tmp').replace(cache)
    print('Validated prior-only features',len(f),'cache reused',hit,flush=True)
    raw,log=prequential(f,hs,hc);choice,tuning=select(f,raw)
    arms={'best_existing':compose(f.copy())}
    o=f.drop(columns=['p','s','q','c','x']).merge(original[KEY+['p','s','q','c','x']],on=KEY,validate='one_to_one');arms['original']=compose(o)
    for kind in ['A','B','C','D']:arms[kind]=change(f,kind,choice[kind],raw=raw)
    # Explicit ablations, not a grid searched on evaluation outcomes.
    for label,parts in [('A_B',['A','B']),('A_C',['A','C']),('B_C',['B','C']),('B_D',['B','D']),('A_B_C_D',['A','B','C','D'])]:
        g=f.copy()
        for kind in parts:
            if kind=='B'and 'A'in parts:
                # Blend the fixed calibrated signal with A on log-odds scale;
                # calibrated B is fitted to baseline, not secretly refitted to A.
                from scipy.special import expit
                shift=logit(np.clip(raw['B:'+str(choice['B'])],1e-8,1-1e-8))-logit(np.clip(f.p,1e-8,1-1e-8))
                fixed=g.p.eq(0)&g.q.eq(0);g['p']=expit(logit(np.clip(g.p,1e-8,1-1e-8))+shift);g.loc[fixed,'p']=0.;g=project(g)
            else:g=change(g,kind,choice[kind],raw=raw)
        arms[label]=compose(g)
    evalmask=f.season.eq('2025-26')|f.gw.ge(22)
    if int((f.loc[evalmask].p.eq(0)&f.loc[evalmask].q.eq(0)&f.loc[evalmask].minutes.gt(0)).sum())!=35:raise ValueError('False-zero cohort changed')
    clubnames={(r.season,int(r.team_id)):r.club for r in pd.read_csv(BASE/'coverage.csv').itertuples()}
    overall=[];clubrows=[];groups=[];calibration=[];cirows=[];diagnostic=[];worst=[]
    for season in ['2024-25','2025-26']:
        low=22 if season=='2024-25'else 6;grid=range(low,39)
        idx=f.index[f.season.eq(season)&f.gw.ge(low)];reference=arms['best_existing'].loc[idx]
        for label,arm in arms.items():
            g=arm.loc[idx];overall.append(dict(season=season,model=label,**metrics(g)))
            ci=temporal_ci(g,reference,grid)
            for k,v in ci['metrics'].items():cirows.append(dict(season=season,model=label,metric=k,delta=v['delta'],low=v['interval95'][0]if v['interval95']else None,high=v['interval95'][1]if v['interval95']else None))
            for target,p,y in [('start',g.p,g.y),('appearance',g.p+(1-g.p)*g.q,g.minutes.gt(0))]:
                for r in probability_scores(p,y)['reliability']:calibration.append(dict(season=season,model=label,target=target,**r))
            for group,mask in get_groups(reference).items():
                if group=='all':continue
                jj=reference.index[np.asarray(mask)];gg=g.loc[jj]
                if not len(gg):continue
                pair=temporal_ci(gg,reference.loc[jj],grid)
                v=pair['metrics']['minute_mae'];b=pair['metrics']['start_brier'];ps=probability_scores(gg.p,gg.y)
                groups.append(dict(season=season,club='ALL',model=label,group=group,**metrics(gg),start_ece=ps['ece_10_bins'],mae_delta=v['delta'],mae_low=v['interval95'][0]if v['interval95']else None,mae_high=v['interval95'][1]if v['interval95']else None,start_brier_delta=b['delta'],start_brier_low=b['interval95'][0]if b['interval95']else None,start_brier_high=b['interval95'][1]if b['interval95']else None,ci_status=pair.get('status','Available conditional block CI')))
            for team,rg in reference.groupby('team_id'):
                take=rg.index;cg=g.loc[take];club=clubnames[(season,int(team))];cc=temporal_ci(cg,rg,grid)
                mm=metrics(cg);v=cc['metrics']['minute_mae'];clubrows.append(dict(season=season,club=club,team_id=int(team),model=label,**mm,mae_delta=v['delta'],mae_low=v['interval95'][0]if v['interval95']else None,mae_high=v['interval95'][1]if v['interval95']else None))
                for group,mask in get_groups(rg).items():
                    if group=='all':continue
                    jj=rg.index[np.asarray(mask)];gg=cg.loc[jj]
                    if not len(gg):continue
                    pair=temporal_ci(gg,rg.loc[jj],grid,draws=1000)
                    v=pair['metrics']['minute_mae'];ps=probability_scores(gg.p,gg.y)
                    groups.append(dict(season=season,club=club,model=label,group=group,**metrics(gg),start_ece=ps['ece_10_bins'],mae_delta=v['delta'],mae_low=v['interval95'][0]if v['interval95']else None,mae_high=v['interval95'][1]if v['interval95']else None,ci_status=pair.get('status','Available conditional block CI')))
                if label=='best_existing':diagnostic.append(dict(season=season,club=club,**component_problem(cg)))
            top=g.assign(abs_error=abs(g.x-g.minutes)).nlargest(30,'abs_error')
            for r in top.itertuples():worst.append(dict(season=season,model=label,club=clubnames[(season,int(r.team_id))],player=names.get(r.player_uuid),player_uuid=r.player_uuid,fixture_uuid=r.fixture_uuid,gw=r.gw,cutoff=str(r.cutoff),minutes=r.minutes,p=r.p,s=r.s,q=r.q,c=r.c,x=r.x,abs_error=r.abs_error,news_state=r.news_state,news_source=r.news_source,explanation='Observed source conflict'if r.news_state in ['OUT','SUSPENDED']and r.minutes>0 else'No verified causal medical/tactical explanation'))
        print('Evaluated',season,'all20clubs',len(arms),'MM arms',flush=True)
    combined={};combined_intervals={}
    for label,arm in arms.items():
        e=arm.loc[evalmask];combined[label]=metrics(e);combined_intervals[label]=combined_ci(e,arms['best_existing'].loc[evalmask])
    if abs(combined['best_existing']['minute_mae']-10.521391638183292)>1e-12:raise ValueError('Frozen reference mismatch')
    for name,rows in [('overall_metrics',overall),('club_metrics',clubrows),('group_metrics',groups),('calibration',calibration),('paired_intervals',cirows),('top_errors',worst)]:pd.DataFrame(rows).to_csv(OUT/(name+'.csv.gz'if name=='group_metrics'else name+'.csv'),index=False,compression={'method':'gzip','mtime':0}if name=='group_metrics'else None)
    log.to_csv(OUT/'fit_cutoffs.csv',index=False);tuning.to_csv(OUT/'development_selection.csv',index=False)
    # Clean prior-only features separate from the truth/prediction archive.
    cols=KEY+['team_id','gw','cutoff','kickoff_at','known_at','news_eligible','news_state','news_effective_at','return_active','return_prior_p','return_prior_s','return_prior_games','return_kind','prior_type','prior_three_full_starts','single_short_after_three_full','max_history_known_at']+NUM
    feature=f[cols].drop(columns=['known_at'])
    feature.to_csv(OUT/'prior_only_features.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    distribution=[]
    for i,r in f.iterrows():
        a=str(choice['C'][0]);distribution.append(dict(**{k:r[k]for k in KEY},cutoff=str(r.cutoff),conditional_start_mean=raw['C_s:'+a][i],conditional_cameo_mean=raw['C_c:'+a][i],**{k:raw[k+':'+a][i]for k in ['s_sd','s_q10','s_q90','s_p90','c_sd','c_q10','c_q90','c_p1_15']}))
    pd.DataFrame(distribution).to_csv(OUT/'conditional_distributions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    fields=KEY+['gw','team_id','cutoff','p','s','q','c','x','y','minutes','prior_type','news_state']
    packed=[]
    for label,g in arms.items():z=g[fields].copy();z['mode']=label;packed.append(z)
    (OUT/'predictions.npz').write_bytes(encode_frame(pd.concat(packed,ignore_index=True)))
    conflicts=pd.read_csv(ROOT/'analysis/results/mm-probability-robustness-20261016/endpoint_conflicts.csv')
    conflicts['intervention']='No unsupported repair; all new arms preserve source hard exclusions'
    text=conflicts.raw_news.fillna('').str.lower()
    conflicts['source_reason_class']=np.select([conflicts.news_state.eq('SUSPENDED'),text.str.contains('loan|joined|transfer'),text.str.contains('injury|knock|achilles|hamstring|groin|ankle|knee|foot|thigh|shoulder|head|leg'),text.str.contains('fitness'),text.str.contains('personal')],['suspension','registration_or_loan','source_medical_wording','source_fitness','source_personal'],default='unknown')
    conflicts.to_csv(OUT/'false_zero_source_diagnosis.csv',index=False)
    summary=dict(selected=choice,combined=combined,combined_intervals=combined_intervals,component_diagnostics=diagnostic,
        protocol=dict(base_branch='research-role-injury-club-audit-20261016',base_commit='aca5dba',new_branch='research-individual-mm-refinement-20261016',development='2024/25GW14-21 nested prequential tuning; origins fitted only known earlier labels',evaluation='2024/25GW22-38 and2025/26GW6-38, reused research periods NOT independent holdouts',label_clocks='Inherited PL kickoff+4h/3h proxies; not full publication certification',workload='Recorded PL only, not all-competition; unknown rest is missing, no invented injury',return_description='Prior source medical OUT/suspension then explicit AVAILABLE; selection return, NOT clinical clearance',conditional_duration='Personal decayed empirical PMFs plus prequential regularized position-residual prior; no verified exit causes or match-state hazard',false_zero_count=35,hard_caps_never_softened=True,full_mm_only=True,pm_ts_points_chips_run=False,locked_model_active=False,production_changed=False))
    inputs=[BASE/'predictions.npz',ROOT/'scripts/research_individual_mm_refinement.py',ROOT/'analysis/results/mm-probability-robustness-20261016/endpoint_conflicts.csv']
    summary['inputs_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs}
    (OUT/'report.json').write_text(json.dumps(summary,indent=2,default=str,allow_nan=False)+'\n')
    filenames=['overall_metrics.csv','club_metrics.csv','group_metrics.csv.gz','calibration.csv','paired_intervals.csv','top_errors.csv','fit_cutoffs.csv','development_selection.csv','prior_only_features.csv.gz','conditional_distributions.csv.gz','predictions.npz','false_zero_source_diagnosis.csv','report.json']
    manifest={}
    for name in filenames:
        path=OUT/name
        if name.endswith('.npz'):raw_content=load_frame(path).to_csv(index=False).encode()
        else:raw_content=gzip.decompress(path.read_bytes())if name.endswith('.gz')else path.read_bytes()
        manifest[name]=dict(content_sha256=hashlib.sha256(raw_content).hexdigest(),content_bytes=len(raw_content))
    (OUT/'content_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v['minute_mae']for k,v in combined.items()},indent=2),flush=True)


if __name__=='__main__':main()
