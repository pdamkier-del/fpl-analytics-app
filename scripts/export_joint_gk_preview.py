#!/usr/bin/env python3
"""Export validated public GK evidence only; no private TS plan/state files."""
from pathlib import Path
import hashlib,json
import pandas as pd
from gk_joint_bridge import VERSION
from mm_locked_bridge import locked_sampler_expectation
from fpl_v1_1_model.forecast_snapshot import require_snapshot
ROOT=Path(__file__).resolve().parents[1]

def dump(path,value):
    b=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();path.write_bytes(b)
    return hashlib.sha256(b).hexdigest()

def export():
    source=ROOT/'work/joint-gk-current';repeat=ROOT/'work/joint-gk-repeat';out=ROOT/'app/mm-preview/gk';out.mkdir(exist_ok=True)
    for file in ['forecast.json','gk-mm.json','gk-audit.json']:
        if (source/file).read_bytes()!=(repeat/file).read_bytes():raise ValueError('Joint GK repeat differs: '+file)
    forecast=json.loads((source/'forecast.json').read_text());require_snapshot(forecast)
    mm=json.loads((source/'gk-mm.json').read_text());audit=json.loads((source/'gk-audit.json').read_text())
    if forecast['model']!=VERSION or not audit['point_components_reconciled']:raise ValueError('GK model gate failed')
    historical=json.loads((ROOT/'work/joint-gk-historical/summary.json').read_text())
    uncertainty=json.loads((ROOT/'work/joint-gk-historical/uncertainty.json').read_text())
    stages=json.loads((source/'stage-validation.json').read_text());ts=json.loads((source/'ts-validation.json').read_text())
    if not historical['all_team_gk_minutes_90'] or not stages['passed'] or not ts['ts_ran']:raise ValueError('GK validation missing')
    baseline=json.loads((source/'baseline-mm.json').read_text())['players']
    points=pd.read_csv(source/'paired-baseline.csv.gz').set_index(['fixture_uuid','player_uuid'])
    before=[]
    for r in baseline:
        k=(r['fixture_id'],r['player_id']);p=points.loc[k]
        before.append(dict(fixture_uuid=k[0],player_uuid=k[1],p=r['p_start'],xm=r['xmins'],pm=float(locked_sampler_expectation(r['p_start'],r['p_sub_given_not_start'],r['start_minutes'],r['sub_minutes'])),sampled_pm=float(p.minutes),xp=float(p.xpts)))
    index=dict(model=VERSION,forecast_sha256=dump(out/'forecast.json',forecast),mm_sha256=dump(out/'gk-mm.json',mm),before_sha256=dump(out/'before.json',dict(players=before)))
    dump(out/'evidence.json',dict(model=VERSION,historical=historical,uncertainty=uncertainty,stages=stages,ts=ts,
        deterministic_repeat=True,production_changed=False,intervals_independently_certified=False,
        official_sources=forecast['official_gk_evidence']))
    dump(out/'index.json',index)
    print(json.dumps(index,indent=2))
if __name__=='__main__':export()
