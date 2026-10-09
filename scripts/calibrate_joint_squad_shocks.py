#!/usr/bin/env python3
"""Calibrate out-of-sample squad disruptions from historical FPL minutes.

NOT a clinical/injury dataset. 'Unexpected zero' means 0 league minutes
after consecutive >=60-minute appearances when the GW had 10 PL fixtures.
Transfer/team-specific correlations are not certified. Use this only as
an availability proxy, not as injury or red-card labels.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

def calibration_one(root:Path,season:str,draws:int,rng):
    folder=root/'data'/season
    m=pd.read_csv(folder/'gws'/'merged_gw.csv',
                  usecols=lambda c:c in ('element','GW','minutes','team'))
    for c in ['element','GW','minutes']:
        m[c]=pd.to_numeric(m[c],errors='coerce')
    m=m.dropna(subset=['element','GW']).copy()
    m[['element','GW']]=m[['element','GW']].astype(int)
    # Aggregate multiple matches of a DGW per player before participation.
    m=m.groupby(['element','GW'],as_index=False).agg(
        minutes=('minutes','sum'))
    wide=m.pivot(index='element',columns='GW',values='minutes')
    schedule=pd.read_csv(folder/'fixtures.csv',usecols=['event'])
    counts=pd.to_numeric(schedule.event,errors='coerce').dropna().astype(int).value_counts().to_dict()
    out=[];next_samples=[]
    for gw in range(3,38):
        if int(counts.get(gw,0))!=10:continue
        if int(counts.get(gw-1,0))!=10 or int(counts.get(gw-2,0))!=10:continue
        if not set([gw,gw-1,gw-2]).issubset(wide.columns):continue
        eligible=(wide[gw-1].fillna(0).ge(60)&wide[gw-2].fillna(0).ge(60))
        ids=wide.index[eligible]
        if len(ids)<22:continue
        cur=wide.loc[ids,gw].fillna(0).to_numpy(float)
        misses=(cur<=0).astype(int)
        if int(counts.get(gw+1,0))==10 and gw+1 in wide.columns:
            nxt=wide.loc[ids,gw+1].fillna(0).to_numpy(float)
            next_samples.extend([(int(z),int(n<=0)) for z,n in zip(misses,nxt)])
        # Historical real-GW draws preserve per-GW systemic correlation but
        # sample hypothetical 11 starters; not actual historical FPL squads.
        for _ in range(draws):
            sample=rng.choice(len(ids),size=11,replace=False)
            n=int(misses[sample].sum())
            out.append(dict(season=season,gw=gw,missing=n))
    return pd.DataFrame(out),next_samples

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vaastav',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--draws-per-gw',type=int,default=300)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(20261009);all_rows=[];persistence=[]
    for season in ['2022-23','2023-24','2024-25']:
        rows, nxt=calibration_one(Path(a.vaastav),season,a.draws_per_gw,rng)
        all_rows.append(rows);persistence.extend(nxt)
    x=pd.concat(all_rows,ignore_index=True)
    if len(x)<1000:raise RuntimeError('insufficient historical calibration')
    p_zero=float(x.missing.eq(0).mean())
    p_mild=float(x.missing.between(1,2).mean())
    p_severe=float(x.missing.ge(3).mean())
    p0=pd.DataFrame(persistence,columns=['missed_current','missed_next'])
    still=float(p0[p0.missed_current.eq(1)].missed_next.mean())
    result=dict(classification='PROXY, not labelled injury',
                seasons=['2022-23','2023-24','2024-25'],
                hypothetical_11_player_squad_draws=int(len(x)),
                normal_10_match_gws=int(x[['season','gw']].drop_duplicates().shape[0]),
                p_no_unexpected_zero=p_zero,
                p_one_or_two_unexpected_zero=p_mild,
                p_three_plus_unexpected_zero=p_severe,
                p_zero_minutes_persists_one_gw=still,
                methodological_caveat='Players with >=60 minutes in prior two GWs; zero-minute outcome may reflect rotation, suspension, injury, other absences. Draws use hypothetical 11-player lineups and exclude structural BGW/DGW.')
    x.to_csv(out/'historical_hypothetical_squad_shocks.csv',index=False)
    (out/'availability_calibration.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
