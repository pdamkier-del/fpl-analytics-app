#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import run_transfer_strategy_v3_replay as ts

WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)
BUFFER=1.0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vfinal',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,cold=ts.prepare()
    # Cold-start provider is retained only for decisions GW1-5 (origin_gw 0-4).
    cold=cold[cold.origin_gw<=4].copy()
    vf=pd.read_csv(a.vfinal)
    vf['web_name']=vf.id.astype(int).map(names).fillna(vf.id.astype(str))
    keep=['id','web_name','position','gw','origin_gw','xpts_mean','p_play','fixtures']
    vf=vf[keep].copy();vf.id=vf.id.astype(int)
    forecast=pd.concat([cold[keep],vf],ignore_index=True)
    # Assert the handoff: no old provider from decision GW6 onward.
    assert not (forecast[(forecast.origin_gw>=5)&forecast.origin_gw.isin(cold.origin_gw)].shape[0])
    missing=[g for g in range(6,39) if not (forecast.origin_gw==g-1).any()]
    if missing:raise ValueError('missing vFinal origins '+str(missing))
    ts.WEIGHTS=WEIGHTS;ts.BUFFER=BUFFER;ts.OUT=out
    r=ts.run_v3(gws,names,forecast)
    logs=pd.DataFrame(r.pop('logs'));plans=pd.DataFrame(r.pop('plans'))
    logs.to_csv(out/'gameweek_log.csv',index=False);plans.to_csv(out/'plans.csv',index=False)
    summary={
      'classification':'full-season TS v3 replay: cold-start decisions GW1-5, locked MM+vFinal PM decisions GW6-38',
      'weights':list(WEIGHTS),'hit_uncertainty_buffer':BUFFER,'chips':'OFF',
      'total_points':int(r['total_points']),'transfers':int(r['transfers']),'hit_points':int(r['hit_points']),
      'points_gw1_5':int(logs[logs.gw<=5].score.sum()),
      'points_gw6_38':int(logs[logs.gw>=6].score.sum()),
      'cold_start_decision_gws':[1,2,3,4,5],
      'locked_chain_decision_gws':[6,38],
      'phase5q_after_gw5':False,
      'ts_v3_mechanics':'unchanged run_transfer_strategy_v3_replay.run_v3'
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
