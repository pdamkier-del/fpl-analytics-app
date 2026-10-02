from pathlib import Path
import math, json, sys
import numpy as np, pandas as pd
ROOT=Path('/mnt/data/fpl5e/fpl-xpts-2026-27')
FPL5Y=Path('/mnt/data/fpl5y')
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.minutes import project_minutes
OUT=Path('/mnt/data/pstart_v2_longrun'); OUT.mkdir(parents=True,exist_ok=True)
GWS=pd.read_csv(ROOT/'data/cache/history/2025-26/gws/merged_gw.csv',low_memory=False)
ROLL=pd.read_csv(FPL5Y/'outputs/v1_1/phase5t_rolling_reference/rolling_phase5q_forecasts.csv',low_memory=False)
# Fixed on 2023/24+2024/25 only. 2025/26 is never used to fit these coefficients.
COEF={
'intercept':-3.0074696650,'fast':-2.2237219401,'slow':1.5813870992,
'recent_mins':4.8495162559,'last_start':-1.6896450163,'last_mins':4.2126430435,
'pos_DEF':-0.4763683881,'pos_FWD':-0.5989799648,'pos_GK':-0.7352321599,'pos_GKP':0.0,'pos_MID':-0.4605718143,
}
ROLE_H=1.3150986300759975; DUR_H=0.32192611540889443; LI=0.03186876473704488; LS=0.6645162300313383
HF=3.; HS=10.; HM=3.; LAMBDA=0.70; RATE_MAX=12.0
GWS['starts']=pd.to_numeric(GWS.starts,errors='coerce').fillna(0).astype(int)
GWS['minutes']=pd.to_numeric(GWS.minutes,errors='coerce').fillna(0.).astype(float)
GWS['element']=GWS.element.astype(int); GWS['GW']=GWS.GW.astype(int)
# history rows fixture-level, oldest to newest
hist={int(pid):g.sort_values(['GW','kickoff_time','fixture'])[['GW','starts','minutes']].to_dict('records') for pid,g in GWS.groupby('element')}

def wavg(rows, field, half, D, default=.25):
    vals=[]; ws=[]
    for z in rows:
        gw=int(z['GW'])
        if gw>=D: continue
        lag=max(1,D-gw); w=2**(-lag/half)
        vals.append(float(z['starts']) if field=='start' else float(z['minutes'])/90.0); ws.append(w)
    return float(np.average(vals,weights=ws)) if ws else default

def exact11(group):
    arr=np.clip(group['p_raw'].to_numpy(float),1e-8,1-1e-8)
    logits=np.log(arr/(1-arr)); lo,hi=-30.,30.
    for _ in range(80):
        mid=(lo+hi)/2; s=(1/(1+np.exp(-(logits+mid)))).sum()
        if s<11: lo=mid
        else: hi=mid
    return pd.Series(1/(1+np.exp(-(logits+(lo+hi)/2))),index=group.index)

states=[]
for D in range(6,39):
    # team/position known for this deadline's GW; duplicate rows collapsed (DGW safe)
    meta=GWS[GWS.GW==D].sort_values('kickoff_time').drop_duplicates('element',keep='first')[['element','team','position']].copy()
    rows=[]
    for r in meta.itertuples(index=False):
        pid=int(r.element); h=[z for z in hist.get(pid,[]) if int(z['GW'])<D]
        fast=wavg(h,'start',HF,D); slow=wavg(h,'start',HS,D); rm=wavg(h,'mins',HM,D)
        prev=[z for z in h if int(z['GW'])==D-1]
        last_start=float(np.mean([z['starts'] for z in prev])) if prev else fast
        last_mins=float(np.mean([z['minutes'] for z in prev]))/90.0 if prev else rm
        pos=str(r.position)
        z=(COEF['intercept']+COEF['fast']*fast+COEF['slow']*slow+COEF['recent_mins']*rm+
           COEF['last_start']*last_start+COEF['last_mins']*last_mins+COEF.get('pos_'+pos,0.0))
        p_raw=1/(1+math.exp(-max(-30,min(30,z))))
        hh=[{'started':int(z0['starts']),'minutes':float(z0['minutes'])} for z0 in h]
        old=project_minutes(hh,role_half_life=ROLE_H,duration_half_life=DUR_H,start_logit_intercept=LI,start_logit_slope=LS,availability=1.0)
        rows.append({'decision_gw':D,'id':pid,'team':str(r.team),'position':pos,'fast':fast,'slow':slow,'recent_mins':rm,'last_start':last_start,'last_mins':last_mins,'p_raw':p_raw,
                     'old_p_start':old.p_start,'old_xmins':old.expected_minutes,'p_cameo':old.p_cameo_given_bench,'start_mins':old.expected_minutes_given_start,'cameo_mins':old.expected_minutes_given_cameo})
    f=pd.DataFrame(rows)
    f['p_start_v2']=f.groupby('team',group_keys=False).apply(exact11,include_groups=False).sort_index()
    f['new_xmins']=f.p_start_v2*f.start_mins+(1-f.p_start_v2)*f.p_cameo*f.cameo_mins
    f['p_play_v2']=f.p_start_v2+(1-f.p_start_v2)*f.p_cameo
    states.append(f)
