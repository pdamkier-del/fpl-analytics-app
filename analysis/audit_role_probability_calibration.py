"""Held-later-GW probability diagnostics; does not fit/recalibrate a model."""
import argparse,json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from b_chain_contract import duration_pmf


@lru_cache(maxsize=100000)
def conditional(mean,sigma):return duration_pmf(mean,sigma)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    frame=pd.read_csv(a.out/'predictions.csv.gz',low_memory=False)
    frame=frame[frame.gw.between(22,38)&~frame.pos.isin(['GK','GKP'])].copy()
    rows=[];bins=[];calibration=[]
    for r in frame.itertuples():
        st=conditional(float(r.s),10.);ca=conditional(float(r.c),7.)
        for arm,p,q in [('baseline',r.p,r.q),('candidate',r.candidate_p,r.candidate_q)]:
            mass=p*st+(1-p)*q*ca;mass=mass.copy();mass[0]+=(1-p)*(1-q)
            cdf=np.cumsum(mass);lo=int(np.searchsorted(cdf,.1));hi=int(np.searchsorted(cdf,.9))
            rows.append(dict(season=r.season,fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,
                group=r.prior_type,arm=arm,p0=mass[0],p60=sum(mass[60:]),p90=mass[90],
                y0=int(r.minutes==0),y60=int(r.minutes>=60),y90=int(r.minutes==90),
                covered80=int(lo<=r.minutes<=hi),width80=hi-lo,model_mass80=sum(mass[lo:hi+1])))
    f=pd.DataFrame(rows)
    for (season,arm,group),g in f.groupby(['season','arm','group']):
        calibration.append(dict(season=season,arm=arm,group=group,rows=len(g),coverage80=float(g.covered80.mean()),
                                mean_width80=float(g.width80.mean()),mean_model_mass80=float(g.model_mass80.mean())))
        for event in ['0','60','90']:
            p=g['p'+event].to_numpy();y=g['y'+event].to_numpy();bucket=np.minimum((p*10).astype(int),9)
            for i in range(10):
                mask=bucket==i
                if mask.any():bins.append(dict(season=season,arm=arm,group=group,event=event,bin=i,
                    rows=int(mask.sum()),predicted=float(p[mask].mean()),observed=float(y[mask].mean()),
                    brier=float(np.mean((p[mask]-y[mask])**2))))
    pd.DataFrame(calibration).to_csv(a.out/'minute-interval-coverage.csv',index=False)
    pd.DataFrame(bins).to_csv(a.out/'probability-reliability.csv',index=False)
    metrics=[];rng=np.random.default_rng(20261022)
    for season,g in f.groupby('season'):
        pair=g[g.arm.eq('candidate')].merge(g[g.arm.eq('baseline')],on=['season','fixture_uuid','player_uuid'],suffixes=('','_baseline'),validate='one_to_one')
        for event in ['0','60','90']:
            y=pair['y'+event];p=pair['p'+event];base=pair['p'+event+'_baseline'];delta=(p-y)**2-(base-y)**2
            blocks=pd.DataFrame(dict(fixture=pair.fixture_uuid,delta=delta)).groupby('fixture').delta.agg(['sum','size']).to_numpy()
            draw=blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1)
            metrics.append(dict(season=season,event=event,rows=len(pair),baseline_brier=float(((base-y)**2).mean()),
                candidate_brier=float(((p-y)**2).mean()),delta=float(delta.mean()),fixture_bootstrap95=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()))
    report=dict(scope='outfield GW22-38; analytic probabilities of the exact B mean-preserving minute kernel',
        metrics=metrics,independent_certification=False,
        limitations=['Reused historical research periods and source-clock proxies','Discrete interval model mass often exceeds 80%; empirical coverage is reported separately',
                     'This diagnostic does not validate parameter uncertainty or confidence intervals for xP','GK calibration is separate; no sparse keeper subgroup is called certified'])
    (a.out/'probability-calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
