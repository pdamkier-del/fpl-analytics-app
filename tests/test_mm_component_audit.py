import numpy as np
import pandas as pd
from audit_mm_components import error_terms, attribution, prefix_features

def test_signed_identity_and_shapley_conservation():
    rng=np.random.default_rng(10);n=100
    p,q=rng.uniform(size=(2,n));s,c=rng.uniform(1,90,size=(2,n));y=rng.integers(2,size=n)
    m=np.where(y==1,rng.uniform(1,90,n),rng.choice([0,15,25],size=n))
    t=error_terms(p,s,q,c,y,m);e=p*s+(1-p)*q*c-m
    assert np.allclose(t.sum(axis=1),e)
    a=attribution(t)
    assert np.isclose(sum(v['mae_shapley'] for v in a.values()),abs(e).mean())
    assert np.isclose(sum(v['mse_cross_alloc'] for v in a.values()),(e**2).mean())

def test_delayed_previous_gw_and_future_rows_cannot_enter_features():
    rows=[]
    for gw,known,st,m in [(1,'2024-08-02',1,80),(2,'2024-08-20',1,90),(4,'2024-08-09',0,15)]:
        rows.append(dict(fixture_uuid=str(gw),player_uuid='p',gw=gw,team_id=1,started=st,minutes=m,kickoff_at=known,known=pd.Timestamp(known,tz='UTC'),goals=0,fpl_assists=0))
    obs=pd.DataFrame(rows)
    f=pd.DataFrame([dict(player_uuid='p',team_id=1,gw=3,cutoff='2024-08-10T00:00:00Z',new_start_minutes=78)])
    a=prefix_features(f,obs)
    assert a.history_n.iloc[0]==2
    assert a.start_history_mean.iloc[0]==80
    assert a.last_started.iloc[0]==0
    # A future GW number can be observed before cutoff; chronological truth wins.
    obs.loc[obs.gw.eq(2),'minutes']=5
    assert prefix_features(f,obs).duration_h3.iloc[0]==a.duration_h3.iloc[0]

def test_cancellation_not_causal_percentage():
    t=np.array([[10.,-8.,10.,0.]])
    a=attribution(t)
    assert a['starter_duration']['mae_shapley']<0
    assert np.isclose(sum(v['mae_share'] for v in a.values()),1)
