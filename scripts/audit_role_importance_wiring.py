"""Read-only wiring/assignment audit, not a new predictive model."""
import json,hashlib,argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.special import logit
from mm_candidate import FormationSelector
from mm_candidate_forecast import infer_B
from fpl_v1_1_model.role_classifier import template,role_family
ROOT=Path(__file__).resolve().parents[1]


def matrix(players,slots):
 m=np.full((len(slots),len(players)),-np.inf)
 for j,p in enumerate(players):
  if p['p_start']<=0:continue
  rr=p['role_probabilities'];keeper=p['primary_role']=='GK'or p.get('position')in ['GK','GKP']
  for i,slot in enumerate(slots):
   if keeper!=(slot=='GK'):continue
   exact=rr.get(slot,0);family=sum(v for r,v in rr.items()if role_family(r)==role_family(slot))
   m[i,j]=logit(np.clip(p['p_start'],1e-7,1-1e-7))+.5*np.log(.02+.78*exact+.20*family)
 return m


def assign(m,players,slots,forced=None):
 m=m.copy()
 for name,slot in (forced or {}).items():
  j=next(j for j,p in enumerate(players)if p['name']==name);i=slots.index(slot);v=m[i,j];m[i,:]=-np.inf;m[:,j]=-np.inf;m[i,j]=v
 try:row,col=linear_sum_assignment(-m)
 except ValueError:return dict(feasible=False)
 if len(row)!=11 or not np.isfinite(m[row,col]).all():return dict(feasible=False)
 return dict(feasible=True,assignment_score=float(m[row,col].sum()),XI=[dict(slot=slots[i],player=players[j]['name'])for i,j in zip(row,col)])


def main():
 a=argparse.ArgumentParser();a.add_argument('--mm',type=Path,required=True);a.add_argument('--inputs',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
 raw=args.mm.read_bytes();mm=json.loads(raw)
 target_all=pd.read_csv(args.inputs/'target.csv.gz',float_precision='round_trip')
 positions={str(r.player_uuid):r.pos for r in target_all[target_all.fixture_uuid.eq('live-2026-27-fpl-72')].itertuples()}
 players=[dict(p,position=positions[p['player_id']])for p in mm['players']if p.get('club_id')==15 and p.get('gw')==8];assert players
 form=next(p['formation']for p in players if p['formation']);slots=['GK']+[r for line in template(form)for r in line]
 m=matrix(players,slots);best=assign(m,players,slots);both=assign(m,players,slots,{'Foden':'RAM','Cherki':'CAM'});trio=assign(m,players,slots,{'Doku':'LAM','Cherki':'CAM','Foden':'RAM'})
 assert best['feasible']and both['feasible']
 chosen={p['name']:p for p in players if p['name']in ['Foden','Cherki','Ndiaye']}
 roles=pd.read_csv(args.inputs/'roles.csv.gz');target=target_all[target_all.fixture_uuid.eq('live-2026-27-fpl-72')&target_all.team_id.eq(15)].copy().reset_index(drop=True)
 history=pd.read_csv(args.inputs/'history.csv.gz',low_memory=False,float_precision='round_trip');prov=json.loads((args.inputs/'provenance.json').read_text());pred,_=infer_B(history,target,prov)
 changed=target.copy();changed['future_rotation_pressure']=1000.;changed['future_next_importance']=1000.;changed['target_match_importance']=-1000.;changed['role_CAM']=1000.;changed['role_RAM']=-1000.
 after,_=infer_B(history,changed,prov);assert np.array_equal(pred.p.to_numpy(),after.p.to_numpy())
 selector=FormationSelector(roles);old=selector.choose(pred)
 altered=roles.copy();altered['importance']=1-pd.to_numeric(altered.importance)
 new=FormationSelector(altered).choose(pred);assert old==new
 d=dict(classification='READ_ONLY_ROLE_IMPORTANCE_WIRING_AUDIT',public_MM_data_at=mm.get('data_at'),public_MM_file_sha256=hashlib.sha256(raw).hexdigest(),frozen_B_input_cutoff=prov['data_at'],input_sha256={n:hashlib.sha256((args.inputs/n).read_bytes()).hexdigest()for n in ['target.csv.gz','history.csv.gz','roles.csv.gz','provenance.json']},code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),role_ledger_matches=int(roles.match_id.nunique()),role_ledger_matches_by_competition=roles[['match_id']].drop_duplicates().match_id.str.replace(r'^26-27-','',regex=True).str.replace(r'-\d+$','',regex=True).value_counts().to_dict(),public_roles={k:{n:p.get(n)for n in ['p_start','primary_role','secondary_role','role_probabilities']}for k,p in chosen.items()},display_assignment=best,forced_Foden_right_Cherki_central=both,forced_attacking_trio_Doku_Cherki_Foden=trio,assignment_score_gap=best['assignment_score']-both['assignment_score'],important_caveat='Assignment score is an optimizer objective, not a probability or evidence that either XI will start.',controlled_wiring_checks={'B_probabilities_unchanged_when_unconsumed_importance_and_role_columns_mutated':True,'display_roles_and_XI_unchanged_when_historical_importance_reversed':True,'B_p_start_has_no_feedback_from_FormationSelector':True},findings=['Foden already has historical RAM and RW support; the problem is not missing right-wing eligibility.','FormationSelector chooses a point XI after B marginal probabilities are fixed; the role history does not feed back from this assignment into those probabilities.','FormationSelector uses unweighted historical role counts with time decay and formation frequencies; its input importance column is discarded.','Upstream role summaries and PM tactical priors do exist; these checks do not claim that all earlier model components ignore roles or importance.','The joint starter kernel in joint_simulator uses exact outfield count and marginal p, not formation-slot compatibility or alternative-XI importance scores.','No proper end-to-end role-by-target-importance calibration/alternative-XI historical validation is established by the existing unit tests.'],production_changed=False,preview_changed=False,model_changed=False)
 args.out.mkdir(parents=True,exist_ok=True);(args.out/'audit.json').write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');print(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
