import pandas as pd
from fpl_xpts.initial_squad_joint import InitialSquadConfig,optimize_initial_squad_joint

def test_initial_joint_builds_legal_15_and_uses_horizon():
    rows=[]
    pid=1
    specs=[('GKP',2),('DEF',6),('MID',6),('FWD',4)]
    meta=[]
    for pos,n in specs:
        for _ in range(n):
            meta.append({'id':pid,'position':pos,'team':pid,'price_tenths':50})
            for gw in (1,2):
                # Player 18 is weak now but huge next GW; horizon should be able
                # to value future contribution rather than GW1 only.
                x=20.0 if (pid==18 and gw==2) else (1.0 if pid==18 else 5.0)
                rows.append({'id':pid,'gw':gw,'xpts_mean':x,'p_play':1.0})
            pid+=1
    meta=pd.DataFrame(meta);p=pd.DataFrame(rows)
    r=optimize_initial_squad_joint(
        p,meta,1,InitialSquadConfig(weights=(1.0,1.0),budget_tenths=1000,time_limit=10,mip_rel_gap=0)
    )
    assert len(r.squad_ids)==15
    sm=meta[meta.id.isin(r.squad_ids)]
    assert sm.position.value_counts().to_dict()=={'MID':5,'DEF':5,'FWD':3,'GKP':2}
    assert 18 in r.squad_ids
    assert all(len(x)==11 for x in r.lineups.values())
