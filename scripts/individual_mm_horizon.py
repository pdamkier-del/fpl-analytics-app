#!/usr/bin/env python3
"""Conditional frozen-origin MM horizon validation; never produces TS input files."""
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from individual_mm_validation import save,load_obs
from audit_capture_io import write_frame
from audit_mm_components import score,prob_score

def horizon_rows(pred,obs,mode):
    out=[];gaps=[]
    base=pred[pred['mode'].eq('original')];candidate=pred[pred['mode'].eq(mode)]
    for origin,f in base.groupby('gw'):
        cut=pd.to_datetime(f.cutoff,utc=True).min()
        # Each origin's roster/club and predictions are frozen. No target roster feature.
        cols=['player_uuid','team_id'];b=f.groupby(cols,as_index=False).agg(p=('p','mean'),x=('x','mean'))
        c=candidate[candidate.gw.eq(origin)].groupby(cols,as_index=False).agg(role_p=('p','mean'),role_x=('x','mean'))
        state=b.merge(c,on=cols,validate='one_to_one')
        control=pred[pred['mode'].eq('same_logistic_without_role')&pred.gw.eq(origin)].groupby(cols,as_index=False).agg(control_p=('p','mean'),control_x=('x','mean'))
        state=state.merge(control,on=cols,validate='one_to_one')
        for horizon in range(6):
            target=int(origin+horizon)
            if target>38:continue
            actual=obs[obs.gw.eq(target)&pd.to_datetime(obs.kickoff_at,utc=True).gt(cut)]
            teams=set(state.team_id);actual=actual[actual.team_id.isin(teams)]
            # This uses final realized PL fixtures to define scored opportunities only.
            # It is a retrospective horizon diagnostic, not schedule-snapshot certification.
            pairs=actual.merge(state,on=cols,validate='many_to_one',how='inner')
            expected=sum(len(state[state.team_id.eq(t)])*actual[actual.team_id.eq(t)].fixture_uuid.nunique() for t in state.team_id.unique())
            gaps.append(dict(origin=int(origin),target=target,unscored_target_rows=len(actual)-len(pairs),unscored_origin_player_fixture_targets=int(expected-len(pairs)),origin_players=len(state),matched_rows=len(pairs)))
            if not len(pairs):continue
            pairs=pairs.assign(origin=int(origin),target=target,horizon=horizon,origin_cutoff=str(cut));out.append(pairs)
    return pd.concat(out,ignore_index=True),gaps

def report(frame,weights):
    result={}
    for h,g in frame.groupby('horizon'):
        a=weights[str(int(h))];p=(1-a)*g.p+a*g.role_p;x=(1-a)*g.x+a*g.role_x
        d=abs(x-g.minutes)-abs(g.x-g.minutes)
        block=pd.DataFrame(dict(origin=g.origin,d=d)).groupby('origin').d.agg(['sum','size']).to_numpy();rng=np.random.default_rng(20261015);b=block[rng.integers(len(block),size=(2000,len(block)))].sum(1)
        role_delta=abs(g.role_x-g.minutes)-abs(g.control_x-g.minutes)
        rb=pd.DataFrame(dict(origin=g.origin,d=role_delta)).groupby('origin').d.agg(['sum','size']).to_numpy();rd=rb[rng.integers(len(rb),size=(2000,len(rb)))].sum(1)
        result[str(int(h))]=dict(logistic_control=dict(minutes=score(g.minutes,g.control_x),start=prob_score(g.started,g.control_p)),role_vs_logistic_mae_delta=float(role_delta.mean()),role_vs_logistic_origin_interval95=np.quantile(rd[:,0]/rd[:,1],[.025,.975]).tolist(),rows=len(g),origins=g.origin.nunique(),mixture_weight=a,baseline=dict(minutes=score(g.minutes,g.x),start=prob_score(g.started,g.p)),role_frozen=dict(minutes=score(g.minutes,g.role_x),start=prob_score(g.started,g.role_p)),calibrated_mixture=dict(minutes=score(g.minutes,x),start=prob_score(g.started,p)),paired_mae_delta=float(d.mean()),origin_block_interval95=np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist())
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='analysis/results/individual-mm-20261015');a=ap.parse_args();root=Path(a.root);sel=json.loads((root/'selection.json').read_text());mode=sel['selected_arm']
    p24=pd.read_csv(root/'2024-25_candidates.csv.gz');o24=load_obs('work/core.sqlite3','2024-25',4);r24,gap24=horizon_rows(p24,o24,mode)
    dev=r24[r24.origin.between(11,16)&r24.target.le(21)];grid={};weights={}
    for h,g in dev.groupby('horizon'):
        grid[str(h)]={str(w):float(abs((1-w)*g.x+w*g.role_x-g.minutes).mean()) for w in [0.,.25,.5,.75,1.]};weights[str(h)]=float(min(grid[str(h)],key=grid[str(h)].get))
    if len(weights)!=6:raise ValueError('Incomplete development horizons')
    fit_max=pd.to_datetime(dev.known,utc=True).max();save(root/'horizon_selection.json',dict(development='2024-25 origins GW11-16, targets <=21',selected_mm=mode,weights=weights,grid=grid,maximum_development_label_known=str(fit_max),independent_holdout=False))
    test24=r24[r24.origin.ge(22)&pd.to_datetime(r24.origin_cutoff,utc=True).gt(fit_max)]
    p25=pd.read_csv(root/'2025-26_candidates.csv.gz');o25=load_obs('work/core.sqlite3','2025-26',3);r25,gap25=horizon_rows(p25,o25,mode)
    write_frame(root/'horizon_predictions.csv.gz',pd.concat([r24.assign(season='2024-25'),r25.assign(season='2025-26')],ignore_index=True))
    save(root/'horizon_report.json',dict(classification='CONDITIONAL_FROZEN_ORIGIN_MM_HORIZON_DIAGNOSTIC_NOT_TS',results={'2024-25_GW22-38':report(test24,weights),'2025-26_GW6-38':report(r25,weights)},coverage={'2024-25':gap24,'2025-26':gap25},ts_allowed=False,locked_model_active=False,limitations=['Future fixtures here define outcome scoring opportunities from final schedule; fixture publication and cancellation clocks not certified','Both baseline and roles freeze origin club/roster; future transfer or registration changes unscored, not zero-imputed','No rest correction: coefficients for unvalidated days-rest adjustment remain zero','A calibrated shrinkage of origin MM is not a full injury/rotation/workload trajectory','Overlapping origin horizons induce dependence; origin bootstrap still omits cross-origin target dependence','Full PM six-GW player/price/news/schedule snapshots not complete; no TS replay']))
    print(json.dumps(dict(weights=weights,results={s:{h:r['paired_mae_delta'] for h,r in report(f,weights).items()}for s,f in [('2024-25',test24),('2025-26',r25)]}),indent=2))
if __name__=='__main__':main()
