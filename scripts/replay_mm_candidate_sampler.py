#!/usr/bin/env python3
"""Research-only paired legacy/B-duration-PMF replay; never alters production.

Uses identical B inputs, vFinal rates and PM scoring. It compares only the
duration sampler. Prior historical period is reused, not an independent test.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame
from run_vfinal_integrated import build_final_frame, FROZEN, score
from fpl_v1_1_model.paired_joint import read_frozen_table
from mm_locked_bridge import simulate_candidate_pair, code_identity

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--gws',nargs='+',type=int,default=list(range(22,39)))
    p.add_argument('--output',type=Path,default=ROOT/'analysis/results/mm-pmf-sampler-research-20261017')
    a=p.parse_args()
    out=a.output.resolve()
    if out.is_relative_to(ROOT/'app'):
        raise ValueError('Research results must not overwrite public app assets')
    original=code_identity(ROOT)
    pm=build_final_frame()
    pm=pm[pm.gw.isin(a.gws)].copy()
    pm['season']='2025-26'
    source=ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz'
    mm=load_frame(source)
    mm=mm[mm.season.eq('2025-26') & mm['mode'].eq('B') & mm.gw.isin(a.gws)]
    common=mm.merge(pm[['fixture_uuid','player_uuid','pos']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
    if not len(common) or pm.fixture_uuid.nunique()==0:
        raise ValueError('No matched frozen MM/PM replay fixtures')
    result=simulate_candidate_pair(pm,common,season='2025-26')
    expected=set(map(tuple,common[['fixture_uuid','player_uuid']].to_numpy()))
    for arm,g in result.groupby('arm'):
        if set(map(tuple,g[['fixture_uuid','player_uuid']].to_numpy()))!=expected:
            raise ValueError('Different player cohort across sampler arms: '+arm)
    if set(result.arm)!={'locked_sampler','candidate_PMF'}:
        raise ValueError('Missing sampler arm')
    if original!=code_identity(ROOT):
        raise ValueError('Locked production model changed')
    truth=read_frozen_table(FROZEN,'targets')
    actual=result.merge(truth[['fixture_uuid','player_uuid','total_points']],on=['fixture_uuid','player_uuid'],validate='many_to_one')
    if len(actual)!=len(result) or actual.total_points.isna().any():
        raise ValueError('Historical labels missing')
    stats={}
    for arm,g in actual.groupby('arm'):
        stats[arm]=dict(point_metrics=score(g.total_points,g.xpts),
                        mean_simulated_minutes=float(g.sampled_minutes.mean()),
                        mean_expected_B_minutes=float(g.target_xmins.mean()),
                        mean_minute_offset=float((g.sampled_minutes-g.target_xmins).mean()))
    out.mkdir(parents=True,exist_ok=True)
    result.to_csv(out/'paired_sampler.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    summary=dict(scope='reused_historical_research',season='2025-26',gws=sorted(a.gws),
        matched_rows=len(common),fixtures=int(pm.fixture_uuid.nunique()),draws=400,
        production_changed=False,PM_math_changed=False,TS_math_changed=False,
        certification='NOT CERTIFIED: prior reused cohort, 400-draw Monte Carlo, uncalibrated PMF',
        arms=stats)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
