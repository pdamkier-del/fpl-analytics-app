import sqlite3, math, json
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

DB='data_v1_1/normalized/fpl_v1_1.sqlite3'
con=sqlite3.connect(DB)
q='''
select p.season,p.gw,p.fixture_uuid,p.player_uuid,p.team_id,p.fpl_position,p.started,p.minutes,p.kickoff_at
from player_fixture_observations p
where p.season in ('2023-24','2024-25','2025-26') and p.is_final=1
order by p.season,p.gw,p.kickoff_at,p.team_id,p.player_uuid
'''
df=pd.read_sql_query(q,con)
df['started']=df.started.astype(int); df['minutes']=df.minutes.fillna(0).astype(float)
# verify actual starters per team fixture
counts=df.groupby(['season','fixture_uuid','team_id']).started.sum()
print('actual starter counts', counts.value_counts().head().to_dict(), 'bad', int((counts!=11).sum()), 'of', len(counts))

# Build deadline-safe historical weighted features using only prior GWs, reset each season/player.
def make_features(h_fast=3.0,h_slow=10.0,h_min=3.0):
    rows=[]
    hist=defaultdict(list)
    # predict in chronological GW order; update after entire GW to avoid DGW leakage
    for season in ['2023-24','2024-25','2025-26']:
        sdf=df[df.season==season]
        for gw in sorted(sdf.gw.dropna().unique()):
            gdf=sdf[sdf.gw==gw]
            for r in gdf.itertuples(index=False):
                h=hist[(season,r.player_uuid)]
                def wavg(field, half, default):
                    vals=[]; ws=[]
                    for pgw,st,mins in h:
                        lag=max(1, int(gw-pgw))
                        w=2**(-lag/half)
                        vals.append(st if field=='start' else mins/90.0); ws.append(w)
                    return float(np.average(vals,weights=ws)) if ws else default
                fast=wavg('start',h_fast,0.25)
                slow=wavg('start',h_slow,0.25)
                minu=wavg('mins',h_min,0.25)
                # immediate prior-GW state
                prev=[x for x in h if x[0]==gw-1]
                last_start=float(np.mean([x[1] for x in prev])) if prev else fast
                last_mins=float(np.mean([x[2] for x in prev]))/90.0 if prev else minu
                rows.append((season,int(gw),r.fixture_uuid,r.player_uuid,int(r.team_id),r.fpl_position,int(r.started),float(r.minutes),fast,slow,minu,last_start,last_mins))
            # update only after all target rows in GW are predicted
            # for DGW keep both fixtures as history entries for future GW
            for r in gdf.itertuples(index=False):
                hist[(season,r.player_uuid)].append((int(gw),int(r.started),float(r.minutes)))
    cols=['season','gw','fixture_uuid','player_uuid','team_id','pos','y','minutes','fast','slow','recent_mins','last_start','last_mins']
    return pd.DataFrame(rows,columns=cols)

def exact11(p, group_keys):
    out=p.copy()
    # shift all logits by common delta inside each team-fixture so sum probabilities = 11
    for idx in group_keys.values():
        arr=np.clip(p.loc[list(idx)].to_numpy(),1e-6,1-1e-6)
        logits=np.log(arr/(1-arr))
        lo,hi=-20.,20.
        for _ in range(70):
            mid=(lo+hi)/2
            s=(1/(1+np.exp(-(logits+mid)))).sum()
            if s<11: lo=mid
            else: hi=mid
        out.loc[list(idx)]=1/(1+np.exp(-(logits+(lo+hi)/2)))
    return out

def evaluate(hf,hs,hm):
    x=make_features(hf,hs,hm)
    # exclude early GWs just like existing benchmark; enough history
    x=x[x.gw>=6].copy()
    X=pd.concat([x[['fast','slow','recent_mins','last_start','last_mins']], pd.get_dummies(x['pos'],prefix='pos',dtype=float)],axis=1)
    dev=x.season.isin(['2023-24','2024-25']); hold=x.season.eq('2025-26')
    model=LogisticRegression(C=1.0,max_iter=500,class_weight=None)
    model.fit(X[dev],x.loc[dev,'y'])
    ph=pd.Series(model.predict_proba(X[hold])[:,1],index=x.index[hold])
    # exact 11 normalize by fixture/team
    groups=x.loc[hold].groupby(['season','fixture_uuid','team_id']).groups
    pc=exact11(ph,groups)
    y=x.loc[hold,'y'].to_numpy()
    raw=(brier_score_loss(y,ph),log_loss(y,ph,labels=[0,1]),float(ph.mean()))
    con=(brier_score_loss(y,pc),log_loss(y,pc,labels=[0,1]),float(pc.mean()))
    return raw,con,model.coef_[0],list(X.columns),len(y)

raw,con,coef,cols,n=evaluate(3.0,10.0,3.0)
print("SINGLE 3/10", "raw", raw, "exact11", con, "n", n)
print("COEFS", dict(zip(cols,coef)))
