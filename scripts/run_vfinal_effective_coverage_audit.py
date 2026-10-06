#!/usr/bin/env python3
from pathlib import Path
import sys,json,pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base
from fpl_xpts.identity import resolve_uuid_to_fpl_ids
from fpl_xpts.vfinal_forecast import compose_current_forecast,composition_summary

VF=ROOT/'analysis/results/vfinal-integrated-20261005-v1/predictions.csv.gz'
FEAT=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
OUT=ROOT/'analysis/results/vfinal-effective-coverage-audit-20261006-v2'

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    gws,names,forecast=base.prepare()
    feat=pd.read_csv(FEAT,usecols=['player_uuid','player']).drop_duplicates()
    raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
    mp,detail=resolve_uuid_to_fpl_ids(feat,raw)
    vf=pd.read_csv(VF)
    vf['id']=vf.player_uuid.astype(str).map(mp)
    vf=vf[vf.id.notna()].copy();vf.id=vf.id.astype(int)
    vf=vf.groupby(['gw','id'],as_index=False).agg(vfinal_xp=('vfinal_xpts','sum'))
    # p(play) is intentionally taken from Phase5Q in this fast coverage audit;
    # the full replay overlays combined-minutes p(play) where integrated vFinal exists.
    vf['vfinal_p_play']=np.nan

    rows=[];comps=[]
    for gw in range(22,39):
        meta=hp.gw_meta(gws,names,gw)
        origin=base.origin_with_meta(forecast,meta,gw)
        cur=(origin[origin.gw.eq(gw)][['id','gw','xpts_mean','p_play']]
             .groupby(['id','gw'],as_index=False).agg(xpts_mean=('xpts_mean','sum'),p_play=('p_play','max')))
        v= vf[vf.gw.eq(gw)].copy()
        # preserve Phase5Q p(play) when vFinal p(play) is unavailable in this audit
        v=v.merge(cur[['id','p_play']],on='id',how='left')
        v['vfinal_p_play']=v.p_play
        v=v[['id','gw','vfinal_xp','vfinal_p_play']]
        comp=compose_current_forecast(cur,v,gw)
        comps.append({'gw':gw,**composition_summary(comp)})
        act=hp.actual_gw(gws,gw)[['id','minutes','points']]
        z=act.merge(comp[['id','xpts_mean','p_play','forecast_source']],on='id',how='left')
        z=z[z.minutes>0].copy();z['gw']=gw
        z['artificial_missing']=z.xpts_mean.isna()
        z['effective_zero']=z.xpts_mean.fillna(0).abs().le(1e-12)
        rows.append(z)
    allp=pd.concat(rows,ignore_index=True)
    coverage=pd.DataFrame(comps)
    allp.to_csv(OUT/'active_effective_forecasts.csv',index=False)
    coverage.to_csv(OUT/'coverage_by_gw.csv',index=False)
    zero=allp[allp.effective_zero].copy()
    zero.to_csv(OUT/'active_effective_zero.csv',index=False)
    summary={
      'identity':{'mapped':len(mp),'total':len(feat),'share':len(mp)/len(feat)},
      'active_player_gws':int(len(allp)),
      'artificial_missing_active_player_gws':int(allp.artificial_missing.sum()),
      'effective_zero_active_player_gws':int(zero.shape[0]),
      'effective_zero_actual_points':int(zero.points.sum()),
      'mean_vfinal_share_all_forecast_rows':float(coverage.vfinal_share.mean()),
      'mean_phase5q_fallback_rows':float(coverage.phase5q_fallback.mean()),
      'policy':'vFinal when row exists, otherwise explicit Phase5Q fallback; missing vFinal never becomes zero'
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
