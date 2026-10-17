#!/usr/bin/env python3
"""Report point/minute errors without hiding active-player error in bench zeroes."""
from pathlib import Path
import json,sqlite3,hashlib
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/full-model-audit-20261012'
def metric(g):
    return dict(rows=len(g),original_point_mae=float(abs(g.original-g.total_points).mean()),candidate_point_mae=float(abs(g.candidate-g.total_points).mean()),original_minute_mae=float(abs(g.minutes_original-g.minutes).mean()),candidate_minute_mae=float(abs(g.minutes_candidate-g.minutes).mean()))
def main():
    core=ROOT/'work/core.sqlite3';manifest=json.loads((ROOT/'model/checkpoints/phase5e_core/PARTS_MANIFEST.json').read_text())
    if hashlib.sha256(core.read_bytes()).hexdigest()!=manifest['sqlite_sha256']:raise ValueError('Frozen Core checksum mismatch')
    p=pd.read_csv(OUT/'historical_sampler_predictions.csv.gz')
    with sqlite3.connect(core.resolve().as_uri()+'?mode=ro',uri=True) as c:
        truth=pd.read_sql_query("select fixture_uuid,player_uuid,minutes,started,total_points as core_points from player_fixture_observations where season='2025-26' and is_final=1",c)
    s=p.merge(truth,on=['fixture_uuid','player_uuid'],validate='one_to_one',how='left',indicator=True)
    if not s._merge.eq('both').all() or not np.array_equal(s.total_points,s.core_points):raise ValueError('Archived cohort actuals do not match verified Core')
    report=dict(classification='REUSED_ARCHIVED_PM_SUBGROUP_DIAGNOSTIC',all=metric(s),played=metric(s[s.minutes.gt(0)]),started=metric(s[s.started.eq(1)]),by_position={str(k):metric(g) for k,g in s.groupby('pos')},promotion_allowed=False)
    (OUT/'sampler_subgroup_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
