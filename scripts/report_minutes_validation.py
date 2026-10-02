"""Report reproduced v2 holdout metrics and posthoc actual-role diagnostic slices."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument('--predictions',required=True)
ap.add_argument('--roles',required=True)
ap.add_argument('--out',required=True)
a=ap.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
d=pd.read_csv(a.predictions)
r=pd.read_csv(a.roles)[['fixture_uuid','team_id','player_uuid','role']]
r.role=r.role.replace({'AM':'CAM'})
d=d.merge(r,on=['fixture_uuid','team_id','player_uuid'],how='left',validate='one_to_one')
d['role']=d.role.fillna('bench_no_observed_role')

def score(z):
    y=z.y.to_numpy();p=np.clip(z.p_start_v2.to_numpy(),1e-10,1-1e-10)
    e=z.expected_minutes_v2.to_numpy()-z.minutes.to_numpy()
    return {'n':len(z),'brier':float(np.mean((p-y)**2)),
            'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),
            'xmins_mae':float(np.mean(abs(e))),'xmins_rmse':float(np.sqrt(np.mean(e**2))),
            'xmins_bias':float(np.mean(e)),'mean_p_start':float(p.mean()),
            'start_rate':float(y.mean())}

summary={label:score(d[d.gw>=gw]) for label,gw in [('gw6_38',6),('gw12_38',12),('gw22_38',22)]}
summary['method']={'train':['2023-24','2024-25'],'holdout':'2025-26',
                  'features':'historical rows with GW lower than target GW; inherited benchmark uses GW order',
                  'cutoff_audit':'strict deadline/observed_at validation is pending; no new leakage-safe certification',
                  'role_slices':'actual target starter role, diagnostic only; never used in forecast features',
                  'comparison':'reproduced baseline only; original role predictions/features unavailable'}
(out/'metrics.json').write_text(json.dumps(summary,indent=2)+'\n')
for col in ['gw','team_id','pos','role','y']:
    pd.DataFrame([{col:key,**score(z)} for key,z in d.groupby(col)]).to_csv(out/f'by_{col}.csv',index=False)
d['calibration_bin']=pd.cut(d.p_start_v2,bins=np.linspace(0,1,11),include_lowest=True)
bins=d.groupby('calibration_bin',observed=True).agg(n=('y','size'),predicted=('p_start_v2','mean'),actual=('y','mean'))
bins.to_csv(out/'calibration.csv')
print(json.dumps(summary,indent=2))
