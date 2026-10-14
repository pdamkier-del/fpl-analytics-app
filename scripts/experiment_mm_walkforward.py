#!/usr/bin/env python3
"""Offline temporal MM screen. Configuration selection precedes evaluation reads."""
import argparse,json,sys,hashlib
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_mm_components import load_obs,metrics,score
from fpl_v1_1_model.experimental_mm_research import fit_start,survival_prediction,project_partition

STARTS=[('logistic_'+str(c),c,False) for c in (.1,1.)]+[('hierarchical_'+str(c),c,True) for c in (.1,1.)]
SURV=[('survival_'+str(h)+'_'+str(t),h,t) for h in (21.,42.) for t in (2.,8.)]

def predict(frame,obs,previous=None,previous_obs=None):
    rows=[];audit=[]
    alltrain=frame if previous is None else pd.concat([previous,frame],ignore_index=True)
    allobs=obs if previous_obs is None else pd.concat([previous_obs,obs],ignore_index=True)
    allobs=allobs.rename(columns={'fpl_position':'pos'})
    allobs['pos']=allobs.pos.replace({'GKP':'GK','G':'GK'})
    for gw,g in frame.groupby('gw',sort=True):
        cut=pd.to_datetime(g.cutoff,utc=True).min()
        train=alltrain[pd.to_datetime(alltrain.outcome_known_at,utc=True,format="mixed")<cut]
        if len(train) and (pd.to_datetime(train.outcome_known_at,utc=True,format="mixed")>=cut).any():raise ValueError('Leaky fit')
        audit.append(dict(gw=int(gw),cutoff=str(cut),training_rows=len(train),max_training_known=str(pd.to_datetime(train.outcome_known_at,utc=True,format="mixed").max()) if len(train) else None))
        p=g.new_p_start.to_numpy();s=g.new_start_minutes.to_numpy();q=g.new_q_sub.to_numpy();c=g.new_sub_minutes.to_numpy()
        modes={'original':(p,s),'partition_only':(project_partition(g,p),s),'duration_h3':(p,g.duration_h3.to_numpy()),'duration_h6':(p,g.duration_h6.to_numpy())}
        for name,reg,hierarchy in STARTS:modes[name]=(fit_start(train,g,C=reg,hierarchical=hierarchy),s)
        pool=allobs[(allobs.known<cut)&allobs.started.eq(1)]
        for name,half,strength in SURV:modes[name]=(p,survival_prediction(g,obs,pool,half_days=half,strength=strength))
        for name,(pp,ss) in modes.items():
            r=g.copy();r['mode']=name;r['p']=pp;r['s']=ss;r['q']=q;r['c']=c;r['x']=pp*ss+(1-pp)*q*c;rows.append(r)
        print('MM candidate prefix completed',g.season.iloc[0],gw,flush=True)
    return pd.concat(rows,ignore_index=True),audit

def combined(pred,start,duration):
    keys=['season','fixture_uuid','player_uuid'];a=pred[pred['mode'].eq(start)].copy();b=pred[pred['mode'].eq(duration)].set_index(keys)
    a['s']=b.loc[pd.MultiIndex.from_frame(a[keys]),'s'].to_numpy();a['mode']='combined';a['x']=a.p*a.s+(1-a.p)*a.q*a.c
    return pd.concat([pred,a],ignore_index=True)

def summary(f):
    result={};rng=np.random.default_rng(20261014)
    baseline=f[f['mode'].eq('original')][['fixture_uuid','player_uuid','x']]
    for mode,g in f.groupby('mode'):
        m=metrics(g,p=g.p,s=g.s,q=g.q,c=g.c);pair=g.merge(baseline,on=['fixture_uuid','player_uuid'],suffixes=('','_base'),validate='one_to_one');d=abs(pair.x-pair.minutes)-abs(pair.x_base-pair.minutes)
        b=pd.DataFrame(dict(fixture=pair.fixture_uuid,delta=d)).groupby('fixture').delta.agg(['sum','size']).to_numpy();draw=b[rng.integers(len(b),size=(2000,len(b)))].sum(axis=1)
        m['paired_minute_mae_delta']=float(d.mean());m['fixture_bootstrap_95_ci']=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()
        m['groups']={k:dict(minutes=score(v.minutes,v.x),start_brier=float(((v.p-v.y)**2).mean())) for k,v in g.groupby('player_type')}
        for state,v in g.groupby('team_news_state'):
            m['groups']['team_news_'+str(state)]=dict(minutes=score(v.minutes,v.x),start_brier=float(((v.p-v.y)**2).mean()))
        result[mode]=m
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='analysis/results/mm-research-20261014');ap.add_argument('--db',default='work/core.sqlite3');a=ap.parse_args();out=Path(a.out)
    f24=pd.read_csv(out/'2024-25_features.csv.gz');o24=load_obs(a.db,'2024-25',4)
    p24,fit24=predict(f24,o24)
    dev=p24[p24.gw.between(11,21)];scores=summary(dev)
    start=min((name for name,_,_ in STARTS),key=lambda k:scores[k]['start']['log_loss'])
    duration=min([name for name,_,_ in SURV]+['duration_h3','duration_h6'],key=lambda k:scores[k]['starter_duration']['rmse'])
    protocol=dict(development='2024/25 GW11-21; prefix fits only cutoff-known outcomes',test=['2024/25 GW22-38','2025/26 GW6-38'],start_selection='minimum development start log-loss',duration_selection='minimum development conditional starter-duration RMSE',selected_start=start,selected_duration=duration,selection_timestamp_utc=str(pd.Timestamp.now(tz='UTC')),selection_uses_test_metrics=False,strict_fit_masks=True,source_publication_certified=False,development_metrics=scores)
    # Persist selection before loading the later evaluation season.
    (out/'selection.json').write_text(json.dumps(protocol,indent=2)+'\n')
    p24=combined(p24,start,duration)
    f25=pd.read_csv(out/'2025-26_features.csv.gz');o25=load_obs(a.db,'2025-26',3)
    p25,fit25=predict(f25,o25,previous=f24,previous_obs=o24);p25=combined(p25,start,duration)
    p24.to_csv(out/'2024-25_candidates.csv.gz',index=False,compression='gzip');p25.to_csv(out/'2025-26_candidates.csv.gz',index=False,compression='gzip')
    report=dict(classification='TEMPORAL_COMPONENT_SCREEN_WITH_UNCERTIFIED_SOURCE_CLOCKS',protocol=protocol,results={'2024-25_GW22-38':summary(p24[p24.gw.ge(22)]),'2025-26_GW6-38':summary(p25)},fit_audit={'2024-25':fit24,'2025-26':fit25},promotion_allowed=False,locked_model_active=False,limitations=['Historical kickoff+3/4h availability proxies; not actual publication timestamps','Locked baseline selected partly on these seasons; neither is pristine independent model-development OOS','Medical absence/exit cause/coach/score-at-exit labels unavailable in Core','Prefix workload features use PL observations only, not complete all-competition workload','Survival candidate treats all <90-minute starter departures as all-cause exits; not inferred tactical substitutions','Minute survival mean fed to original Normal PM sampler; full duration distribution not replaced','No historical complete six-GW candidate TS acceptance test'])
    (out/'walkforward_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(selected_start=start,selected_duration=duration,results={k:{m:v['minutes'] for m,v in r.items()} for k,r in report['results'].items()}),indent=2))
if __name__=='__main__':main()
