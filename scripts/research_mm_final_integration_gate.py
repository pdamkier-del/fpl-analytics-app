#!/usr/bin/env python3
"""Research-only final MM integration gate: B + XI-formation + uncertainty.

Unlike a synthetic "combined model", each piece is validated against original
independent frozen source predictions. The report explicitly separates joint
coverage from unsupported all-in-one efficacy. No production mutations.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/mm-final-integration-gate-20261017'
B=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
XI=ROOT/'analysis/results/mm-formation-replay-20261017/xi_fixtures.csv'
DIST=ROOT/'analysis/results/mm-predictive-distribution-20261017/distributions.csv.gz'
BANDS=[-1e-9,5,15,30,60,np.inf]
LABELS=['0-5','5-15','15-30','30-60','over-60']
KEY=['season','fixture_uuid','player_uuid']

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    missing=[str(q) for q in [B,XI,DIST] if not q.exists()]
    if missing:raise SystemExit('Missing previous research input: '+str(missing))
    base=load_frame(B)
    evalm=((base.season=='2024-25')&base.gw.between(22,38))|((base.season=='2025-26')&base.gw.between(6,38))
    base=base[evalm & base['mode'].isin(['original','best_existing','B'])].copy()
    if any(len(g)!=39264 for _,g in base.groupby('mode')):raise ValueError('B baseline evaluation row mismatch')
    baseline=[]
    for arm,g in base.groupby('mode'):
        ae=(g.x-g.minutes).abs()
        baseline.append(dict(mode=arm,n=len(g),mae=float(ae.mean()),rmse=float(np.sqrt(np.mean((g.x-g.minutes)**2))),start_brier=float(np.mean((g.p-g.y)**2)),error_over30=int((ae>30).sum()),error_over60=int((ae>60).sum())))
    pd.DataFrame(baseline).to_csv(OUT/'full_history_MM_comparison.csv',index=False)
    # B + minute distribution: *exactly* same p and x for all rows.
    d=pd.read_csv(DIST,compression='gzip')
    if set(d['mode'])!={'homogeneous','role_dependent'}:raise ValueError('Invalid distribution models')
    distribution=[]
    b=base[base['mode']=='B'][KEY+['p','x','minutes','y']].copy()
    for mode,g in d.groupby('mode'):
        if len(g)!=39264 or g.duplicated(KEY).any():raise ValueError('Unmatched distribution cohort '+mode)
        t=b.merge(g,on=KEY,suffixes=('_source','_dist'),validate='one_to_one')
        if len(t)!=39264:raise ValueError('Incomplete distribution join')
        for col in ['p','x','minutes','y']:
            source=col+'_source';derived=col+'_dist'
            if source in t and derived in t:
                if not np.allclose(t[source],t[derived],atol=1e-8):raise ValueError('Changed fixed B '+col)
        distribution.append(dict(mode=mode,n=len(g),crps=float(g.crps.mean()),logloss=float(g.logloss.mean()),coverage80=float(g.inside80.mean()),interval_width=float((g.upper80-g.lower80).mean()),predicted_zeros=float(g.p0.mean()),observed_zeros=float((g.minutes==0).mean())))
    pd.DataFrame(distribution).to_csv(OUT/'distribution_comparison.csv',index=False)
    # XI roles are evaluated only on 2025/26 team fixtures with cutoff-safe role history.
    xi=pd.read_csv(XI)
    modes=['original','best_existing','B','B_role_formation']
    if set(xi['mode'])!=set(modes):raise ValueError('Missing XI comparator')
    ids=xi[xi['mode']=='B_role_formation'][['season','fixture_uuid','team_id']].drop_duplicates()
    xi=xi.merge(ids,on=['season','fixture_uuid','team_id'],validate='many_to_one')
    if len(ids)!=660 or len(xi)!=4*660:raise ValueError('Invalid formation coverage')
    results=[]
    for arm,g in xi.groupby('mode'):
        results.append(dict(mode=arm,n=len(g),avg_correct=float(g.correct.mean()),exact11=int((g.correct==11).sum()),exact11_pct=100*float((g.correct==11).mean()),at_least10_pct=100*float((g.correct>=10).mean())))
    pd.DataFrame(results).to_csv(OUT/'xi_matched_comparison.csv',index=False)
    # Paired XI effect table to avoid treating an unpaired percentage as evidence.
    wide=xi.pivot(index=['season','fixture_uuid','team_id'],columns='mode',values='correct')
    paired=pd.DataFrame(dict(B=wide['B'],B_role_formation=wide['B_role_formation']))
    paired['delta']=paired.B_role_formation-paired.B
    paired['B_11']=paired.B==11
    paired['role_11']=paired.B_role_formation==11
    paired.reset_index().to_csv(OUT/'paired_xi_fixtures.csv',index=False)
    # Stratify big minute errors using ONLY pre-target historical role.
    b=base[base['mode']=='B'].copy();b['ae']=(b.x-b.minutes).abs()
    b['band']=pd.cut(b.ae,BANDS,labels=LABELS)
    rows=[]
    for role,g in b.groupby('prior_type'):
        for band in LABELS:
            sub=g[g.band==band]
            rows.append(dict(role=role,band=band,n=len(sub),fraction=100*len(sub)/len(g),error_share=100*sub.ae.sum()/g.ae.sum(),denominator=len(g)))
    pd.DataFrame(rows).to_csv(OUT/'B_role_error_bands.csv',index=False)
    b.groupby('prior_type').agg(n=('ae','size'),mae=('ae','mean'),median=('ae','median'),p95=('ae',lambda a:a.quantile(.95)),over60=('ae',lambda a:int((a>60).sum()))).reset_index().to_csv(OUT/'B_role_summary.csv',index=False)
    # Evidence-constrained decision: do not promote under worse start Brier / RMSE / >60 tails.
    prev=pd.read_csv(ROOT/'analysis/results/mm-formation-replay-20261017/mm_metrics.csv')
    bb=prev.set_index('mode').loc['B']
    combined=prev.set_index('mode').loc['B_role_nudge_diagnostic']
    risk_flags={
      'minute_mae_improved': bool(combined.mae<bb.mae),
      'rmse_not_worse': bool(combined.rmse<=bb.rmse),
      'start_brier_not_worse': bool(combined.start_brier<=bb.start_brier),
      'error_over60_not_worse': bool((pd.read_csv(ROOT/'analysis/results/mm-formation-replay-20261017/minute_error_bands.csv').query("mode=='B_role_nudge_diagnostic' and band=='over-60'")['count'].iloc[0]) <= (pd.read_csv(ROOT/'analysis/results/mm-formation-replay-20261017/minute_error_bands.csv').query("mode=='B' and band=='over-60'")['count'].iloc[0]))
    }
    j=dict(frozen_B_rows=39264,formations_team_fixtures=660,forecast_source='Original frozen PR9 Model B',reuse=['PR11 pre-cutoff historical formation selector','PR13 probabilistic minute distribution','PR12 role-dependent error stratification'],evidence_scope='Separate components validated against same frozen B, NOT an end-to-end single combined candidate',formation_nudge_flags=risk_flags,ready_for_production=False,why_not=['Formation probability nudge worsens Brier, RMSE and over60 tails','Uncertainty 80% intervals empirical coverage ~90%, not calibrated','Distribution hyperparameter role conditions selected same spread for all','No independent fresh season and inherited data known-at proxies'],production_changed=False,pm_ts_chips_untouched=True)
    (OUT/'integration_decision.json').write_text(json.dumps(j,indent=2)+'\n')
    print((OUT/'integration_decision.json').read_text())
    print(pd.read_csv(OUT/'full_history_MM_comparison.csv').to_string(index=False))
    print(pd.read_csv(OUT/'xi_matched_comparison.csv').to_string(index=False))
    print(pd.read_csv(OUT/'distribution_comparison.csv').to_string(index=False))
if __name__=='__main__':main()
