#!/usr/bin/env python3
"""Audit why PM(vFinal current GW)+TS(v4) warmstart underperformed Phase5Q TS v4.

Compares completed artifacts:
- TS v4 Phase5Q full-season proxy (2120)
- PM/TS vFinal-current-GW warmstart (2009)

Focus GW22-38 where PM differs. Also checks forecast scale mismatch between
current-GW vFinal and Phase5Q on matched player-GW rows.
"""
from __future__ import annotations
import json,sys,unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base

OLD=ROOT/'analysis/results/compare_inputs/ts_v4_phase5q'
NEW=ROOT/'analysis/results/compare_inputs/pm_ts_vfinal'
VFINAL=ROOT/'analysis/results/vfinal-integrated-20261005-v1'
OUT=ROOT/'analysis/results/pm-ts-underperformance-audit-20261006-v1'


def ints(x):
    if pd.isna(x) or str(x).strip()=='':
        return []
    return [int(float(v)) for v in str(x).split(';') if str(v).strip() and str(v)!='nan']


def _norm_name(x):
    s=unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().casefold()
    return ''.join(ch for ch in s if ch.isalnum())


def mapping_uuid_to_id():
    feat=pd.read_csv(
        ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz',
        usecols=['player_uuid','player']
    ).drop_duplicates()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
    candidates={}
    for r in raw.itertuples():
        vals=[getattr(r,'web_name','')]
        first=getattr(r,'first_name','');second=getattr(r,'second_name','')
        if str(first)!='nan' or str(second)!='nan':
            vals.append(f"{first} {second}")
        for v in vals:
            k=_norm_name(v)
            if k:candidates.setdefault(k,set()).add(int(r.id))
    out={}
    for r in feat.itertuples():
        ids=candidates.get(_norm_name(r.player),set())
        if len(ids)==1:out[str(r.player_uuid)]=next(iter(ids))
    return out


