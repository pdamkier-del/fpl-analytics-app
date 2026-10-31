"""Difficulty score/update verification and temporally selected alternatives."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit,logit
from audit_capture_io import write_frame
from research_pm_conversion import deadlines
from research_shot_finishing import loss,metrics
from fpl_v1_1_model.experimental_shot_difficulty import fit_difficulty
from fpl_v1_1_model.experimental_shot_finishing import fit_shots


def control():
    rows=[]
    for x in (.05,.8):
        for goal in (0,1):
            # Identical 50-shot history, .1 xG each and five goals; prior ridge 5.
            def equation(u):
                return 50*expit(logit(.1)+u)-5+expit(logit(x)+u)-goal+5*u
            rows.append(dict(xg=x,goal=goal,initial_player_score=goal-x,
                             fitted_offset_update=float(brentq(equation,-10,10))))
    return rows


def comparisons(frame):
    results={m:metrics(g)for m,g in frame.groupby('mode')};paired={}
    rng=np.random.default_rng(20261020)
    for base in ('native_xg','existing_player','calibration','weighted_matched_player','quality_response_matched_player'):
        reference=frame[frame['mode'].eq(base)][['shot_id','probability']]
        for mode,g in frame.groupby('mode'):
            p=g.merge(reference,on='shot_id',validate='one_to_one',suffixes=('','_base'))
            d=loss(p.goal,p.probability)-loss(p.goal,p.probability_base)
            blocks=pd.DataFrame(dict(fixture=p.fixture_uuid,delta=d)).groupby('fixture').delta.agg(['sum','size']).to_numpy()
            sample=blocks[rng.integers(len(blocks),size=(3000,len(blocks)))].sum(1)
            paired[f'{mode}_vs_{base}']=dict(log_loss_delta=float(d.mean()),
                                          ci95=np.quantile(sample[:,0]/sample[:,1],[.025,.975]).tolist())
    return dict(metrics=results,paired=paired)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--source',default='analysis/results/shot-finishing-20261020')
    parser.add_argument('--out',default='analysis/results/shot-difficulty-20261020')
    parser.add_argument('--mm-root',required=True)
    args=parser.parse_args();source=Path(args.source);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    frame=pd.read_csv(source/'native_nonpenalty_shots.csv.gz',dtype={'shot_id':str})
    frame['known']=pd.to_datetime(frame.known,utc=True);frame=frame[~frame.quarantined_credit_dispute]
    cuts=deadlines(Path(args.mm_root))['2024-25']
    configs=([dict(family='weighted',ridge=r,power=p)for r in (5.,20.,80.)for p in (.5,1.)]
             +[dict(family='quality_response',ridge=r,shape_ridge=s)for r in (5.,20.,80.)for s in (5.,20.,80.,320.)])
    dev=[]
    for gw in range(16,22):
        cut=cuts[gw];train=frame[frame.known.lt(cut)];target=frame[frame.gw.eq(gw)]
        for index,cfg in enumerate(configs):
            fit=fit_difficulty(train,cut,**{k:v for k,v in cfg.items()if k!='family'})
            score=loss(target.goal.to_numpy(),fit.predict(target.xg,target.player_uuid))
            dev.append(dict(config=index,shots=len(target),loss_sum=float(score.sum())))
        print('development',gw,flush=True)
    scores=pd.DataFrame(dev).groupby('config')[['shots','loss_sum']].sum()
    means=scores.loss_sum/scores.shots
    chosen={family:configs[min((i for i,c in enumerate(configs)if c['family']==family),key=lambda i:means.loc[i])]
            for family in ('weighted','quality_response')}
    selection=dict(selected=chosen,development='GW16-21 only; no recency; no named-player tuning',
                   grid=[dict(**cfg,log_loss=float(means.loc[i]))for i,cfg in enumerate(configs)])
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    columns=['shot_id','fixture_uuid','player_uuid','xg','goal','mode','probability']
    prior=pd.read_csv(source/'test_predictions.csv.gz',dtype={'shot_id':str})
    prior=prior[prior['mode'].isin(['native_xg','calibration','shot_player'])].copy()
    prior['mode']=prior['mode'].replace({'shot_player':'existing_player'})
    historical=[prior[columns]]
    for gw in range(22,39):
        cut=cuts[gw];train=frame[frame.known.lt(cut)];target=frame[frame.gw.eq(gw)]
        for family,cfg in chosen.items():
            fit=fit_difficulty(train,cut,**{k:v for k,v in cfg.items()if k!='family'})
            b=target.copy();b['mode']=family;b['probability']=fit.predict(target.xg,target.player_uuid)
            historical.append(b[columns])
            matched=fit_shots(train,cut,ridge=cfg['ridge'])
            b=target.copy();b['mode']=family+'_matched_player';b['probability']=matched.predict(target.xg,target.player_uuid)
            historical.append(b[columns])
        print('evaluation',gw,flush=True)
    historical=pd.concat(historical,ignore_index=True)
    write_frame(out/'historical_predictions.csv.gz',historical)
    later=pd.read_csv(source/'later_predictions.csv.gz',dtype={'shot_id':str,'fixture_uuid':str})
    later=later[later['mode'].isin(['native_xg','calibration','shot_player'])].copy()
    later['mode']=later['mode'].replace({'shot_player':'existing_player'})
    later_blocks=[later[columns]];target=later[later['mode'].eq('native_xg')]
    for family,cfg in chosen.items():
        fit=fit_difficulty(frame,pd.Timestamp('2026-08-01',tz='UTC'),**{k:v for k,v in cfg.items()if k!='family'})
        b=target.copy();b['mode']=family;b['probability']=fit.predict(target.xg,target.player_uuid)
        later_blocks.append(b[columns])
        matched=fit_shots(frame,pd.Timestamp('2026-08-01',tz='UTC'),ridge=cfg['ridge'])
        b=target.copy();b['mode']=family+'_matched_player';b['probability']=matched.predict(target.xg,target.player_uuid)
        later_blocks.append(b[columns])
    later=pd.concat(later_blocks,ignore_index=True)
    write_frame(out/'later_predictions.csv.gz',later)
    root=Path(__file__).resolve().parents[1]
    report=dict(classification='EXPLORATORY_DIFFICULTY_WEIGHTING_CONDITIONAL_SHOT_TEST',
                control=control(),selected=chosen,historical=comparisons(historical),later=comparisons(later),
                hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (
                    out/'selection.json',out/'historical_predictions.csv.gz',out/'later_predictions.csv.gz')},
                code_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest()for n in (
                    'scripts/research_shot_difficulty.py','src/fpl_v1_1_model/experimental_shot_difficulty.py')},
                limitations=['Reused research data; exploratory follow-up after earlier outcomes inspected',
                             'Only development period selects difficulty parameters',
                             'One full shot season plus partial later sample; missing intervening season',
                             'Conditions on realized pre-shot xG, not pre-match xP',
                             'Player-specific quality curve can absorb context/source biases'],
                production_changed=False,promotion_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(selected=chosen,control=report['control'],
                         historical=report['historical']['metrics'],later=report['later']['metrics']),indent=2))


if __name__=='__main__':main()
