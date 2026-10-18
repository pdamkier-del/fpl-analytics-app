#!/usr/bin/env python3
"""Audit archived component forecasts against independently observed FPL events.

Never interpret forecast component totals as observed event points. Output
NOT_AVAILABLE for a component without an explicit matching truth column.
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame, restore

ROOT=Path(__file__).resolve().parents[1]
PRED=['appearance_points','goal_points','assist_points','cs_points',
      'save_points','dc_points','negative_points','gc_points',
      'penalty_save_points','expected_bonus']
# Observed points must be computed from season-correct event rules elsewhere
# or presented as an explicitly audited points column in the truth table.
OBS={k:k+'_actual' for k in PRED}

def metrics(truth,pred):
    delta=np.asarray(pred,float)-np.asarray(truth,float)
    if not np.isfinite(delta).all():raise ValueError('Nonfinite truth or predictions')
    return dict(n=int(len(delta)),mae=float(np.abs(delta).mean()),
        rmse=float(np.sqrt(np.square(delta).mean())),
        bias=float(delta.mean()),actual_mean=float(np.mean(truth)),
        predicted_mean=float(np.mean(pred)))

def audit(predictions,truth,season,arm):
    keys=['fixture_uuid','player_uuid']
    if predictions.duplicated(keys+['mode']).any() or truth.duplicated(keys).any():
        raise ValueError('Ambiguous player-fixture identity')
    p=predictions[predictions['mode'].eq(arm)].copy()
    if p.empty:raise ValueError('Requested arm missing: '+arm)
    if not set(keys+PRED+['total_points','xp'])<=set(p):
        raise ValueError('Incomplete saved PM components')
    if not set(keys+['total_points'])<=set(truth):
        raise ValueError('Missing actual FPL total points')
    q=p.merge(truth,on=keys,how='inner',validate='one_to_one',suffixes=('','_actual'))
    if len(q)!=len(p):raise ValueError('Missing observed player-fixture total')
    rows=[]
    # Archived joint-simulator targets expose observed bonus as a raw 0-3
    # FPL point value, unlike the other point components.
    if 'bonus' in q and 'expected_bonus_actual' not in q:
        q['expected_bonus_actual']=q['bonus']
    for name in PRED:
        observed=OBS[name]
        if observed not in q or q[observed].isna().any():
            rows.append(dict(season=season,arm=arm,component=name,status='NOT_AVAILABLE',
                reason='No audited observed component points in truth',n=0))
        else:
            rows.append(dict(season=season,arm=arm,component=name,status='VALID',
                **metrics(q[observed],q[name])))
    if 'total_points_actual' not in q:
        raise ValueError('Observed total points overwritten or absent')
    if 'bonus' in q and q['bonus'].notna().all():
        rows.append(dict(season=season,arm=arm,component='nonbonus_points',status='VALID',
                         **metrics(q.total_points_actual-q.bonus,q.xp-q.expected_bonus)))
    rows.append(dict(season=season,arm=arm,component='total_xP',status='VALID',
                     **metrics(q.total_points_actual,q.xp)))
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--capsule',type=Path,required=True)
    ap.add_argument('--truth-2024',type=Path,required=True)
    ap.add_argument('--truth-2025',type=Path,required=True)
    ap.add_argument('--arm',required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    rows=[]
    for season,path in [('2024-25',a.truth_2024),('2025-26',a.truth_2025)]:
        pred=load_frame(a.capsule/(season+'_pm_predictions.npz'))
        truth=pd.read_csv(path)
        rows+=audit(pred,truth,season,a.arm)
    out=a.out.resolve()
    if out.is_relative_to(ROOT/'app'):
        raise ValueError('Never publish unaudited PM components to app')
    out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'component_metrics.csv',index=False)
    (out/'audit.json').write_text(json.dumps(dict(arm=a.arm,
       missing_components=[r['component'] for r in rows if r['status']!='VALID'],
       truth_requirement='observed per-player per-fixture season-correct FPL point components',
       scope='historical_reused_not_independent'),indent=2)+'\n')
    print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
