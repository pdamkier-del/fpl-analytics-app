#!/usr/bin/env python3
"""Score a paired historical PM shadow only after exact archived reproduction."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


def scores(g):
    a = g.xpts_mean_original-g.total_points
    b = g.xpts_mean_candidate-g.total_points
    return dict(rows=len(g), original_mae=float(abs(a).mean()), candidate_mae=float(abs(b).mean()), original_rmse=float(np.sqrt((a*a).mean())), candidate_rmse=float(np.sqrt((b*b).mean())), paired_mae_delta=float((abs(b)-abs(a)).mean()))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['archive','original','candidate','db','out']:
        ap.add_argument('--'+name, required=True)
    args = ap.parse_args()
    key = ['decision_gw','gw','id','fixture']
    archived = pd.read_csv(Path(args.archive)/'fixture_predictions.csv.gz')
    original = pd.read_csv(Path(args.original)/'fixture_predictions.csv.gz')
    exact = archived.merge(original, on=key, suffixes=('_archive','_replay'), validate='one_to_one', how='outer', indicator=True)
    if not exact._merge.eq('both').all() or not all(np.array_equal(exact[c+'_archive'],exact[c+'_replay']) for c in ['xpts_fixture','p_play_fixture','player_uuid','team','position']):
        raise ValueError('Original historical PM replay differs from archived benchmark')
    original = pd.read_csv(Path(args.original)/'rolling_vfinal_forecast.csv.gz')
    candidate = pd.read_csv(Path(args.candidate)/'rolling_vfinal_forecast.csv.gz')
    key = ['decision_gw','gw','id','player_uuid','team','position']
    pair = original.merge(candidate,on=key,suffixes=('_original','_candidate'),validate='one_to_one',how='outer',indicator=True)
    if not pair._merge.eq('both').all():
        raise ValueError('Candidate cohort differs')
    if not np.array_equal(pair.p_play_original,pair.p_play_candidate):
        raise ValueError('Duration-only experiment changed appearance probabilities')
    pair = pair.drop(columns='_merge')
    if not pair.gw.eq(pair.decision_gw).all():
        raise ValueError('This scorer requires current-GW-only archived forecasts')
    with sqlite3.connect(f'file:{Path(args.db).resolve()}?mode=ro',uri=True) as c:
        truth = pd.read_sql_query("SELECT player_uuid,gw,sum(total_points) as total_points,sum(minutes) as minutes FROM player_fixture_observations WHERE season='2025-26' AND is_final=1 GROUP BY player_uuid,gw",c)
    pair = pair.merge(truth,on=['player_uuid','gw'],how='left',validate='one_to_one',indicator=True)
    missing = int(pair.total_points.isna().sum())
    available = pair[pair.total_points.notna()].copy()
    groups = dict(all=available, played=available[available.minutes.gt(0)], GW6_21=available[available.gw.le(21)], GW22_38=available[available.gw.ge(22)])
    rng = np.random.default_rng(20261013)
    results = {}
    for name,g in groups.items():
        delta = abs(g.xpts_mean_candidate-g.total_points)-abs(g.xpts_mean_original-g.total_points)
        blocks = pd.DataFrame(dict(gw=g.gw,delta=delta)).groupby('gw').delta.agg(['sum','size']).to_numpy()
        draws = blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1)
        results[name] = {**scores(g),'gameweek_block_bootstrap_95_ci':np.quantile(draws[:,0]/draws[:,1],[.025,.975]).tolist()}
    results['by_position'] = {str(pos):scores(g) for pos,g in available.groupby('position')}
    report = dict(classification='REUSED_HISTORICAL_DURATION_PM_SHADOW_NOT_TS_ACCEPTANCE',exact_archived_fixture_rows=len(exact),max_archived_xp_difference=0.0,forecast_rows=len(pair),missing_actuals_excluded_not_imputed=missing,results=results,promotion_allowed=False,limitations=['Only current-GW cells exist in the archived benchmark; no six-GW TS comparison','Existing historical period reused during model development, not pristine holdout','400 Monte Carlo draws per fixture, paired identical seeds','Historical publication time remains kickoff+3h proxy'],source_sha256={name:hashlib.sha256((Path(getattr(args,name))/'rolling_vfinal_forecast.csv.gz').read_bytes()).hexdigest() for name in ['archive','original','candidate']})
    Path(args.out).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
