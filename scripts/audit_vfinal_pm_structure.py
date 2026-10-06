#!/usr/bin/env python3
"""Audit structural lineup consistency of the current vFinal joint simulator.

No model is changed. This quantifies the consequence of sampling each player's
starter Bernoulli independently after P(start) has only been constrained to 11
in expectation.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from run_vfinal_integrated import build_final_frame

OUT=ROOT/'analysis/results/vfinal-pm-structure-audit-20261006-v1'

def poisson_binomial(p):
    d=np.array([1.0])
    for q in np.asarray(p,float):
        d=np.convolve(d,np.array([1-q,q]))
    return d

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    f=build_final_frame()
    rows=[]
    for (fx,team),g in f.groupby(['fixture_uuid','team_id'],sort=True):
        p=g.combined_p_start.to_numpy(float)
        dist=poisson_binomial(p)
        gk=g[g.pos.isin(['GK','GKP'])]
        pg=poisson_binomial(gk.combined_p_start.to_numpy(float))
        p11=float(dist[11]) if len(dist)>11 else 0.
        p1gk=float(pg[1]) if len(pg)>1 else 0.
        rows.append(dict(
            fixture_uuid=fx,team_id=int(team),gw=int(g.gw.iloc[0]),players=len(g),
            expected_starters=float(p.sum()),starter_variance=float(np.sum(p*(1-p))),
            p_exactly_11=p11,p_not_11=1-p11,
            p_under_11=float(dist[:11].sum()),p_over_11=float(dist[12:].sum()),
            expected_abs_deviation=float(sum(abs(k-11)*v for k,v in enumerate(dist))),
            goalkeepers=len(gk),expected_gk_starters=float(gk.combined_p_start.sum()),
            p_exactly_one_gk=p1gk,p_not_one_gk=1-p1gk,
            p_zero_gk=float(pg[0]) if len(pg) else 1.,
            p_two_plus_gk=float(pg[2:].sum()) if len(pg)>2 else 0.,
        ))
    x=pd.DataFrame(rows)
    x.to_csv(OUT/'fixture_team_lineup_probabilities.csv',index=False)
    by_gw=x.groupby('gw').agg(
        teams=('team_id','size'),
        mean_p_not_11=('p_not_11','mean'),
        mean_p_not_one_gk=('p_not_one_gk','mean'),
        mean_expected_abs_deviation=('expected_abs_deviation','mean'),
        mean_starter_variance=('starter_variance','mean')
    ).reset_index()
    by_gw.to_csv(OUT/'by_gw.csv',index=False)
    report={
      'classification':'structural audit of current vFinal simulation; no model change',
      'fixture_team_rows':len(x),
      'expected_starters_min':float(x.expected_starters.min()),
      'expected_starters_max':float(x.expected_starters.max()),
      'mean_probability_not_exactly_11_starters':float(x.p_not_11.mean()),
      'median_probability_not_exactly_11_starters':float(x.p_not_11.median()),
      'mean_probability_wrong_gk_count':float(x.p_not_one_gk.mean()),
      'mean_probability_zero_gk':float(x.p_zero_gk.mean()),
      'mean_probability_two_plus_gk':float(x.p_two_plus_gk.mean()),
      'mean_expected_abs_starter_count_deviation':float(x.expected_abs_deviation.mean()),
      'worst_lineup_rows':x.nlargest(12,'p_not_11')[['fixture_uuid','team_id','gw','p_not_11','starter_variance','expected_abs_deviation']].to_dict(orient='records'),
      'interpretation':'P(start) is normalized to 11 in expectation, but independent Bernoulli sampling does not enforce a legal XI in each Monte Carlo draw. This can make downstream on-pitch goal, clean-sheet, goals-conceded and BPS states internally inconsistent.',
      'recommended_gate':'Replace independent starter Bernoulli draws with a joint role/availability-constrained XI sample before calling the PM structurally production-ready.'
    }
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
