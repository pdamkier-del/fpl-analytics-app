from __future__ import annotations
import json, math, sqlite3
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data_v1_1/normalized/fpl_v1_1.sqlite3'
OUT=ROOT/'outputs/v1_1/phase5e_team_goal_candidates'; OUT.mkdir(parents=True,exist_ok=True)
FIT=json.loads((ROOT/'outputs/v1_1/phase3b_team_goals/team_goal_fit.json').read_text())['fit']
SEASONS=('2023-24','2024-25','2025-26')

def load():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 q=','.join('?'*len(SEASONS))
 return c.execute(f"select season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,gf,ga,xg,xga from team_fixture_observations where source_name='vaastav_historical_core' and season in ({q}) order by season,kickoff_at,fixture_uuid,was_home desc",SEASONS).fetchall()

def raw_features(rows,ha=13.,hd=20.,min_gw=6):
 da=2**(-1/ha); dd=2**(-1/hd); out=[]; by=defaultdict(list)
 for r in rows: by[r['season']].append(r)
 for season,rs in by.items():
  fixtures=defaultdict(list)
  for r in rs: fixtures[(r['kickoff_at'],r['fixture_uuid'])].append(r)
  att={};deff={};lg=0.;n=0
  for key in sorted(fixtures):
   cur=fixtures[key]
   for r in cur:
    t,o=r['team_id'],r['opponent_team_id']
    if int(r['gw'])<min_gw or t not in att or o not in deff or n==0: continue
    aw,gf,xg=att[t]; dw,ga,xga=deff[o]
    out.append(dict(season=season,gw=int(r['gw']),fixture_uuid=r['fixture_uuid'],team_id=t,opp=o,home=int(r['was_home']),y=float(r['gf']),gf=gf/aw,xg=xg/aw,ga=ga/dw,xga=xga/dw,lg=lg/n))
   for r in cur:
    t=r['team_id'];a=att.get(t,[0.,0.,0.]);d=deff.get(t,[0.,0.,0.]);a=[x*da for x in a];d=[x*dd for x in d]
    a[0]+=1;a[1]+=float(r['gf']);a[2]+=float(r['xg']);d[0]+=1;d[1]+=float(r['ga']);d[2]+=float(r['xga']);att[t]=a;deff[t]=d;lg+=float(r['gf']);n+=1
 return out

def base_lambda(rs):
 a=FIT['xg_weight_alpha'];b=FIT['xga_weight_beta'];it=FIT['intercept'];h=FIT['home_log_effect']
 return np.array([np.clip(math.exp(it+h*r['home'])*max(.05,a*r['xg']+(1-a)*r['gf'])*max(.05,b*r['xga']+(1-b)*r['ga'])/max(.3,r['lg']),.05,5) for r in rs])

def nll(l,y): return float(np.mean(l-y*np.log(np.maximum(l,1e-12))))
def met(l,y):
 e=l-y
 # Poisson randomized-free calibration summaries
 X=np.c_[np.ones(len(l)),np.log(np.maximum(l,1e-9))]
 def f(z):
  ll=np.exp(X@z); return np.mean(ll-y*np.log(ll))
 z=minimize(f,[0,1],method='BFGS').x
 return dict(n=len(y),nll=nll(l,y),mae=float(np.mean(abs(e))),rmse=float(np.sqrt(np.mean(e*e))),bias=float(np.mean(e)),mean_pred=float(np.mean(l)),mean_actual=float(np.mean(y)),cal_intercept=float(z[0]),cal_slope=float(z[1]),zero_pred=float(np.mean(np.exp(-l))),zero_actual=float(np.mean(y==0)))

def shrink_lambda(rs,z):
 # sA,sD in (0,1); intercept/home are refit, so this tests partial pooling not cosmetic holdout correction
 sA=1/(1+np.exp(-z[0])); sD=1/(1+np.exp(-z[1])); it,h=z[2],z[3]; a=FIT['xg_weight_alpha'];b=FIT['xga_weight_beta']
 vals=[]
 for r in rs:
  A=a*r['xg']+(1-a)*r['gf']; D=b*r['xga']+(1-b)*r['ga']; L=r['lg']
  A=L+sA*(A-L); D=L+sD*(D-L)
  vals.append(np.clip(math.exp(it+h*r['home'])*max(.05,A)*max(.05,D)/max(.3,L),.05,5))
 return np.array(vals)

def fit_shrink(train):
 y=np.array([r['y'] for r in train]); f=lambda z:nll(shrink_lambda(train,z),y)
 return minimize(f,[2,2,FIT['intercept'],FIT['home_log_effect']],method='L-BFGS-B',bounds=[(-6,6),(-6,6),(-.7,.7),(-.3,.5)]).x

def cal_lambda(rs,z):
 raw=base_lambda(rs); return np.clip(np.exp(z[0]+z[1]*np.log(raw)),.05,5)
def fit_cal(train):
 y=np.array([r['y'] for r in train]); return minimize(lambda z:nll(cal_lambda(train,z),y),[0,1],method='L-BFGS-B',bounds=[(-.7,.7),(.2,1.8)]).x

