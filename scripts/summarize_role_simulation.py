"""Descriptive component diagnostics from frozen 80-draw paired forecasts."""
import hashlib
import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT = Path(__file__).resolve().parents[1]

def main():
    source = ROOT/'analysis/results/role-event-priors-20261005-v1'
    pred = read_frozen_table(source, 'predictions')
    con = sqlite3.connect(f'file:{ROOT}/work/core.sqlite3?mode=ro', uri=True)
    obs = pd.read_sql_query("SELECT observation_id,fixture_uuid,player_uuid,fpl_position,total_points FROM player_fixture_observations WHERE season='2025-26'", con)
    comp = pd.read_sql_query("SELECT c.* FROM player_fixture_point_components c JOIN player_fixture_observations o USING(observation_id) WHERE o.season='2025-26'", con)
    keys = ['fixture_uuid','player_uuid']
    for col in ['fpl_position','total_points']:
        assert obs.groupby(keys)[col].nunique().max() == 1
    linked = comp.merge(obs, on='observation_id', validate='many_to_one')
    assert linked.groupby(keys+['component']).points.nunique().max() == 1
    actual = linked.drop_duplicates(keys+['component']).pivot(index=keys,columns='component',values='points').fillna(0).add_prefix('actual_').reset_index()
    frame = pred.merge(obs.drop_duplicates(keys)[keys+['fpl_position','total_points']],on=keys,validate='one_to_one').merge(actual,on=keys,how='left',validate='one_to_one')
    acols = [c for c in frame if c.startswith('actual_')]
    frame[acols] = frame[acols].fillna(0)
    assert len(frame)==11794 and frame.fixture_uuid.nunique()==144
    mapping = {'appearance_points':['appearance'],'goal_points':['goals'],'assist_points':['fpl_assists'],'cs_points':['clean_sheet'],'save_points':['saves'],'dc_points':['defcon'],'negative_points':['yellow_cards','red_cards','own_goals'],'gc_points':['goals_conceded'],'expected_bonus':['bonus']}
    records=[]
    for component, targets in mapping.items():
        mask = pd.Series(True,index=frame.index)
        if component in ['save_points','gc_points']: mask=frame.fpl_position.isin(['GK','GKP'] if component=='save_points' else ['GK','GKP','DEF'])
        if component=='cs_points': mask=frame.fpl_position.isin(['GK','GKP','DEF','MID'])
        if component=='dc_points': mask=~frame.fpl_position.isin(['GK','GKP'])
        y=frame.loc[mask,['actual_'+c for c in targets]].sum(axis=1)
        for arm in ['current_v4','role_candidate']:
            p=frame.loc[mask,arm+'_'+component]; e=p-y
            records.append(dict(component=component,arm=arm,rows=int(mask.sum()),actual_mean=float(y.mean()),predicted_mean=float(p.mean()),mae=float(abs(e).mean()),rmse=float(np.sqrt((e**2).mean())),bias=float(e.mean())))
    out=ROOT/'analysis/results/role-event-component-summary-20261005-v1'
    out.mkdir(exist_ok=True)
    pd.DataFrame(records).to_csv(out/'component_metrics.csv',index=False)
    sums=frame.filter(regex='^actual_').sum(axis=1)
    report=dict(rows=len(frame),fixtures=144,draws_per_arm=80,classification='posthoc_reused_diagnostic_not_new_holdout',component_targets='Core reconstructed point components; not official component ledger',official_flags=sorted(comp.is_official.unique().tolist()),component_sum_mismatches=int((sums!=frame.total_points).sum()),limitations=['1200-draw confirmation retains totals only; these component estimates use 80 draws','Bonus uses inherited wrong-season BPS and is not season-valid','Penalty saves/misses are not represented by the simulator component mapping','MAEs across different point scales and cohorts are not comparable'],sources=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [source/'manifest.json',ROOT/'work/core.sqlite3',Path(__file__)]])
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(pd.DataFrame(records).to_string(index=False)); print(json.dumps(report,indent=2))

if __name__=='__main__': main()