state=pd.concat(states,ignore_index=True)
state.to_csv(OUT/'pstart_v2_deadline_states_2025_26.csv',index=False)
# diagnostics exact 11
sums=state.groupby(['decision_gw','team']).p_start_v2.sum()
print('state rows',len(state),'max sum error',float((sums-11).abs().max()),'mean old/new mins',state.old_xmins.mean(),state.new_xmins.mean())

adj=ROLL.copy()
adj['xpts_mean_old']=adj.xpts_mean
adj['p_play_old']=adj.p_play
s=state[['decision_gw','id','old_xmins','new_xmins','p_play_v2','p_start_v2']]
adj=adj.merge(s,on=['decision_gw','id'],how='left')
mask=(adj.decision_gw>=6)&adj.new_xmins.notna()
# fixture total minute exposure; target fixtures=0 stays untouched.
fx=adj.fixtures.fillna(1).astype(float).clip(lower=0)
old_total=adj.old_xmins*fx; new_total=adj.new_xmins*fx
rate=np.divide(adj.xpts_mean_old.to_numpy(float), (old_total.to_numpy(float)/90.0), out=np.zeros(len(adj)), where=old_total.to_numpy(float)>2.0)
rate=np.clip(rate,0,RATE_MAX)
delta=(new_total-old_total).to_numpy(float)/90.0
newx=adj.xpts_mean_old.to_numpy(float)+LAMBDA*delta*rate
adj.loc[mask,'xpts_mean']=np.maximum(0,newx[mask.to_numpy()])
adj.loc[mask,'p_play']=adj.loc[mask,'p_play_v2'].clip(0,1)
# Cold-start GW1-5 exactly frozen.
assert np.allclose(adj.loc[adj.decision_gw<6,'xpts_mean'],adj.loc[adj.decision_gw<6,'xpts_mean_old'])
cols=['origin_gw','decision_gw','gw','id','web_name','position','xpts_mean','fixtures','p_play']
adj[cols].to_csv(OUT/'rolling_phase5q_pstart_v2_forecasts.csv',index=False)
# Save audit version too
adj.to_csv(OUT/'rolling_phase5q_pstart_v2_audit.csv',index=False)
summary={
 'method':'frozen Phase5Q forecasts + cutoff-safe P(start) v2 minutes-only correction',
 'development_seasons':['2023-24','2024-25'],'holdout':'2025-26','v2_applied_decision_gw_min':6,
 'half_lives':{'fast':HF,'slow':HS,'recent_minutes':HM},'exact11_max_abs_error':float((sums-11).abs().max()),
 'rolling_rows':int(len(adj)),'adjusted_rows':int(mask.sum()),'mean_abs_xpts_change_adjusted':float((adj.loc[mask,'xpts_mean']-adj.loc[mask,'xpts_mean_old']).abs().mean()),
 'mean_xpts_change_adjusted':float((adj.loc[mask,'xpts_mean']-adj.loc[mask,'xpts_mean_old']).mean()),
 'mechanical_xpts_mapping':{'lambda':LAMBDA,'per90_rate_clip':[0,RATE_MAX],'calibrated_against':'old vs exact new Phase5E simulator outputs only; no actual-points labels'},
}
(OUT/'rolling_v2_build_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
