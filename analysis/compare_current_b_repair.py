"""Same-source current B control; never used as a production forecast."""
import argparse,json,shutil
from pathlib import Path
import pandas as pd
from build_current_b_inputs import historical_B_training,current_observations
from current_b_features import prior_features
from b_physical_workload import FIELDS
from run_joint_gk_preview import current

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=Path('work/current-B-inputs'));p.add_argument('--out',type=Path,default=Path('work/integrated-B-before'));p.add_argument('--after',type=Path,default=Path('work/joint-gk-current'));a=p.parse_args();temp=a.out/'inputs';shutil.copytree(a.inputs,temp,dirs_exist_ok=True)
    prov=json.loads((temp/'provenance.json').read_text());cut=pd.Timestamp(prov['data_at']);b=json.loads((temp/'bootstrap.json').read_text());t=pd.read_csv(temp/'target.csv.gz',low_memory=False)
    original=prior_features(t,current_observations(cut,b),pd.read_csv('work/previous-B-role-ledger.csv.gz',low_memory=False))
    for name in FIELDS:t[name]=original[name]
    t=t.drop(columns=[name for name in t if name.startswith(('persistent_','medical_','eligibility_'))or name in ['physical_feature_version','role_horizon_absence']])
    h=historical_B_training();h=h[pd.to_datetime(h.known_at,utc=True).lt(cut)]
    t.to_csv(temp/'target.csv.gz',index=False);h.to_csv(temp/'history.csv.gz',index=False)
    for name in ['physical_feature_version','physical_workload_coverage']:prov.pop(name,None)
    prov['source_scopes']['explicit_workload_and_last_start']='Premier League only';(temp/'provenance.json').write_text(json.dumps(prov,indent=2)+'\n')
    current(temp,a.out,paired=False,chain=True,assignment_policy='analysis/results/joint-role-candidate-20261022/policy.json',goal_head_policy='analysis/results/integrated-repair-20261031/nonpenalty-policy.json',physical_minutes=True)
    write_comparison(a.out,a.after)

def write_comparison(before,after):
    before=json.loads((Path(before)/'forecast.json').read_text());after_path=Path(after);after=json.loads((after_path/'forecast.json').read_text());by={p['id']:p for p in before['players']};rows=[]
    if before['gws']!=after['gws']:raise ValueError('Control horizon differs')
    for p in after['players']:
        if p['name']not in ['Penders','E.Le Fée','Cherki','Sávio']:continue
        for arm,player in [('before',by[p['id']]),('after',p)]:
            w=player['weeks'][0];f=w['fixtures'][0];rows.append(dict(player=p['name'],arm=arm,gw=w['gw'],p_start=f['p_start'],xM=w['xmins'],PM_E_minutes=w['pm_analytic_minutes'],p60=f['p_60_plus'],p90=f['p_90'],xP=w['xpts']))
    result=dict(scope='Same-source previous B features/events versus repaired B; not a cross-week comparison',data_asof=after['data_asof'],forecast_sha256=after['forecast_sha256'],monte_carlo_order_changes=True,players=rows)
    (after_path/'source-control.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':main()
