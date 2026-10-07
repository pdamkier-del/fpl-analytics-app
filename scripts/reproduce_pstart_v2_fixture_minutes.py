from pathlib import Path
import sqlite3, json
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from fpl_v1_1_model.minutes import project_minutes

ROOT=Path(__file__).resolve().parents[1]
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('--db',required=True)
ap.add_argument('--out',required=True)
ap.add_argument('--min-gw',type=int,default=6)
a=ap.parse_args()
DB=Path(a.db)
OUT=Path(a.out)
OUT.mkdir(parents=True,exist_ok=True)
con=sqlite3.connect(DB.resolve().as_uri()+'?mode=ro', uri=True)
df=pd.read_sql_query('''
select p.season,p.gw,p.fixture_uuid,p.player_uuid,p.team_id,p.fpl_position,p.started,p.minutes,p.kickoff_at
from player_fixture_observations p
where p.season in ('2023-24','2024-25','2025-26') and p.is_final=1
order by p.season,p.gw,p.kickoff_at,p.team_id,p.player_uuid
''',con)
df['started']=df.started.fillna(0).astype(int); df['minutes']=df.minutes.fillna(0).astype(float)

def make_features(h_fast=3.0,h_slow=10.0,h_min=3.0):
    rows=[]; hist=defaultdict(list)
    for season in ['2023-24','2024-25','2025-26']:
        sdf=df[df.season==season]
        for gw in sorted(sdf.gw.dropna().unique()):
            gdf=sdf[sdf.gw==gw]
            for r in gdf.itertuples(index=False):
                h=hist[(season,r.player_uuid)]
                def wavg(field,half,default):
                    vals=[]; ws=[]
                    for pgw,st,mins in h:
                        lag=max(1,int(gw-pgw)); w=2**(-lag/half)
                        vals.append(st if field=='start' else mins/90.0); ws.append(w)
                    return float(np.average(vals,weights=ws)) if ws else default
                fast=wavg('start',h_fast,.25); slow=wavg('start',h_slow,.25); minu=wavg('mins',h_min,.25)
                prev=[x for x in h if x[0]==gw-1]
                last_start=float(np.mean([x[1] for x in prev])) if prev else fast
                last_mins=float(np.mean([x[2] for x in prev]))/90. if prev else minu
                rows.append((season,int(gw),r.fixture_uuid,r.player_uuid,int(r.team_id),str(r.fpl_position),int(r.started),float(r.minutes),fast,slow,minu,last_start,last_mins))
            for r in gdf.itertuples(index=False):
                hist[(season,r.player_uuid)].append((int(gw),int(r.started),float(r.minutes)))
    return pd.DataFrame(rows,columns=['season','gw','fixture_uuid','player_uuid','team_id','pos','y','minutes','fast','slow','recent_mins','last_start','last_mins'])

def exact11_series(ph, frame):
    out=ph.copy()
    groups=frame.groupby(['season','fixture_uuid','team_id']).groups
    for _,idx in groups.items():
        inds=list(idx); arr=np.clip(ph.loc[inds].to_numpy(),1e-8,1-1e-8)
        logits=np.log(arr/(1-arr)); lo,hi=-30.,30.
        for _ in range(80):
            mid=(lo+hi)/2; s=(1/(1+np.exp(-(logits+mid)))).sum()
            if s<11: lo=mid
            else: hi=mid
        out.loc[inds]=1/(1+np.exp(-(logits+(lo+hi)/2)))
    return out

x=make_features(); x=x[x.gw>=a.min_gw].copy()
feat=['fast','slow','recent_mins','last_start','last_mins']
X=pd.concat([x[feat],pd.get_dummies(x['pos'],prefix='pos',dtype=float)],axis=1)
# Ensure stable columns
for c in ['pos_DEF','pos_FWD','pos_GK','pos_GKP','pos_MID']:
    if c not in X: X[c]=0.0
# sklearn tolerates extra; keep actual learned set across dev/holdout
cols=list(X.columns)
dev=x.season.isin(['2023-24','2024-25']); hold=x.season.eq('2025-26')
model=LogisticRegression(C=1.0,max_iter=1000)
model.fit(X.loc[dev,cols],x.loc[dev,'y'])
ph=pd.Series(model.predict_proba(X.loc[hold,cols])[:,1],index=x.index[hold],name='p_start_v2_raw')
hf=x.loc[hold].copy(); hf['p_start_v2_raw']=ph
hf['p_start_v2']=exact11_series(ph,hf)
# Duration/cameo params kept from frozen Phase 3A; only P(start) changes.
ROLE_H=1.3150986300759975; DUR_H=0.32192611540889443; LI=0.03186876473704488; LS=0.6645162300313383
obs25=df[df.season.eq('2025-26')].copy()
hist_by={pid:g.sort_values(['gw','kickoff_at'])[['gw','started','minutes']].to_dict('records') for pid,g in obs25.groupby('player_uuid')}
sm=[]; cm=[]; pc=[]; oldps=[]; oldxm=[]; newxm=[]; newplay=[]
for r in hf.itertuples(index=False):
    h=[z for z in hist_by.get(r.player_uuid,[]) if int(z['gw'])<int(r.gw)]
    p=project_minutes(h,role_half_life=ROLE_H,duration_half_life=DUR_H,start_logit_intercept=LI,start_logit_slope=LS,availability=1.0)
    ps=float(r.p_start_v2)
    xm=ps*p.expected_minutes_given_start+(1-ps)*p.p_cameo_given_bench*p.expected_minutes_given_cameo
    pp=ps+(1-ps)*p.p_cameo_given_bench
    sm.append(p.expected_minutes_given_start); cm.append(p.expected_minutes_given_cameo); pc.append(p.p_cameo_given_bench)
    oldps.append(p.p_start); oldxm.append(p.expected_minutes); newxm.append(xm); newplay.append(pp)
hf['old_p_start_reconstructed']=oldps; hf['old_expected_minutes_reconstructed']=oldxm
hf['start_minutes_mean']=sm; hf['cameo_minutes_mean']=cm; hf['p_cameo_given_bench']=pc
hf['expected_minutes_v2']=newxm; hf['p_play_v2']=newplay
outcols=['season','gw','fixture_uuid','player_uuid','team_id','pos','y','minutes','p_start_v2_raw','p_start_v2','expected_minutes_v2','p_play_v2','old_p_start_reconstructed','old_expected_minutes_reconstructed','start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench']
hf[outcols].to_csv(OUT/'pstart_v2_fixture_holdout_2025_26.csv',index=False)
y=hf.y.to_numpy(); p=hf.p_start_v2.to_numpy()
res={
 'train_seasons':['2023-24','2024-25'],'holdout':'2025-26','min_gw':int(a.min_gw),'n':len(hf),
 'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,p,labels=[0,1])),
 'mean_p_start':float(p.mean()),'actual_start_rate':float(y.mean()),
 'coefficients':{'intercept':float(model.intercept_[0]),**{c:float(v) for c,v in zip(cols,model.coef_[0])}},
 'half_lives':{'fast':3.0,'slow':10.0,'minutes':3.0},
 'exact11_max_abs_error':float(hf.groupby(['fixture_uuid','team_id']).p_start_v2.sum().sub(11).abs().max()),
 'mean_expected_minutes_v2':float(hf.expected_minutes_v2.mean()),
 'mean_old_expected_minutes_reconstructed':float(hf.old_expected_minutes_reconstructed.mean())
}
(OUT/'metrics.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))
