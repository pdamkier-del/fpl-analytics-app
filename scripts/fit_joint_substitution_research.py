"""Fit research-only substitution count, allocation and reported-minute proxies."""
from pathlib import Path
import json,gzip,hashlib
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit,logit
ROOT=Path(__file__).resolve().parent
SOURCE=None
PROTOCOL={'version':'joint-substitution-research-v1','scope':'Offline hierarchical joint count/incoming/outgoing/timing model; no production activation','fit':'Conditional heads: fit2024-25, diagnose2025-26, then refit both before evaluating2026-27 GW6/7','evaluation':'20 reused reconstructed GW6/7 matches, not independent or exact current-app forecast replay','count':'Dirichlet-smoothed empirical team outfield-substitution counts; reserve a slot for an actual simulated keeper replacement','incoming':'Ridge logistic conditional cameo propensity; weighted race without replacement among medically available bench players','outgoing':'Ridge logistic exit propensity from frozen starter-duration mean and FPL position; weighted race among starters','time':'Position-pooled historical starter reported minutes and substitute reported minutes, coupled to a single pair entry/exit time; at most3 windows','preserved':['Original XI weights and starter probabilities','Exclusive keeper law','Reported medical availability bounds','10 outfield and1 keeper active,900+90 physical minutes','At most5 substitutions and3 windows','Same event/scoring engine and goal inputs'],'changed':'Old q_sub is a soft propensity, no longer an immutable appearance ceiling; medical caps remain hard','fixed_hyperparameters':{'ridge':10,'time_pool_strength':20,'count_pseudocount_per_category':.5,'conditional_states':128},'data_limits':['No verified exact substitution times, causes or pair identities; reported FPL minutes are explicit proxies','No fitted match-score dependence, coaching statements or injury mechanisms','FPL position matching is an engineering preference, not observed tactical pair labels','Inherited audit cohort and upstream-fit provenance limitations remain']}
def design(rows,head):
 vals=[]
 for r in rows:
  base=np.clip(r['q'],1e-5,1-1e-5)if head=='incoming'else np.clip((90-r['s'])/25,.02,.98)
  vals.append([1.,float(logit(base)),float(r['pos']=='DEF'),float(r['pos']=='MID')])
 return np.asarray(vals)
def fit_head(rows,head):
 x=design(rows,head);y=np.array([r['cameo']if head=='incoming'else r['exit']for r in rows],float)
 def obj(b):
  z=x@b;return np.logaddexp(0,z).sum()-y@z+5*(b@b),x.T@(expit(z)-y)+10*b
 m=minimize(obj,np.zeros(x.shape[1]),jac=True,method='BFGS',options={'gtol':1e-7,'maxiter':1000});assert np.linalg.norm(m.jac)<1e-4
 return m.x.tolist()
def prepare():
 records=json.load(gzip.open(SOURCE,'rt'));rows=[];counts=[];skipped=0
 for record in records:
  for team in [record['input']['home_team'],record['input']['away_team']]:
   players=[p for p in record['input']['players']if p['team']==team];known=[(p,record['actual'].get(p['player_id']))for p in players];known=[(p,a)for p,a in known if a is not None]
   field=[(p,a)for p,a in known if not p['is_keeper']];gks=[(p,a)for p,a in known if p['is_keeper']]
   if sum(a['started']for p,a in field)!=10 or sum(a['started']for p,a in gks)!=1:skipped+=1;continue
   k=sum(not a['started'] and a['minutes']>0 for p,a in field);gkchange=any(not a['started']and a['minutes']>0 for p,a in gks)
   if k>5-int(gkchange):skipped+=1;continue
   counts.append({'season':record['season'],'k':k})
   for p,a in field:
    if a['minutes']is None or not 0<=a['minutes']<=90:continue
    # Do not treat an explicitly identified dismissal as an observed ordinary substitution.
    if a.get('fpl_red_cards',0)or a.get('straight_reds',0):continue
    rows.append({'season':record['season'],'pos':p['position'],'q':p['p_cameo_given_bench'],'s':p['start_minutes_mean'],'started':bool(a['started']),'cameo':bool(not a['started']and a['minutes']>0),'exit':bool(a['started']and 0<a['minutes']<90),'minutes':a['minutes']})
 return rows,counts,skipped

def train(rows,counts):
 model={'heads':{},'time':{},'count':None}
 for head in ['incoming','outgoing']:
  subset=[r for r in rows if r['started']==(head=='outgoing')];model['heads'][head]=fit_head(subset,head)
 for event in ['exit','cameo']:
  eligible=[r for r in rows if r[event]];pool=[r['minutes']for r in eligible]
  model['time'][event]={'pool':pool,'by_position':{pos:[r['minutes']for r in eligible if r['pos']==pos]for pos in ['DEF','MID','FWD']}}
 c=np.bincount([r['k']for r in counts],minlength=6)+.5;model['count']=(c/c.sum()).tolist();return model

def main():
 ROOT.mkdir(parents=True,exist_ok=True)
 (ROOT/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2));rows,counts,skipped=prepare();development=train([r for r in rows if r['season']=='2024-25'],[r for r in counts if r['season']=='2024-25']);validation={}
 for head in ['incoming','outgoing']:
  test=[r for r in rows if r['season']=='2025-26'and r['started']==(head=='outgoing')];y=np.array([r['cameo']if head=='incoming'else r['exit']for r in test]);p=expit(design(test,head)@development['heads'][head]);validation[head]={'n':len(test),'brier':float(np.mean((p-y)**2)),'predicted_rate':float(p.mean()),'observed_rate':float(y.mean())}
 model=train(rows,counts);model['source_sha256']=hashlib.sha256(SOURCE.read_bytes()).hexdigest();model['training']={'eligible_team_matches':len(counts),'eligible_player_rows':len(rows),'excluded_team_matches':skipped,'seasons':sorted({r['season']for r in rows})};model['conditional_head_validation']=validation
 (ROOT/'model.json').write_text(json.dumps(model,indent=2));print(json.dumps({'training':model['training'],'conditional_head_validation':validation,'count_pmf':model['count']},indent=2))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();SOURCE=args.source;ROOT=args.out;main()
