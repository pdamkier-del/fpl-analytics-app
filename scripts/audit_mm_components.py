#!/usr/bin/env python3
"""Descriptive locked-MM attribution; no model changes or causal claims."""
import argparse, hashlib, itertools, json, math, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
KEYS=['fixture_uuid','player_uuid']
COMPONENTS=['start_selection','starter_duration','sub_appearance','sub_duration']

def error_terms(p,s,q,c,y,m):
    p,s,q,c,y,m=[np.asarray(a,float) for a in (p,s,q,c,y,m)]
    z=((y==0)&(m>0)).astype(float)
    return np.column_stack([(p-y)*(s-q*c),y*(s-m),(1-y)*(q-z)*c,(1-y)*z*(c-m)])

def attribution(terms):
    """Shapley allocation of absolute signed-error sums; cancellation can be negative."""
    total=terms.sum(axis=1); n=terms.shape[1]; shares=np.zeros(n)
    for order in itertools.permutations(range(n)):
        acc=np.zeros(len(total))
        for j in order:
            shares[j]+=np.mean(abs(acc+terms[:,j])-abs(acc));acc+=terms[:,j]
    shares/=math.factorial(n)
    mse=float(np.mean(total**2))
    return {name:dict(signed_bias=float(terms[:,j].mean()),standalone_absolute=float(abs(terms[:,j]).mean()),mae_shapley=float(shares[j]),mae_share=float(shares[j]/np.mean(abs(total))) if np.any(total) else None,mse_cross_alloc=float(np.mean(terms[:,j]*total)),mse_share=float(np.mean(terms[:,j]*total)/mse) if mse else None) for j,name in enumerate(COMPONENTS)}

def prob_score(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);safe=np.clip(p,1e-12,1-1e-12)
    if not len(y):return dict(rows=0)
    bins=[];ece=0.
    for a in np.linspace(0,1,11)[:-1]:
        ix=(p>=a)&(p<(a+.1) if a<.9 else p<=1)
        if not ix.any():continue
        bins.append(dict(lower=float(a),rows=int(ix.sum()),pred=float(p[ix].mean()),actual=float(y[ix].mean())))
        ece+=ix.mean()*abs(p[ix].mean()-y[ix].mean())
    return dict(rows=len(y),brier=float(np.mean((p-y)**2)),log_loss=float(-np.mean(y*np.log(safe)+(1-y)*np.log(1-safe))),bias=float(np.mean(p-y)),mean_pred=float(p.mean()),mean_actual=float(y.mean()),ece10=float(ece),bins=bins)

def score(y,p):
    e=np.asarray(p,float)-np.asarray(y,float)
    return dict(rows=len(e),mae=float(abs(e).mean()),rmse=float(np.sqrt(np.mean(e**2))),bias=float(e.mean())) if len(e) else dict(rows=0)

def metrics(f,p=None,s=None,q=None,c=None):
    p=f.new_p_start.to_numpy() if p is None else np.asarray(p)
    s=f.new_start_minutes.to_numpy() if s is None else np.asarray(s)
    q=f.new_q_sub.to_numpy() if q is None else np.asarray(q)
    c=f.new_sub_minutes.to_numpy() if c is None else np.asarray(c)
    y=f.y.to_numpy();m=f.minutes.to_numpy();sub=(y==0)&(m>0);nostart=y==0
    x=p*s+(1-p)*q*c;t=error_terms(p,s,q,c,y,m)
    if not np.allclose(t.sum(axis=1),x-m,rtol=0,atol=1e-9):raise ValueError('Attribution identity failed')
    probabilities=np.column_stack([p,(1-p)*q,(1-p)*(1-q)])
    state=np.where(y==1,0,np.where(m>0,1,2))
    state_one=np.eye(3)[state]
    return dict(minutes=score(m,x),played=score(m[m>0],x[m>0]),start=prob_score(y,p),sub_appearance=prob_score((m[nostart]>0).astype(int),q[nostart]),starter_duration=score(m[y==1],s[y==1]),sub_duration=score(m[sub],c[sub]),state_log_loss=float(-np.log(np.clip(probabilities[np.arange(len(f)),state],1e-12,1)).mean()),state_brier=float(((probabilities-state_one)**2).sum(axis=1).mean()),attribution=attribution(t))