# Schedule-adjusted latent xG model, pre-GW refits. Uses xG response only; ridge partial pooling.
def latent_predict(rows, ridge=1.0, half_life=16.0, min_gw=6):
 by=defaultdict(list)
 for r in rows: by[r['season']].append(r)
 preds=[]
 for season,rs in by.items():
  teams=sorted({r['team_id'] for r in rs}); idx={t:i for i,t in enumerate(teams)}; T=len(teams)
  # group team-fixture rows by GW; all predictions in a GW use only prior GWs
  gws=sorted({int(r['gw']) for r in rs})
  history=[]
  prev=None
  for gw in gws:
   cur=[r for r in rs if int(r['gw'])==gw]
   if gw>=min_gw and history:
    # age measured in team-fixture rows' GW distance; exponential recency
    yy=np.array([float(r['xg']) for r in history]); home=np.array([int(r['was_home']) for r in history]); ti=np.array([idx[r['team_id']] for r in history]); oi=np.array([idx[r['opponent_team_id']] for r in history]); ages=np.array([max(0,gw-int(r['gw'])) for r in history]); w=2**(-ages/half_life)
    # params mu,home, attacks T-1, defences T-1; final effects = -sum for identifiability
    def unpack(z):
     aa=np.r_[z[2:2+T-1],-np.sum(z[2:2+T-1])]; dd=np.r_[z[2+T-1:2+2*(T-1)],-np.sum(z[2+T-1:2+2*(T-1)])]; return z[0],z[1],aa,dd
    def obj(z):
     mu,hh,aa,dd=unpack(z); eta=mu+hh*home+aa[ti]+dd[oi]; lam=np.exp(np.clip(eta,-4,3)); loss=np.sum(w*(lam-yy*eta))/np.sum(w); pen=ridge*(np.mean(aa*aa)+np.mean(dd*dd)); return loss+pen
    if prev is None or len(prev)!=2+2*(T-1): prev=np.zeros(2+2*(T-1)); prev[0]=math.log(max(.2,np.average(yy,weights=w)))
    opt=minimize(obj,prev,method='L-BFGS-B',options={'maxiter':120,'ftol':1e-9}); prev=opt.x
    mu,hh,aa,dd=unpack(prev)
    for r in cur:
     lam=float(np.clip(math.exp(mu+hh*int(r['was_home'])+aa[idx[r['team_id']]]+dd[idx[r['opponent_team_id']]]),.05,5))
     preds.append(dict(season=season,gw=gw,fixture_uuid=r['fixture_uuid'],team_id=r['team_id'],y=float(r['gf']),lam=lam))
   history.extend(cur)
 return preds

def main():
 rows=load(); feats=raw_features(rows)
 train=[r for r in feats if r['season']=='2023-24']; val=[r for r in feats if r['season']=='2024-25']; ev=[r for r in feats if r['season']=='2025-26']
 res={}
 for name,rs in [('train',train),('validation',val),('evaluation',ev)]: res.setdefault('raw',{})[name]=met(base_lambda(rs),np.array([r['y'] for r in rs]))
 zs=fit_shrink(train); zc=fit_cal(train)
 for key,z,fun in [('shrink',zs,shrink_lambda),('calibration',zc,cal_lambda)]:
  res[key]={'params':z.tolist()}
  if key=='shrink': res[key]['interpreted']={'attack_retention':float(1/(1+np.exp(-z[0]))),'defence_retention':float(1/(1+np.exp(-z[1]))),'intercept':float(z[2]),'home_log_effect':float(z[3]),'home_multiplier':float(math.exp(z[3]))}
  else: res[key]['interpreted']={'intercept':float(z[0]),'slope':float(z[1])}
  for name,rs in [('train',train),('validation',val),('evaluation',ev)]: res[key][name]=met(fun(rs,z),np.array([r['y'] for r in rs]))
 # latent: choose ridge from train->validation only; half-life fixed 16 to avoid half-life retune in this experiment
 latent_all={}
 for ridge in [0.05,0.1,0.25,0.5,1.0,2.0,4.0]:
  pp=latent_predict(rows,ridge=ridge,half_life=16.)
  mm={}
  for s,label in [('2023-24','train'),('2024-25','validation'),('2025-26','evaluation')]:
   p=[x for x in pp if x['season']==s];mm[label]=met(np.array([x['lam'] for x in p]),np.array([x['y'] for x in p]))
  latent_all[str(ridge)]=mm
 best=min(latent_all,key=lambda k:latent_all[k]['validation']['nll'])
 res['latent_schedule_adjusted']={'fixed_half_life':16.0,'ridge_grid':latent_all,'selected_ridge_on_validation':float(best),'train':latent_all[best]['train'],'validation':latent_all[best]['validation'],'evaluation':latent_all[best]['evaluation']}
 # persist selected latent team-fixture lambdas for downstream structural xPts test
 selected_preds=latent_predict(rows,ridge=float(best),half_life=16.)
 import csv
 with (OUT/'latent_selected_predictions.csv').open('w',newline='') as fh:
  ww=csv.DictWriter(fh,fieldnames=['season','gw','fixture_uuid','team_id','y','lam']); ww.writeheader(); ww.writerows(selected_preds)
 # select architecture by validation NLL only among candidates (raw has old params fitted on train+val, so not fair for selection); report rather than promote automatically
 cand={'shrink':res['shrink']['validation']['nll'],'calibration':res['calibration']['validation']['nll'],'latent':res['latent_schedule_adjusted']['validation']['nll']}
 res['selection_note']={'candidate_validation_nll':cand,'best_candidate':min(cand,key=cand.get),'warning':'Raw Phase3B parameters were originally fitted on 2023-24+2024-25, so its validation metric is not a clean train-only comparator. No production promotion is made here.'}
 (OUT/'candidate_results.json').write_text(json.dumps(res,indent=2)+'\n')
 print(json.dumps(res['selection_note'],indent=2));
 for k in ['raw','shrink','calibration','latent_schedule_adjusted']:
  print(k, 'VAL',res[k]['validation']['nll'],'EVAL',res[k]['evaluation']['nll'], 'eval bias',res[k]['evaluation']['bias'],'slope',res[k]['evaluation']['cal_slope'])
if __name__=='__main__': main()
