#!/usr/bin/env python3
from pathlib import Path
import sys,unicodedata,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_horizon_policy_comparison as hp
import run_transfer_strategy_v3_replay as base

OUT=ROOT/'analysis/results/vfinal-zero-xp-audit-20261006-v1'
VF=ROOT/'analysis/results/vfinal-integrated-20261005-v1/predictions.csv.gz'
FEAT=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
MINS=ROOT/'analysis/results/v4-combined-minutes-20261005-v1/reused_diagnostic_predictions.csv.gz'

def norm(x):
 s=unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().casefold()
 return ''.join(c for c in s if c.isalnum())

def build_mapping(raw,feat):
 cand={}
 for r in raw.drop_duplicates('id').itertuples():
  vals=[getattr(r,'web_name',''),f"{getattr(r,'first_name','')} {getattr(r,'second_name','')}"]
  for v in vals:
   k=norm(v)
   if k:cand.setdefault(k,set()).add(int(r.id))
 uuid_to_id={};id_to_uuid={}
 for r in feat[['player_uuid','player']].drop_duplicates().itertuples():
  ids=cand.get(norm(r.player),set())
  if len(ids)==1:
   pid=next(iter(ids));uuid_to_id[str(r.player_uuid)]=pid;id_to_uuid.setdefault(pid,[]).append(str(r.player_uuid))
 return uuid_to_id,id_to_uuid,cand

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 gws,names,forecast=base.prepare()
 raw=hp.unpack_runtime('players_raw.csv').drop_duplicates('id').copy()
 feat=pd.read_csv(FEAT)
 uuid_to_id,id_to_uuid,cand=build_mapping(raw,feat)

 vf=pd.read_csv(VF)
 vf['mapped_id']=vf.player_uuid.astype(str).map(uuid_to_id)
 vf_m=vf[vf.mapped_id.notna()].copy();vf_m.mapped_id=vf_m.mapped_id.astype(int)
 vf_sum=vf_m.groupby(['gw','mapped_id'],as_index=False).agg(vfinal_xp=('vfinal_xpts','sum'),vf_rows=('vfinal_xpts','size'))

 mins=pd.read_csv(MINS)
 mins['mapped_id']=mins.player_uuid.astype(str).map(uuid_to_id)
 mins_m=mins[mins.mapped_id.notna()].copy();mins_m.mapped_id=mins_m.mapped_id.astype(int)
 mins_g=mins_m.groupby(['gw','mapped_id'],as_index=False).agg(
   min_rows=('player_uuid','size'),
   combined_p_start=('combined_p_start','max'),
   combined_q_sub=('combined_q_sub','max')
 )

 # Phase5Q current-GW coverage
 phase_rows=[]
 for gw in range(22,39):
  meta=hp.gw_meta(gws,names,gw)
  origin=base.origin_with_meta(forecast,meta,gw)
  cur=origin[origin.gw==gw].groupby('id',as_index=False).agg(
    phase5q_xp=('xpts_mean','sum'),
    phase5q_p_play=('p_play','max') if 'p_play' in origin.columns else ('xpts_mean',lambda s:np.nan)
  )
  cur['gw']=gw;phase_rows.append(cur)
 phase=pd.concat(phase_rows,ignore_index=True)

 rows=[]
 for gw in range(22,39):
  meta=hp.gw_meta(gws,names,gw)[['id','web_name','position','team']].drop_duplicates('id')
  act=hp.actual_gw(gws,gw)[['id','points','minutes']].rename(columns={'points':'actual_points'})
  z=meta.merge(act,on='id',how='left')
  z[['actual_points','minutes']]=z[['actual_points','minutes']].fillna(0)
  z=z[z.minutes>0].copy();z['gw']=gw
  z=z.merge(vf_sum[vf_sum.gw==gw][['mapped_id','vfinal_xp','vf_rows']],left_on='id',right_on='mapped_id',how='left')
  z=z.merge(mins_g[mins_g.gw==gw][['mapped_id','min_rows','combined_p_start','combined_q_sub']],left_on='id',right_on='mapped_id',how='left',suffixes=('','_min'))
  z=z.merge(phase[phase.gw==gw][['id','phase5q_xp','phase5q_p_play']],on='id',how='left')
  z['has_uuid_mapping']=z.id.map(lambda x: int(x) in id_to_uuid)
  z['mapped_uuid_count']=z.id.map(lambda x: len(id_to_uuid.get(int(x),[])))
  z['present_vfinal']=z.vf_rows.notna()
  z['present_minutes']=z.min_rows.notna()
  z['vfinal_xp_filled']=z.vfinal_xp.fillna(0.0)

  def classify(r):
   if not r.has_uuid_mapping:return 'NO_UUID_TO_FPL_MAPPING'
   if not r.present_vfinal:
    if not r.present_minutes:return 'MAPPED_BUT_ABSENT_VFINAL_AND_MINUTES_GW'
    return 'MAPPED_PRESENT_MINUTES_BUT_ABSENT_VFINAL_GW'
   if float(r.vfinal_xp_filled)<=1e-12:return 'TRUE_VFINAL_ZERO'
   return 'HAS_POSITIVE_VFINAL'
  z['category']=z.apply(classify,axis=1)
  rows.append(z)
 allp=pd.concat(rows,ignore_index=True)

 zero=allp[allp.vfinal_xp_filled<=1e-12].copy()
 zero=zero.sort_values(['actual_points','minutes'],ascending=False)
 zero.to_csv(OUT/'active_zero_xp_players.csv',index=False)

 # focus on costly cases
 costly=zero[(zero.actual_points>=8)|(zero.minutes>=60)].copy()
 costly.to_csv(OUT/'active_zero_xp_costly.csv',index=False)

 cat=(zero.groupby('category',as_index=False)
      .agg(player_gws=('id','size'),actual_points=('actual_points','sum'),minutes=('minutes','sum')))
 cat.to_csv(OUT/'category_summary.csv',index=False)

 examples=zero.head(40)[[
  'gw','web_name','position','actual_points','minutes','category',
  'has_uuid_mapping','present_vfinal','present_minutes','phase5q_xp','phase5q_p_play'
 ]].to_dict(orient='records')

 summary={
  'active_player_gws':int(len(allp)),
  'zero_vfinal_active_player_gws':int(len(zero)),
  'zero_share':float(len(zero)/len(allp)) if len(allp) else 0,
  'zero_actual_points_total':int(zero.actual_points.sum()),
  'categories':cat.to_dict(orient='records'),
  'top_zero_cases':examples,
  'interpretation':{
   'NO_UUID_TO_FPL_MAPPING':'identity layer failed; vFinal could not be attached to this FPL player',
   'MAPPED_BUT_ABSENT_VFINAL_AND_MINUTES_GW':'identity exists, but target GW is outside/missing from both integrated vFinal and combined-minutes artifacts',
   'MAPPED_PRESENT_MINUTES_BUT_ABSENT_VFINAL_GW':'minutes exists but integrated point forecast missing; integration/wiring gap',
   'TRUE_VFINAL_ZERO':'integrated forecast row exists but sums to zero; inspect point-model logic'
  }
 }
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
