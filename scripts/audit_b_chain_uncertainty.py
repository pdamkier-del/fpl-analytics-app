"""Read-only probability checks and fixture-paired intervals; no tuning."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr
from b_chain_contract import field_marginals
from individual_mm_evidence import load_frame
from fpl_v1_1_model.joint_simulator import PlayerSimInput


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('analysis/results/unified-b-chain-20261021'));args=ap.parse_args();out=args.out
    frame=pd.read_csv(out/'predictions.csv.gz');report={}
    for season,g in frame.groupby('season'):
        base=g[g.arm.eq('control')][['fixture_uuid','player_uuid','xp','total_points']].copy()
        base['base_error']=abs(base.xp-base.total_points)
        for arm in ('mean_preserving','penalty_roles'):
            part=g[g.arm.eq(arm)]
            if part.empty:continue
            p=part.merge(base[['fixture_uuid','player_uuid','base_error']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
            p['delta']=abs(p.xp-p.total_points)-p.base_error
            blocks=p.groupby('fixture_uuid').delta.agg(['sum','size']).to_numpy();rng=np.random.default_rng(20261021)
            samples=blocks[rng.integers(len(blocks),size=(2000,len(blocks)))].sum(1)
            report[season+' '+arm]=dict(delta_xp_mae=float(p.delta.mean()),fixture_paired_95_ci=np.quantile(samples[:,0]/samples[:,1],[.025,.975]).tolist())
    report['limitations']='Paired fixture bootstrap on reused research periods; does not cover all Monte Carlo or source-clock uncertainty.'
    (out/'paired_uncertainty.json').write_text(json.dumps(report,indent=2)+'\n')
    frozen=load_frame('analysis/results/individual-mm-refinement-20261016/predictions.npz');frozen=frozen[frozen['mode'].eq('B')]
    pos=pd.read_csv('work/current-B-inputs/history.csv.gz',usecols=['season','fixture_uuid','player_uuid','pos']).drop_duplicates()
    frozen=frozen.merge(pos,on=['season','fixture_uuid','player_uuid'],validate='one_to_one');probabilities={}
    for season,g in frozen.groupby('season'):
        before=[g.p.to_numpy()*ndtr((g.s.to_numpy()-cut)/10.)for cut in (59.5,89.5)]
        corrected=[]
        for r in g.itertuples():
            mass=field_marginals(PlayerSimInput('x','H',r.pos,r.p,r.q,r.s,r.c));corrected.append((mass[60:].sum(),mass[90]))
        corrected=np.asarray(corrected);actual=g.minutes.to_numpy()
        for label,mask in [('all',np.ones(len(g),bool)),('outfield',g.pos.ne('GK').to_numpy())]:
            metrics={}
            for i,(name,truth)in enumerate([('p60',actual>=60),('p90',actual==90)]):
                old,new=before[i],corrected[:,i]
                metrics[name]=dict(old_brier=float(np.mean((old[mask]-truth[mask])**2)),new_brier=float(np.mean((new[mask]-truth[mask])**2)),
                    mean_old=float(np.mean(old[mask])),mean_new=float(np.mean(new[mask])),observed=float(np.mean(truth[mask])))
            probabilities[season+' '+label]=metrics
    (out/'duration-probabilities.json').write_text(json.dumps(probabilities,indent=2)+'\n')
    print('Saved paired intervals and analytic duration probabilities; no model parameters changed')


if __name__=='__main__':main()
