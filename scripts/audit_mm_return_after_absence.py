#!/usr/bin/env python3
"""Read-only calibration diagnosis of locked MM after one-game absence.

Uses the ALREADY PRODUCED reused 2025/26 diagnostic rows and strictly
prior-gameweek observed player histories. Observed minute labels only score
the forecast; they are never used to classify pre-GW exposure.
This is a reused diagnostic, not independent holdout.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'analysis/results/mm-unified-official-roles-20261006-v1/reused_diagnostic_predictions.csv.gz'
H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
p=pd.read_csv(P,low_memory=False)
h=pd.read_csv(H,usecols=['gw','player_uuid','y','minutes'],low_memory=False)
p['gw']=pd.to_numeric(p.gw,errors='raise').astype(int)
h['gw']=pd.to_numeric(h.gw,errors='raise').astype(int)
assert {'player_uuid','mm_p_start','mm_xmins','minutes','y'}.issubset(p)
assert p.gw.between(22,38).all() and p.gw.nunique()>=12 and not p.duplicated(['fixture_uuid','player_uuid']).any()
assert h.gw.max()>=p.gw.max()
h=h[h.gw>=6].drop_duplicates(['player_uuid','gw','minutes','y'])
prior={}
for pid,g in h.groupby('player_uuid'):
    prior[str(pid)]=g.sort_values('gw')[['gw','y','minutes']].to_dict('records')
segments=[]
for v in p.itertuples(index=False):
    pre=[r for r in prior.get(str(v.player_uuid),[]) if int(r['gw'])<int(v.gw)]
    bygw={int(r['gw']):r for r in pre}
    # Only recent consecutive GWs count; missing data is not a zero.
    old=[bygw.get(int(v.gw)-j) for j in range(1,7)]
    def start(r):return r is not None and float(r['y'])>0
    def absent(r):return r is not None and float(r['minutes'])==0
    prev=old[0] if len(old) else None
    anchor=old[1:5]
    settled=all(v is not None for v in old[:5])
    previous_return=bool(settled and start(old[0]) and absent(old[1]) and
            sum(start(z) for z in old[2:6] if z is not None)>=2)
    missed_last=bool(settled and absent(old[0]) and sum(start(z) for z in old[1:5])>=3)
    stable=bool(settled and all(start(z) for z in old[:5]))
    rows=[('all',True),('return_after_one_zero',previous_return),
          ('zero_last_gw_after_3_starts',missed_last),('five_straight_starts',stable),
          ('last_start_under_80',bool(start(prev) and float(prev['minutes'])<80))]
    for label,ok in rows:
        if ok:segments.append(dict(slice=label,gw=int(v.gw),p_start=float(v.mm_p_start),
              xmins=float(v.mm_xmins),minutes=float(v.minutes),started=float(v.y)))
frame=pd.DataFrame(segments)
assert (frame.slice=='all').sum()==len(p)
scores={}
for name,g in frame.groupby('slice'):
    y=g.minutes.to_numpy(float);xm=g.xmins.to_numpy(float)
    scores[name]=dict(n=len(g),gws=sorted(map(int,g.gw.unique())),mean_p_start=round(float(g.p_start.mean()),5),
       actual_start_rate=round(float(g.started.mean()),5),
       predicted_mean_minutes=round(float(xm.mean()),4),
       actual_mean_minutes=round(float(y.mean()),4),
       minutes_bias=round(float((xm-y).mean()),4),
       mae=round(float(np.mean(np.abs(xm-y))),4),
       rmse=round(float(np.sqrt(np.mean((xm-y)**2))),4),
       actual_minutes_if_started=round(float(g[g.started>0].minutes.mean()),4) if g.started.gt(0).any() else None)
out={'classification':'READ_ONLY_REUSED_MM_DIAGNOSTIC_NO_NEW_HOLDOUT',
     'window':'2025/26 GW22-38 previously used in project model inspection',
     'scores':scores,'note':'Historical unavailability cause is not independently classified; zeros can be injury or rotation; inspect bias only.',
     'model_changed':False}
ROOT.joinpath('work/live-final-model/mm_return_absence_calibration.json').write_text(json.dumps(out,indent=2)+'\n')
for name in scores:print('RETURN_MM_AUDIT',json.dumps({'slice':name,**scores[name]}))