def load_obs(db,season,hours):
    with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True) as con:
        obs=pd.read_sql_query('SELECT fixture_uuid,player_uuid,gw,team_id,fpl_position,started,minutes,kickoff_at,total_points,goals,fpl_assists,absence_reason,sub_off_second,matchday_squad FROM player_fixture_observations WHERE season=? AND is_final=1',con,params=[season])
    if obs.duplicated(KEYS).any() or obs[['started','minutes','kickoff_at']].isna().any().any():raise ValueError('Incomplete or duplicate actuals')
    if not obs.minutes.between(0,90).all() or not obs.started.isin([0,1]).all():raise ValueError('Invalid outcomes')
    obs['known']=pd.to_datetime(obs.kickoff_at,utc=True)+pd.Timedelta(hours=hours)
    return obs

def prefix_features(frame,obs):
    """Only outcomes strictly available before each target cutoff; never GW-order selection."""
    histories={str(pid):g.sort_values(['known','fixture_uuid']) for pid,g in obs.groupby('player_uuid')}
    teamgames=obs[['fixture_uuid','team_id','kickoff_at','known']].drop_duplicates(['fixture_uuid','team_id'])
    teams={int(t):g.sort_values('known') for t,g in teamgames.groupby('team_id')}
    rows=[]
    for r in frame.itertuples():
        cut=pd.Timestamp(r.cutoff);g=histories.get(str(r.player_uuid));past=g[g.known<cut] if g is not None else obs.iloc[:0]
        starts=past[past.started.eq(1)];subs=past[past.started.eq(0)&past.minutes.gt(0)];played=past[past.minutes.gt(0)]
        tail=past.tail(6);streak=0
        for v in past.started.to_numpy()[::-1]:
            if v!=1:break
            streak+=1
        team=teams[int(r.team_id)];team=team[team.known<cut]
        rec=dict(history_n=len(past),start_share6=float(tail.started.mean()) if len(tail) else 0.,last_started=float(past.started.iloc[-1]) if len(past) else 0.,start_streak=streak,days_since_play=float((cut-pd.to_datetime(played.kickoff_at.iloc[-1],utc=True)).total_seconds()/86400) if len(played) else 60.,team_rest_days=float((cut-pd.to_datetime(team.kickoff_at.iloc[-1],utc=True)).total_seconds()/86400) if len(team) else 60.,minutes_14d=float(past[pd.to_datetime(past.kickoff_at,utc=True)>cut-pd.Timedelta(days=14)].minutes.sum()),start_history_mean=float(starts.minutes.mean()) if len(starts) else 78.,sub_history_mean=float(subs.minutes.mean()) if len(subs) else 16.,prior_goals_assists90=float(90*(past.goals.sum()+past.fpl_assists.sum())/past.minutes.sum()) if past.minutes.sum()>0 else 0.,max_history_known=str(past.known.max()) if len(past) else None)
        if len(tail)>=6 and tail.started.eq(1).all():group='regular'
        elif len(tail)>=3 and tail.started.mean()<=.2:group='reserve'
        else:group='rotation_or_short_history'
        rec['player_type']=group
        rec['high_prior_production']=bool(group=='regular' and rec['prior_goals_assists90']>=.5)
        rec['long_gap_proxy']=bool(len(played) and rec['days_since_play']>=21)
        # A gap is not a medical label. Extra competitions are absent from this Core ledger.
        for half in (1.,3.,6.):
            if len(starts):
                lag=np.arange(len(past)-1,-1,-1)[past.started.to_numpy()==1];w=np.exp2(-lag/half)
                rec['duration_h'+str(int(half))]=float(w@starts.minutes.to_numpy()/w.sum())
            else:rec['duration_h'+str(int(half))]=float(r.new_start_minutes)
        rows.append(rec)
    return pd.concat([frame.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

def prepare(mm,db,season):
    frame=pd.read_csv(mm);hours=4 if season=='2024-25' else 3;obs=load_obs(db,season,hours)
    truth=obs[KEYS+['kickoff_at','known','started','minutes']]
    merged=frame.merge(truth,on=KEYS,validate='one_to_one',suffixes=('','_actual'))
    if len(merged)!=len(frame) or not np.array_equal(merged.y,merged.started) or not np.array_equal(merged.minutes,merged.minutes_actual):raise ValueError('Archived outcome identity mismatch')
    legal=pd.to_datetime(merged.cutoff,utc=True)<pd.to_datetime(merged.kickoff_at,utc=True)
    excluded=merged.loc[~legal,KEYS+['gw','cutoff','kickoff_at']].to_dict('records');merged=merged.loc[legal].copy()
    merged['season']=season
    composed=merged.new_p_start*merged.new_start_minutes+(1-merged.new_p_start)*merged.new_q_sub*merged.new_sub_minutes
    discrepancy=float(abs(composed-merged.new_xmins).max())
    f=prefix_features(merged,obs)
    return f,obs,dict(rows=len(f),excluded_already_started=excluded,max_composition_discrepancy=discrepancy,medical_label_rows=int(obs.absence_reason.notna().sum()),substitution_timestamp_rows=int(obs.sub_off_second.notna().sum()),matchday_squad_rows=int(obs.matchday_squad.notna().sum()),availability_proxy_hours=hours,source_sha256=hashlib.sha256(Path(mm).read_bytes()).hexdigest())

def audit(frame):
    group={g:metrics(f) for g,f in frame.groupby('player_type')}
    for label,mask in [('high_prior_production',frame.high_prior_production),('long_gap_not_verified_injury',frame.long_gap_proxy)]:
        if mask.any():group[label]=metrics(frame[mask])
    sums=frame.groupby(['fixture_uuid','team_id']).new_p_start.sum()
    keeper=frame[frame.pos.isin(['GK','GKP'])].groupby(['fixture_uuid','team_id']).new_p_start.sum()
    return dict(all=metrics(frame),groups=group,xi=dict(team_rows=len(sums),max_start_sum_error=float(abs(sums-11).max()),max_keeper_sum_error=float(abs(keeper-1).max()),note='Marginal sums do not guarantee eleven starters in independent simulation'))

def haaland():
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    inputs=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False);hist=pd.read_csv(base/'player_fixture_observations.csv.gz')
    r=inputs[(inputs.fpl_element==411)&(inputs.target_gw==7)].iloc[0];past=hist[hist.fpl_element.eq(411)].sort_values('kickoff_at')
    h=.32192611540889443;w=np.exp2(-np.arange(len(past)-1,-1,-1)/h);p=float(r.p_start);s=float(r.start_minutes_mean);q=float(r.p_cameo_given_bench);c=float(r.mm_sub_minutes if 'mm_sub_minutes' in r else r.cameo_minutes_mean)
    return dict(cutoff=str(r.cutoff),history=past[['gw','started','minutes','kickoff_at']].to_dict('records'),duration_half_life=h,duration_weights=(w/w.sum()).tolist(),p_start=p,start_minutes=s,p_sub_given_not_start=q,sub_minutes=c,starter_contribution=p*s,sub_contribution=(1-p)*q*c,composed_xmins=p*s+(1-p)*q*c,published_xmins=float(r.xmins),loss_from_90_start_nonstart_probability=(1-p)*(90-q*c),loss_from_start_duration=p*(90-s),available_input_layers={k:float(r[k]) for k in ['control_p_start','v4_workload_start_p_start','v4_start_minutes_mean','v4_cameo_minutes_mean','v4_p_cameo_given_bench','work_minutes_7d','work_minutes_14d','seq_start_streak'] if k in r})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',default='work/core.sqlite3');ap.add_argument('--mm2024',default='analysis/results/conditional-2024-25-mm/locked_mm_predictions.csv.gz');ap.add_argument('--mm2025',default='analysis/results/full-model-audit-20261012/locked-2125/locked-mm-final-gw6-38/locked_mm_predictions.csv.gz');ap.add_argument('--out',default='analysis/results/mm-research-20261014');a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True);report=dict(classification='DESCRIPTIVE_LOCKED_MM_ATTRIBUTION_NOT_CAUSAL',seasons={},haaland=haaland(),locked_model_active=False)
    for season,path in [('2024-25',a.mm2024),('2025-26',a.mm2025)]:
        f,obs,coverage=prepare(path,a.db,season);f.to_csv(out/f'{season}_features.csv.gz',index=False,compression='gzip');report['seasons'][season]=dict(coverage=coverage,**audit(f))
    (out/'component_audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({s:r['all'] for s,r in report['seasons'].items()},indent=2));print(json.dumps(report['haaland'],indent=2))
if __name__=='__main__':main()
