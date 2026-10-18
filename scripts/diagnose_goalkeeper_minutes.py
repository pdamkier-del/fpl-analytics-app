#!/usr/bin/env python3
"""Read-only goalkeeper minute diagnostics; NO model mutation.

Compares conditional start duration, MM expected minutes and PM's locked
Gaussian-clipped expectation. A lone available GK is a review signal, not
proof of a guaranteed start.
"""
import argparse
import json
import numpy as np
import pandas as pd
from mm_locked_bridge import locked_sampler_expectation

def diagnose(frame, name='Penders'):
    x=frame.copy()
    if 'name' not in x or 'pos' not in x:
        raise ValueError('Require actual canonical name and pos in snapshot')
    players=x.loc[x.name.astype(str).str.contains(name,case=False,regex=False)&x.pos.isin(['GK','GKP'])]
    if players.empty:raise ValueError('Goalkeeper not found in snapshot')
    out=[]
    for r in players.itertuples(index=False):
        row=pd.DataFrame([r._asdict()])
        needed=['p','q','s','c','x','team_id','fixture_uuid']
        if any(k not in row for k in needed):raise ValueError('Missing MM columns '+','.join(k for k in needed if k not in row))
        pm=locked_sampler_expectation(row.p,row.q,row.s,row.c)
        g=x[(x.fixture_uuid==r.fixture_uuid)&(x.team_id==r.team_id)&x.pos.isin(['GK','GKP'])]
        possible=g.loc[~g.get('news_state',pd.Series(['UNKNOWN']*len(g),index=g.index)).isin(['OUT','SUSPENDED'])]
        out.append(dict(player=r.name,fixture_uuid=r.fixture_uuid,mm_p_start=float(r.p),
            mm_start_minutes=float(r.s),mm_xm=float(r.x),pm_expected_minutes=float(np.asarray(pm)[0]),
            listed_goalkeepers=int(len(g)),not_hard_out_goalkeepers=int(len(possible)),
            review='ONLY_NON_HARD_OUT_GK_CHECK_START_ROLE' if len(possible)==1 else 'VERIFY_OTHER_KEEPERS_AND_TEAM_NEWS',
            note='Do not force 90 minutes; confirm availability, starting choice and historical GK duration.'))
    return out

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--target',required=True);a.add_argument('--name',default='Penders');args=a.parse_args()
    data=pd.read_csv(args.target)
    print(json.dumps(diagnose(data,args.name),indent=2))
