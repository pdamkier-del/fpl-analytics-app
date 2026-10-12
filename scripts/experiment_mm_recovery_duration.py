#!/usr/bin/env python3
"""Read-only duration smoothing for a player returning after one zero-minute GW.

Dev GW22-28 selects beta; GW29-38 is separated chronological test,
but both are REUSED 2025/26 MM diagnostic (not independent certification).

Candidate changes only conditional START duration for selected returners;
leaves exact-11 P(start), sub probability, team formation and PM untouched.
Uses prior observed starts only.
"""
import json
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
p=pd.read_csv(ROOT/'analysis/results/mm-unified-official-roles-20261006-v1/reused_diagnostic_predictions.csv.gz',low_memory=False)
h=pd.read_csv(ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz',usecols=['gw','player_uuid','y','minutes'],low_memory=False)
h=h[h.gw.ge(6)].drop_duplicates(['player_uuid','gw','y','minutes'])
past={str(pid):g.sort_values('gw')[['gw','y','minutes']].to_dict('records') for pid,g in h.groupby('player_uuid')}
p['gw']=p.gw.astype(int)
p=p[p.gw.between(22,38)].copy().reset_index(drop=True)
for col in ['mm_p_start','mm_xmins','mm_q_sub','mm_sub_minutes','minutes','y']:p[col]=pd.to_numeric(p[col],errors='raise')
assert len(p)>10000 and not p.duplicated(['fixture_uuid','player_uuid']).any()
mask=[];healthy=[];current=[]
for v in p.itertuples(index=False):
    priors={int(r['gw']):r for r in past.get(str(v.player_uuid),[]) if int(r['gw'])<int(v.gw)}
    old=[priors.get(int(v.gw)-j) for j in range(1,7)]
    def starts(r):return r is not None and float(r['y'])==1
    flag=bool(all(r is not None for r in old[:5]) and starts(old[0]) and float(old[1]['minutes'])==0 and
             sum(starts(r) for r in old[2:6])>=2)
    past_starts=[float(r['minutes']) for r in old if starts(r)]
    flag=flag and len(past_starts)>=3
    mask.append(flag)
    healthy.append(float(np.mean(past_starts)) if flag else np.nan)
    ps=float(v.mm_p_start)
    if ps>1e-8:
        sm=(float(v.mm_xmins)-(1-ps)*float(v.mm_q_sub)*float(v.mm_sub_minutes))/ps
    else:sm=np.nan
    current.append(sm)
p['returner']=mask;p['healthy_starter_mean']=healthy;p['old_starter_mean']=current
cohort=p[p.returner]
assert 60<=len(cohort)<=300,len(cohort)
assert cohort.old_starter_mean.between(0,90).all()
BETAS=[0.,.25,.5,.75,1.]
for beta in BETAS:
    key='smoothed_'+str(beta)
    # Only a documented rebound after a missed game; all other xM unchanged.
    delta=(p.healthy_starter_mean-p.old_starter_mean).fillna(0).to_numpy(float)
    p[key]=p.mm_xmins + p.mm_p_start.to_numpy(float)*beta*delta*p.returner.to_numpy(int)
    if not p[key].between(0,90.0001).all():raise AssertionError('Projected minutes outside 0..90')
def metric(frame,col):
    error=frame[col].to_numpy(float)-frame.minutes.to_numpy(float)
    return dict(n=len(frame),rmse=round(float(np.sqrt(np.mean(error*error))),5),mae=round(float(np.mean(abs(error))),5),
                mean_forecast=round(float(frame[col].mean()),4),mean_actual=round(float(frame.minutes.mean()),4),
                bias=round(float(error.mean()),5))
dev=p[p.gw.between(22,28)];hold=p[p.gw.between(29,38)]
assert len(dev)>3500 and len(hold)>4500
devco=dev[dev.returner];holdco=hold[hold.returner]
assert len(devco)>=15 and len(holdco)>=30,(len(devco),len(holdco))
cols=['smoothed_'+str(x) for x in BETAS]
a={c:metric(devco,c) for c in cols}
selection=min(cols,key=lambda k:(a[k]['rmse'],a[k]['mae']))
report=dict(classification='READ_ONLY_START_DURATION_SMOOTHING_REUSED_2025_26_DIAGNOSTIC',
    design='only post-zero returned healthy starters, sm_new=sm_old+beta*(mean last observed starts-sm_old)',
    beta_candidates=BETAS,dev_gw22_28_returners=a,
    selected_on_dev=selection,
    holdout_gw29_38_returners={c:metric(holdco,c) for c in cols},
    holdout_gw29_38_all={c:metric(hold,c) for c in cols},
    returner_examples=cohort.sort_values('old_starter_mean')[['player','team','gw','healthy_starter_mean','old_starter_mean','mm_p_start','mm_xmins','minutes','smoothed_0.5']].head(10).round(3).to_dict('records'),
    frozen_input_changed=False,model_promoted=False,
    limitations='Reused MM results from same 2025/26 season; candidate is not validated on an independent season and is not the exact final live MM including XI',
)
out=ROOT/'work/live-final-model/mm_recovery_duration_ab.json'
out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
for k in ['selected_on_dev','dev_gw22_28_returners','holdout_gw29_38_returners','holdout_gw29_38_all']:
    print('MM_DURATION_'+k.upper(),json.dumps(report[k],ensure_ascii=False))
