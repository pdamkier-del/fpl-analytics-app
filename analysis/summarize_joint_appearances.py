"""Descriptive reliability and paired fixture uncertainty; no model selection."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    d=pd.read_csv(a.out/'predictions.csv.gz')
    keys=['season','fixture_uuid','player_uuid']
    b=d[d.arm.eq('baseline')];c=d[d.arm.eq('candidate')]
    pair=b.merge(c,on=keys,validate='one_to_one',suffixes=('_b','_c'))
    if len(pair)!=len(b) or len(pair)!=len(c):raise ValueError('Unpaired predictions')
    reliability=[];uncertainty=[]
    for season,raw in b[~b.keeper].groupby('season'):
        bins=np.minimum((raw.p*10).astype(int),9)
        for bucket,g in raw.groupby(bins):
            reliability.append(dict(season=season,bin=int(bucket),rows=len(g),
                predicted=float(g.p.mean()),observed=float(g.started.mean()),
                minute_mae=float(abs(g.xmins-g.minutes).mean()),scope='Final B outfield start marginals; reused research'))
    for season,g in pair.groupby('season'):
        for name,v in {'all':g,'played':g[g.minutes_b.gt(0)],
                       'rotation':g[~g.keeper_b&g.p_b.between(.2,.85)]}.items():
            v=v.copy()
            for metric,delta in {
                'minute_mae':abs(v.xmins_c-v.minutes_b)-abs(v.xmins_b-v.minutes_b),
                'xp_mae':abs(v.xp_c-v.total_points_b)-abs(v.xp_b-v.total_points_b),
                'p0_brier':(v.p0_c-v.minutes_b.eq(0))**2-(v.p0_b-v.minutes_b.eq(0))**2,
            }.items():
                v['delta']=delta
                clustered=v.groupby('fixture_uuid').delta.agg(['sum','count'])
                rng=np.random.default_rng(20261025)
                indices=rng.integers(len(clustered),size=(2000,len(clustered)))
                samples=clustered['sum'].to_numpy()[indices].sum(axis=1)/clustered['count'].to_numpy()[indices].sum(axis=1)
                uncertainty.append(dict(season=season,cohort=name,metric=metric,
                    delta=float(delta.mean()),fixture_bootstrap95=np.quantile(samples,[.025,.975]).tolist(),
                    fixtures=len(clustered),rows=len(v)))
    pd.DataFrame(reliability).to_csv(a.out/'start-reliability.csv',index=False)
    (a.out/'uncertainty.json').write_text(json.dumps(dict(
        scope='Paired fixture bootstrap on reused periods; includes realized 400-draw differences, not a separate Monte Carlo convergence test',
        bootstrap_replicates=2000,seed=20261025,comparisons=uncertainty),indent=2)+'\n')


if __name__=='__main__':main()
