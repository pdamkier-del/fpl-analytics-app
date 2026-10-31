"""Read-only pipeline consistency diagnostics; no forecast or manager mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.experimental_mean_preserving_minutes import clipped_rounded_mean
from fpl_xpts.optimize import plan_squad


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--preview',required=True)
    parser.add_argument('--pm-input',required=True)
    parser.add_argument('--out',default='analysis/results/model-priorities-20261021/evidence.json')
    args=parser.parse_args();root=Path(args.preview)
    current=json.loads((root/'current/forecast.json').read_text())
    public=json.loads((root/'gk/forecast.json').read_text())
    docs=json.loads((root/'current/existing-app-data.json').read_text())['documents']['current-players.json']
    catalogue={p['id']:p for p in docs['players']}
    pm=pd.read_csv(args.pm_input,low_memory=False)
    examples=[]
    for name,team in [('Penders','Chelsea'),('Saka','Arsenal'),('Palmer','Chelsea')]:
        p=next(p for p in current['players']if p['name']==name and p['team']==team)
        q=next(q for q in public['players']if q['id']==p['id'])
        a,b=p['weeks'][0],q['weeks'][0];fx=a['fixtures'][0]
        row=dict(name=name,team=team,planning_xm=a['xmins'],planning_pm_minutes=fx['pm_analytic_minutes'],
                 planning_xp=a['xpts'],panel_xm=b['xmins'],panel_xp=b['xpts'])
        if name in ('Saka','Palmer'):
            row.update(official_penalty_order=catalogue[p['id']]['penalties_order'],
                       penalty_weight=float(pm[pm.player_uuid.eq(p['player_uuid'])&pm.gw.eq(a['gw'])].pen_weight.iloc[0]))
        examples.append(row)
    delta=np.array([fx['xmins']-fx['pm_analytic_minutes']for p in current['players']if p['position']!=1
                    for w in p['weeks']for fx in w['fixtures']])
    # Synthetic legal position counts, independent goalkeepers and certain field players.
    # Captain always a field player, isolating the omitted bench-GK contribution.
    positions=['GKP']*2+['DEF']*5+['MID']*5+['FWD']*3
    frame=pd.DataFrame([dict(id=i+1,position=pos,gw=1,xpts_mean=(4. if i==0 else 2. if i==1 else 6.),
                             p_play=(.8 if i==0 else 1.))for i,pos in enumerate(positions)])
    first=plan_squad(frame,list(range(1,16)),1)
    better=frame.copy();better.loc[better.id.eq(2),'xpts_mean']=3.
    second=plan_squad(better,list(range(1,16)),1)
    assert first.expected_score==second.expected_score
    files=[root/'current/forecast.json',root/'gk/forecast.json',Path(args.pm_input)]
    evidence=dict(classification='READ_ONLY_ARCHIVED_SNAPSHOT_AND_CODE_REVIEW',
                  data_asof=current['data_asof'],forecast_sha256=current['forecast_sha256'],
                  panel_data_asof=public['data_asof'],panel_forecast_sha256=public['forecast_sha256'],
                  examples=examples,outfield_minutes=dict(rows=len(delta),
                      mean_mm_minus_pm=float(delta.mean()),mean_absolute_gap=float(abs(delta).mean()),
                      rows_absolute_gap_above_one_minute=int((abs(delta)>1).sum()),max_gap=float(delta.max())),
                  normal_location_90_actual_clipped_mean=clipped_rounded_mean(90.,10.),
                  bench_control=dict(kind='SYNTHETIC_NOT_USER_TEAM',
                      baseline_score=first.expected_score,better_bench_score=second.expected_score,
                      backup_gk_xp_before=2.,backup_gk_xp_after=3.,starter_no_play_probability=.2,
                      expected_score_gain_under_independent_autosub=.2),
                  source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},
                  live_refresh_performed=False,production_changed=False)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
