"""Read-only full-horizon conditional-penalty replay against a sealed B release."""
import argparse,json,hashlib
from pathlib import Path
import pandas as pd
from mm_candidate_forecast import infer_B
from mm_locked_bridge import attach_mm
from gk_solo_role import mark_horizon_absences,SoloRolePolicy
from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
from run_joint_gk_preview import run,observations
ROOT=Path(__file__).resolve().parents[1]


def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--forecast',type=Path,required=True);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--squad-evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 h=pd.read_csv(a.inputs/'history.csv.gz',low_memory=False);t=pd.read_csv(a.inputs/'target.csv.gz',low_memory=False);prov=json.loads((a.inputs/'provenance.json').read_text());boot=json.loads((a.inputs/'bootstrap.json').read_text());published=json.loads(a.forecast.read_text())
 pred,_=infer_B(h,t,prov);pred=mark_horizon_absences(pred,boot);frame=attach_mm(pd.read_csv(a.inputs/'pm.csv.gz',low_memory=False),pred);squads=pd.read_csv(a.squad_evidence);squads['clock']=pd.to_datetime(squads.clock,utc=True);squads['kick']=pd.to_datetime(squads.kick,utc=True);policy=SoloRolePolicy(h,squads);catalogue={r.player_uuid:next(p for p in boot['elements']if p['id']==int(r.fpl_element))for r in frame.itertuples()};assignment=AssignmentHistory(pd.read_csv(a.inputs/'roles.csv.gz'))
 obs=observations(ROOT);obs=obs[~obs.season.eq('2026-27')]
 live=pd.read_csv(a.source_root/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz');live=live[live.fpl_position.isin(['GK','GKP','G'])].copy();live['known_at']=pd.to_datetime(live.available_at,utc=True);obs=pd.concat([obs,live[obs.columns]],ignore_index=True)
 weights=None
 if a.model:
  from nonpenalty_goal_bridge import calculate
  weights,head_audit,head_receipt=calculate(ROOT,frame,json.loads(a.model.read_text()),source_root=a.source_root)
  head_audit.to_csv(a.out/'nonpenalty-goal-head.csv.gz',index=False);(a.out/'nonpenalty-source.json').write_text(json.dumps(head_receipt,indent=2)+'\n')
 values={};means={}
 for arm,conditional in [('baseline',False),('conditional',True)]:
  xp,details,audit,_=run(frame,pred,obs,season='2026-27',incomplete_teams=(published['official_gk_evidence']['team_id'],)if published['official_gk_evidence']['unlisted_competitors']else(),role_policy=policy,chain=True,catalogue=catalogue,assignment_history=assignment,assignment_strength=.5,conditional_penalties=conditional,ordinary_goal_weights=weights if conditional else None)
  xp.to_csv(a.out/(arm+'.csv.gz'),index=False);values[arm]=xp.set_index(['fixture_uuid','player_uuid']);means[arm]=details
 reference={(f['fixture_uuid'],p['player_uuid']):f['xpts']for p in published['players']for w in p['weeks']for f in w['fixtures']}
 error=max(abs(values['baseline'].loc[k,'xpts_fixture']-v)for k,v in reference.items());assert error<1e-9,error
 for key in means['baseline']:
  for field in ['p','q','s','c','x','p60','p90']:
   assert means['baseline'][key][field]==means['conditional'][key][field],(key,field)
 rows=[]
 for p in published['players']:
  for w in p['weeks']:
   for f in w['fixtures']:
    key=f['fixture_uuid'],p['player_uuid'];rows.append(dict(player=p['name'],player_uuid=p['player_uuid'],gw=w['gw'],fixture_uuid=key[0],before=float(values['baseline'].loc[key,'xpts_fixture']),after=float(values['conditional'].loc[key,'xpts_fixture'])))
 pd.DataFrame(rows).to_csv(a.out/'comparison.csv.gz',index=False)
 source_files={**{n:a.inputs/n for n in ['history.csv.gz','target.csv.gz','pm.csv.gz','bootstrap.json','provenance.json','roles.csv.gz']},'reference_forecast':a.forecast,'squad_evidence':a.squad_evidence,'live_observations':a.source_root/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz'}
 if a.model:source_files['goal_model']=a.model
 (a.out/'receipt.json').write_text(json.dumps(dict(source_sha256={n:hashlib.sha256(path.read_bytes()).hexdigest()for n,path in source_files.items()},forecast_sha256=published['forecast_sha256'],baseline_max_error=float(error),rows=len(reference),fixtures=int(frame.fixture_uuid.nunique()),gws=sorted(map(int,frame.gw.unique())),all_analytic_minute_marginals_unchanged=True,production_or_preview_changed=False),indent=2)+'\n')
if __name__=='__main__':main()
