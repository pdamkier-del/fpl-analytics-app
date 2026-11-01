"""One bounded regularized fit, before either test window; no holdout search."""
import copy,json,gzip
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit,logsumexp
from precision_audit.dataset import load,dump
from test_separated_goal_head import decode
from b_precision_calibration import assist_features
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'analysis/results/b-precision-development-20261101';WORK=Path('/workspace/scratch/b-precision-development-20261101')

def fit_logistic(X,y,offset,bound,ridge=10.):
    X=np.array(X,float);y=np.array(y,float);offset=np.array(offset,float)
    def fun(b):
        z=offset+X@b;return float((np.logaddexp(0,z)-y*z).sum()+ridge*np.dot(b,b)/2)
    r=minimize(fun,np.zeros(X.shape[1]),method='L-BFGS-B',bounds=[(-bound,bound)]*X.shape[1]);assert r.success,r.message
    return dict(coef=r.x.tolist(),rows=len(y),ridge=ridge,bounds=[-bound,bound],loss=float(r.fun))

def main():
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    f=pd.read_csv(ROOT/'analysis/results/systematic-precision-audit-20261101/baseline-player-diagnostics.csv.gz',low_memory=False)
    h=pd.read_pickle('/workspace/scratch/precision-development-history.pkl');keys=['season','fixture_uuid','player_uuid'];h['training_label_known_at']=h.known_at.astype(str);needed=['training_label_known_at','return_prior_p','return_prior_s','return_prior_games','return_kind','rest_days']
    f=f.merge(h[keys+needed],on=keys,validate='one_to_one');f['baseline_xm']=f.analytic_minutes
    records=load(ROOT/'analysis/results/systematic-precision-audit-20261101/inputs/historical-inputs.json.gz');features={tuple(getattr(r,k)for k in keys):r._asdict()for r in f.itertuples()};train=[];allrows=[]
    for record in records:
        inp=decode(copy.deepcopy(record['input']))
        for p in inp.players:
            key=(record['season'],record['fixture_uuid'],p.player_id);m=features.get(key)
            if m is None:continue
            record['meta'][p.player_id].update({k:(None if pd.isna(m[k])else m[k])for k in needed+['baseline_xm','tactical_role']})
            row=(p,m);allrows.append(row)
            if record['season']=='2024-25'and 22<=record['gw']<=29 and pd.Timestamp(m['training_label_known_at'])<pd.Timestamp(f.loc[f.season.eq('2024-25')&f.gw.ge(30),'cutoff'].min()):train.append(row)
    # Conditional team-assist allocation, total team budget held fixed.
    groups={}
    for p,m in train:groups.setdefault((m['fixture_uuid'],m['team_id']),[]).append((p,m))
    def loss(b):
        total=5*np.dot(b,b)
        for rows in groups.values():
            X=np.array([assist_features(m,p)for p,m in rows]);offset=np.log([max(m['assists'],1e-7)for p,m in rows]);y=np.array([m['actual_assists']for p,m in rows]);z=offset+X@b;total-=y@(z-logsumexp(z))
        return float(total)
    opt=minimize(loss,np.zeros(5),method='L-BFGS-B',bounds=[(-np.log(2),np.log(2))]*5);assert opt.success,opt.message
    policy=dict(version='B-bounded-calibration-candidate-v1',training='2024-25 GW22-29, reused research diagnostics',training_latest_label=str(max(pd.Timestamp(m['training_label_known_at'])for _,m in train)),assist=dict(coef=opt.x.tolist(),rows=len(train),team_fixtures=len(groups),ridge=10.,max_weight_factor=2.,objective='conditional within-team FPL-assist multinomial; offset existing expected assists including minute exposure'))
    (OUT/'candidate-policy.json').write_text(json.dumps(policy,indent=2)+'\n');dump(WORK/'historical-inputs.json.gz',records)
    print(json.dumps(policy,indent=2),flush=True)
if __name__=='__main__':main()
