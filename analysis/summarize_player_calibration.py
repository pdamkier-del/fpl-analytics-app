"""Descriptive probability reliability and fixture-paired error intervals.

These are reused historical research periods, not independent certification.
Never condition calibration cohorts on future realised playing time.
"""
import argparse,json,sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def reliability(frame, probability, outcome):
    g=frame[[probability,outcome]].dropna().copy()
    if not g[probability].between(0,1).all() or not g[outcome].isin([0,1,False,True]).all():
        raise ValueError('Probability or binary outcome outside support')
    g['bin']=np.minimum((10*g[probability]).astype(int),9)
    return [dict(bin=int(i),rows=len(b),predicted=float(b[probability].mean()),
                 observed=float(b[outcome].mean()),brier=float(((b[probability]-b[outcome])**2).mean()),
                 low_sample=len(b)<100)
            for i,b in g.groupby('bin')]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--timeline-predictions',type=Path);args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    f=pd.read_csv(ROOT/'analysis/results/joint-role-candidate-20261022/predictions.csv.gz',low_memory=False)
    f=f[f.gw.between(22,38)&~f.pos.isin(['GK','GKP'])].copy();rows=[]
    for season,g in f.groupby('season'):
        for group,c in [('all_outfield',g)]+[(str(n),b)for n,b in g.groupby('prior_type')]:
            rows.extend(dict(season=season,group=group,event='start',arm='published_role_B',**r)
                        for r in reliability(c,'candidate_p','y'))
    pd.DataFrame(rows).to_csv(out/'start-reliability.csv',index=False)
    intervals=[]
    if args.timeline_predictions:
        predictions=pd.read_csv(args.timeline_predictions)
        with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
            actual=pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,started FROM player_fixture_observations WHERE is_final=1',db)
        predictions=predictions.merge(actual,on=['season','fixture_uuid','player_uuid'],validate='many_to_one')
        predictions['zero']=predictions.minutes.eq(0);predictions['sixty']=predictions.minutes.ge(60);predictions['ninety']=predictions.minutes.eq(90)
        minute_rows=[]
        for (season,arm),g in predictions.groupby(['season','arm']):
            cohorts=[('all',g),('rotation',g[~g.keeper&g.baseline_p_start.between(.2,.85)]),('reserve',g[~g.keeper&g.baseline_p_start.lt(.2)])]
            for group,c in cohorts:
                for probability,outcome in [('p0','zero'),('p60','sixty'),('p90','ninety')]:
                    # Only numerical roundoff within 1e-12 may be clipped.
                    if ((c[probability]<-1e-12)|(c[probability]>1+1e-12)).any():raise ValueError('Invalid timeline probability')
                    c=c.copy();c[probability]=c[probability].clip(0,1)
                    minute_rows.extend(dict(season=season,arm=arm,group=group,event=outcome,**r)for r in reliability(c,probability,outcome))
        pd.DataFrame(minute_rows).to_csv(out/'timeline-probability-reliability.csv',index=False)
        rng=np.random.default_rng(20261024)
        for season,g in predictions.groupby('season'):
            b=g[g.arm.eq('baseline')];c=g[g.arm.eq('candidate')]
            pair=c.merge(b,on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_b'))
            for name,delta in [('xp_mae',abs(pair.xp-pair.total_points)-abs(pair.xp_b-pair.total_points)),
                               ('minute_mae',abs(pair.xmins-pair.minutes)-abs(pair.xmins_b-pair.minutes))]:
                pair=pair.assign(delta=delta);blocks=pair.groupby('fixture_uuid').delta.agg(['sum','size']).to_numpy()
                sampled=blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1)
                intervals.append(dict(season=season,metric=name,delta=float(delta.mean()),fixture_bootstrap95=np.quantile(sampled[:,0]/sampled[:,1],[.025,.975]).tolist()))
    report=dict(scope='two reused GW22-38 historical research periods; original source-clock proxies',
                independent_certification=False,individual_player_calibration_certified=False,
                calibration_cohorts_use_prior_information_only=True,
                low_sample_bin_threshold_is_descriptive_not_release_gate=100,
                start_rows=len(f),timeline_reliability_included=bool(args.timeline_predictions),
                paired_fixture_uncertainty=intervals,production_changed=False)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
