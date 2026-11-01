"""Bounded exact-reference contracts; these toys are not accuracy evidence."""
import numpy as np
import pandas as pd
from precision_audit.decisions import scorer,exact_lineup,exact_candidates,financing_bundles
from fpl_xpts.season_replay import ReplayState,OwnedPlayer

def meta():
    positions=[1,1]+[2]*5+[3]*5+[4]*3+[3,4]
    names={1:'GKP',2:'DEF',3:'MID',4:'FWD'}
    return pd.DataFrame([dict(id=i,element_type=p,position=names[p],team=(i-1)%6,price_tenths=100)for i,p in enumerate(positions,1)])

def test_exact_joint_policy_matches_deterministic_legal_optimum():
    m=meta().iloc[:15];points=np.tile(np.arange(1,16),(4,1));s=scorer(m,points,np.full_like(points,90),10)
    r=exact_lineup(s,10,list(m.id))
    assert r['score']==119 # 3-4-3: 104 from XI plus captain 15.
    assert r['policy']['captain']==15
    assert len(r['policy']['xi'])==11 and len(r['policy']['bench'])==4

def test_exact_pool_keeps_negative_financing_leg_when_bundle_is_legal():
    m=meta();m.loc[m.id.eq(16),'price_tenths']=1;m.loc[m.id.eq(17),'price_tenths']=150
    state=ReplayState({i:OwnedPlayer(i,100)for i in range(1,16)},0,2)
    candidates=exact_candidates(state,m);desired=(set(range(1,16))-{8,13})|{16,17}
    assert desired in candidates
    assert (set(range(1,16))-{13})|{17}not in candidates
    values={i:5. for i in m.id};values.update({8:5.,13:1.,16:4.,17:10.})
    origin=pd.DataFrame([dict(id=i,xpts_mean=v)for i,v in values.items()])
    assert desired in financing_bundles(candidates,state,m,origin)
