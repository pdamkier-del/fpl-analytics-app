from pathlib import Path
import sqlite3, json
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/v1_1/pstart_v2_joint_validation'; DB=ROOT/'data_v1_1/normalized/fpl_v1_1.sqlite3'
con=sqlite3.connect(DB)
# Identity mapping for frozen v1 rows.
mp=pd.read_sql_query("select player_uuid,cast(external_id as integer) id from player_id_mapping where id_namespace='fpl_element' and season='2025-26'",con).drop_duplicates(['player_uuid'])
# Official bonus points per fixture, kept separate because historical BPS rules differ from 2026/27.
bonus=pd.read_sql_query("""
select o.player_uuid,o.fixture_uuid,coalesce(sum(case when c.component='bonus' then c.points else 0 end),0) actual_bonus
from player_fixture_observations o left join player_fixture_point_components c on c.observation_id=o.observation_id
where o.season='2025-26' group by o.player_uuid,o.fixture_uuid
""",con)
x=pd.read_csv(OUT/'joint_xpts_pstart_v2_80sim_2025_26_gw22_38.csv').merge(mp,on='player_uuid',how='inner').merge(bonus,on=['player_uuid','fixture_uuid'],how='left')
x['actual_bonus']=x.actual_bonus.fillna(0)
# Sum fixture means for DGWs. Quantiles are deliberately not summed; Phase 4C evaluates central mean/calibration at player-GW level.
g=x.groupby(['id','gw'],as_index=False).agg(v11_full=('xPts_v1_1_candidate','sum'),v11_nonbonus=('xPts_nonbonus','sum'),v11_expected_bonus=('expected_bonus_mc','sum'),actual_full=('actual_points_reference_only','sum'),actual_bonus=('actual_bonus','sum'))
g['actual_nonbonus']=g.actual_full-g.actual_bonus
v=pd.read_csv(ROOT/'outputs/model_v1_validation/predictions_with_v1_ensemble.csv')
v=v[(v.backtest_season=='2025-26')&(v.horizon==1)&v.target_gw.between(22,38)].copy()
v=v[['id','target_gw','simple_xmins_xg_xa_fixture','xpts_mean','actual_points','p_10_plus','p_attacking_return']].rename(columns={'target_gw':'gw','simple_xmins_xg_xa_fixture':'v10_simple','xpts_mean':'v10_event'})
m=g.merge(v,on=['id','gw'],how='inner')

def metrics(pred,actual):
 e=np.asarray(pred)-np.asarray(actual)
 return {'n':len(e),'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e))}
res={
 'matched_player_gw':len(m),
 'bonus_neutral_primary':{
   'v1_1_joint_nonbonus':metrics(m.v11_nonbonus,m.actual_nonbonus),
   'v1_0_simple_nonbonus':metrics(m.v10_simple,m.actual_nonbonus),
 },
 'full_points_diagnostic_not_rules_comparable':{
   'v1_1_joint_with_2026_27_bps':metrics(m.v11_full,m.actual_full),
   'v1_0_event_legacy':metrics(m.v10_event,m.actual_full),
   'v1_0_simple':metrics(m.v10_simple,m.actual_full),
 },
 'means':{k:float(m[k].mean()) for k in ['v11_nonbonus','v10_simple','actual_nonbonus','v11_full','v10_event','actual_full','v11_expected_bonus','actual_bonus']}
}
# paired GW block bootstrap difference in MAE/RMSE: v1.1 - v1.0, bonus-neutral.
rng=np.random.default_rng(26092026); gws=sorted(m.gw.unique()); boot=[]
for _ in range(5000):
 sample=rng.choice(gws,size=len(gws),replace=True)
 z=pd.concat([m[m.gw==w] for w in sample],ignore_index=True)
 a=z.actual_nonbonus.to_numpy(); p1=z.v11_nonbonus.to_numpy(); p0=z.v10_simple.to_numpy()
 boot.append((np.mean(abs(p1-a))-np.mean(abs(p0-a)), np.sqrt(np.mean((p1-a)**2))-np.sqrt(np.mean((p0-a)**2))))
b=np.asarray(boot)
res['paired_gw_block_bootstrap_v11_minus_v10']={'mae_diff_ci95':[float(x) for x in np.quantile(b[:,0],[.025,.975])], 'rmse_diff_ci95':[float(x) for x in np.quantile(b[:,1],[.025,.975])]}
(OUT/'pstart_v2_joint_metrics.json').write_text(json.dumps(res,indent=2))
m.to_csv(OUT/'pstart_v2_matched_player_gw_evaluation.csv',index=False)
print(json.dumps(res,indent=2))