def executed_plan(frame):
    if 'is_executed' in frame.columns:
        q=frame[frame.is_executed.astype(str).str.lower().isin(['true','1'])]
    else:
        q=frame[frame.step==1]
    return q.sort_values('origin_gw').copy()


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    oldlog=pd.read_csv(OLD/'gameweek_log.csv')
    newlog=pd.read_csv(NEW/'gameweek_log.csv')
    oldplans=executed_plan(pd.read_csv(OLD/'plans.csv'))
    newplans=executed_plan(pd.read_csv(NEW/'plans.csv'))

    c=oldlog.merge(newlog,on='gw',suffixes=('_old','_new'))
    c['score_delta']=c.score_new-c.score_old
    c['cum_delta']=c.cumulative_new-c.cumulative_old
    c['transfer_delta']=c.transfers_new-c.transfers_old
    c['hit_delta']=c.hit_points_new-c.hit_cost_old if 'hit_points_new' in c else c.hit_cost_new-c.hit_cost_old
    c.to_csv(OUT/'gameweek_comparison.csv',index=False)

    op=oldplans[['origin_gw','outgoing','incoming','transfers']].rename(columns={
        'outgoing':'out_old','incoming':'in_old','transfers':'tx_old'})
    np_=newplans[['origin_gw','outgoing','incoming','transfers']].rename(columns={
        'outgoing':'out_new','incoming':'in_new','transfers':'tx_new'})
    p=op.merge(np_,on='origin_gw',how='outer')
    p['same_transfer']=(
        p.out_old.fillna('').astype(str).eq(p.out_new.fillna('').astype(str))&
        p.in_old.fillna('').astype(str).eq(p.in_new.fillna('').astype(str))
    )
    p.to_csv(OUT/'executed_transfer_comparison.csv',index=False)

    # Forecast scale comparison on GW22-38 current-GW values.
    gws,names,forecast=base.prepare()
    mp=mapping_uuid_to_id()
    vf=pd.read_csv(VFINAL/'predictions.csv.gz')
    vf['id']=vf.player_uuid.astype(str).map(mp)
    vf=vf[vf.id.notna()].copy();vf.id=vf.id.astype(int)
    vf=vf.groupby(['gw','id'],as_index=False).agg(vfinal_xp=('vfinal_xpts','sum'))

    rows=[]
    for gw in range(22,39):
        phase=forecast[(forecast.origin_gw==gw-1)&(forecast.gw==gw)][['id','xpts_mean']].copy()
        phase=phase.groupby('id',as_index=False).xpts_mean.sum().rename(columns={'xpts_mean':'phase5q_xp'})
        z=phase.merge(vf[vf.gw==gw][['id','vfinal_xp']],on='id',how='inner')
        if z.empty: continue
        z['gw']=gw
        z['delta']=z.vfinal_xp-z.phase5q_xp
        z['ratio']=np.where(z.phase5q_xp.abs()>1e-9,z.vfinal_xp/z.phase5q_xp,np.nan)
        rows.append(z)
    scale=pd.concat(rows,ignore_index=True)
    scale.to_csv(OUT/'current_gw_forecast_scale.csv',index=False)

    scale_by_gw=scale.groupby('gw').agg(
        n=('id','size'),
        phase_mean=('phase5q_xp','mean'),
        vfinal_mean=('vfinal_xp','mean'),
        mean_delta=('delta','mean'),
        median_delta=('delta','median'),
        mean_ratio=('ratio','mean'),
        corr=('phase5q_xp',lambda s: np.nan)
    ).reset_index()
    # explicit correlation
    for i,row in scale_by_gw.iterrows():
        g=scale[scale.gw==row.gw]
        scale_by_gw.loc[i,'corr']=g[['phase5q_xp','vfinal_xp']].corr().iloc[0,1]
    scale_by_gw.to_csv(OUT/'forecast_scale_by_gw.csv',index=False)

    late=c[c.gw>=22].copy()
    changed=p[p.origin_gw>=22].copy()
    changed_count=int((~changed.same_transfer).sum())

    worst=late.nsmallest(8,'score_delta')[['gw','score_old','score_new','score_delta','transfers_old','transfers_new']]
    best=late.nlargest(5,'score_delta')[['gw','score_old','score_new','score_delta']]

    summary={
      'old_total':int(oldlog.score.sum()),
      'new_total':int(newlog.score.sum()),
      'delta_total':int(newlog.score.sum()-oldlog.score.sum()),
      'old_gw1_21':int(oldlog[oldlog.gw<=21].score.sum()),
      'new_gw1_21':int(newlog[newlog.gw<=21].score.sum()),
      'delta_gw1_21':int(newlog[newlog.gw<=21].score.sum()-oldlog[oldlog.gw<=21].score.sum()),
      'old_gw22_38':int(oldlog[oldlog.gw>=22].score.sum()),
      'new_gw22_38':int(newlog[newlog.gw>=22].score.sum()),
      'delta_gw22_38':int(newlog[newlog.gw>=22].score.sum()-oldlog[oldlog.gw>=22].score.sum()),
      'late_gws_better':int((late.score_delta>0).sum()),
      'late_gws_worse':int((late.score_delta<0).sum()),
      'late_gws_equal':int((late.score_delta==0).sum()),
      'late_transfer_decisions_changed':changed_count,
      'late_transfer_decisions_total':int(len(changed)),
      'mean_current_gw_phase5q_xp':float(scale.phase5q_xp.mean()),
      'mean_current_gw_vfinal_xp':float(scale.vfinal_xp.mean()),
      'mean_current_gw_delta':float(scale.delta.mean()),
      'median_current_gw_delta':float(scale.delta.median()),
      'overall_current_gw_corr':float(scale[['phase5q_xp','vfinal_xp']].corr().iloc[0,1]),
      'worst_gws':worst.to_dict(orient='records'),
      'best_gws':best.to_dict(orient='records'),
      'interpretation_note':(
        'This isolates observed replay differences. It does not prove causality; '
        'current-GW vFinal is mixed with Phase5Q future-horizon values, so scale/ranking '
        'disagreement can change MPC transfer choices.'
      )
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
