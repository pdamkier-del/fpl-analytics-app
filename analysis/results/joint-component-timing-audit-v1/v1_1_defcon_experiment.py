"""Phase 3D.2: defensive-contribution model using 2025/26 fixture data.

DC exists fixture-by-fixture only from 2025/26 in Historical Core.  Therefore
this is an explicitly weaker temporal validation than xMins/team/player attack:
GW6-21 fit the count model and GW22-38 are a later validation block.

Mean DC count = current-season player DC/90 (recency + position shrinkage)
              * xMins/90
              * opponent-induced-DC factor ** gamma.
A negative-binomial count distribution converts the mean to the official
position threshold probability. No previous-season DC data are used.
"""
from __future__ import annotations
import argparse,csv,json,math,sqlite3
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from fpl_v1_1_model.defcon import nb2_logpmf,threshold_probability
from fpl_v1_1_model.evaluation import binary_metrics,regression_metrics

SEASON='2025-26'; FIT_GW=(6,21); VAL_GW=(22,38); POS=('DEF','MID','FWD')

def load(db):
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row
    return c.execute("""select season,gw,fixture_uuid,player_uuid,team_id,opponent_team_id,kickoff_at,fpl_position,started,minutes,defcon_count,defcon_points
      from player_fixture_observations where season=? and fpl_position in ('DEF','MID','FWD')
      order by kickoff_at,fixture_uuid,team_id,player_uuid""",(SEASON,)).fetchall()

def sigmoid(x):return 1/(1+math.exp(-x))

def xmins_context(rows,minfit,preg):
    hr=float(minfit['role_half_life']);hd=float(minfit['duration_half_life']);ar=2**(-1/hr);ad=2**(-1/hd);aa=float(preg['selected']['intercept']);bb=float(preg['selected']['slope']);state={};out={};fixtures=defaultdict(list)
    for r in rows:fixtures[(r['kickoff_at'],r['fixture_uuid'])].append(r)
    for key in sorted(fixtures):
        cur=fixtures[key]
        for r in cur:
            s=state.get(r['player_uuid'],[0.]*8);sw,ss,nw,cc,dw,dm,cw,cm=s
            if int(r['gw'])>=6 and sw>0:
                ps=min(1-1e-6,max(1e-6,ss/sw));ps=1/(1+math.exp(-(aa+bb*math.log(ps/(1-ps)))));pc=cc/nw if nw else .20;sm=dm/dw if dw else 78.;cameo=cm/cw if cw else 16.;out[(r['fixture_uuid'],r['player_uuid'])]=ps*sm+(1-ps)*pc*cameo
        for r in cur:
            s=state.get(r['player_uuid'],[0.]*8);sw,ss,nw,cc,dw,dm,cw,cm=s;sw*=ar;ss*=ar;nw*=ar;cc*=ar;dw*=ad;dm*=ad;cw*=ad;cm*=ad;st=int(r['started'] or 0);m=float(r['minutes'] or 0);sw+=1;ss+=st
            if not st:nw+=1;cc+=float(m>0)
            if st:dw+=1;dm+=m
            elif m>0:cw+=1;cm+=m
            state[r['player_uuid']]=[sw,ss,nw,cc,dw,dm,cw,cm]
    return out

def build_base(rows,xmins,h_player,h_opp):
    dp=2**(-1/h_player);do=2**(-1/h_opp);pstate={};ostate={};pos_tot=defaultdict(lambda:[0.,0.]);league_ind=defaultdict(lambda:[0.,0.]);rec=[];fixtures=defaultdict(list)
    for r in rows:fixtures[(r['kickoff_at'],r['fixture_uuid'])].append(r)
    for key in sorted(fixtures):
        cur=fixtures[key]
        for r in cur:
            if int(r['gw'])<6:continue
            xm=xmins.get((r['fixture_uuid'],r['player_uuid']))
            if xm is None:continue
            pos=r['fpl_position'];ps=pstate.get(r['player_uuid'],[0.,0.]);prior=90*pos_tot[pos][0]/pos_tot[pos][1] if pos_tot[pos][1]>0 else 0.
            os=ostate.get((int(r['opponent_team_id']),pos),[0.,0.]);li=league_ind[pos];opp=os[1]/os[0] if os[0]>0 else (li[0]/li[1] if li[1]>0 else 1.);league=li[0]/li[1] if li[1]>0 else max(opp,1.);factor=max(.25,min(4.,opp/max(.1,league)))
            rec.append((int(r['gw']),r['fixture_uuid'],r['player_uuid'],pos,float(r['defcon_count'] or 0),float(r['defcon_points'] or 0),float(xm),ps[0],ps[1],prior,factor))
        # decay player states once per player's fixture, opponent states once per team fixture
        for r in cur:
            pid=r['player_uuid'];a,b=pstate.get(pid,[0.,0.]);a*=dp;b*=dp;m=float(r['minutes'] or 0);a+=float(r['defcon_count'] or 0);b+=m;pstate[pid]=[a,b];pt=pos_tot[r['fpl_position']];pt[0]+=float(r['defcon_count'] or 0);pt[1]+=m
        # aggregate each team side by position; that total was induced by its opponent
        side=defaultdict(float); opponents={}
        for r in cur:
            side[(int(r['team_id']),r['fpl_position'])]+=float(r['defcon_count'] or 0);opponents[int(r['team_id'])]=int(r['opponent_team_id'])
        for (team,pos),tot in side.items():
            opp=opponents[team];w,v=ostate.get((opp,pos),[0.,0.]);w=w*do+1.;v=v*do+tot;ostate[(opp,pos)]=[w,v];li=league_ind[pos];li[0]+=tot;li[1]+=1
    return rec

def mu_from(rec,tau,gamma):
    mu=[]
    for gw,fix,pid,pos,y,pts,xm,we,wm,prior,factor in rec:
        rate=90*(we+tau*prior/90)/(wm+tau) if wm+tau>0 else prior
        mu.append(max(1e-8,xm/90*rate*(factor**gamma)))
    return np.asarray(mu)

def masks(rec):
    gw=np.asarray([r[0] for r in rec]);return (gw>=FIT_GW[0])&(gw<=FIT_GW[1]),(gw>=VAL_GW[0])&(gw<=VAL_GW[1])

def fit_for_half_lives(rows,xmins,hp,ho):
    rec=build_base(rows,xmins,hp,ho);fit,_=masks(rec);y=np.asarray([r[4] for r in rec],float);pos=np.asarray([r[3] for r in rec]);fit=np.asarray(fit,bool)
    def obj(z):
        tau=math.exp(z[0]);gamma=1.5*sigmoid(z[1]);avec=np.where(pos=='DEF',math.exp(z[2]),np.where(pos=='MID',math.exp(z[3]),math.exp(z[4])));mu=mu_from(rec,tau,gamma);yy=y[fit];mm=mu[fit];aa=avec[fit];rr=1/aa;pp=rr/(rr+mm);ll=gammaln(yy+rr)-gammaln(rr)-gammaln(yy+1)+rr*np.log(pp)+yy*np.log1p(-pp);return -float(np.mean(ll))
    r=minimize(obj,[math.log(300),0,math.log(.15),math.log(.15),math.log(.15)],method='L-BFGS-B',bounds=[(math.log(20),math.log(2000)),(-5,5),(math.log(.005),math.log(2)),(math.log(.005),math.log(2)),(math.log(.005),math.log(2))],options={'maxiter':65,'ftol':1e-9});tau=math.exp(r.x[0]);gamma=1.5*sigmoid(r.x[1]);alphas={'DEF':math.exp(r.x[2]),'MID':math.exp(r.x[3]),'FWD':math.exp(r.x[4])};return float(r.fun),rec,tau,gamma,alphas

def evaluate(rec,tau,gamma,alphas,mask):
    y=np.asarray([r[4] for r in rec],int);pos=np.asarray([r[3] for r in rec]);pts=np.asarray([r[5] for r in rec]);mu=mu_from(rec,tau,gamma);prob=np.asarray([threshold_probability(float(m),p,alphas[p]) for m,p in zip(mu,pos)]);actual=(pts>0).astype(int);sel=np.asarray(mask,bool);bm=binary_metrics(actual[sel],prob[sel]).as_dict();rm=regression_metrics(y[sel],mu[sel]).as_dict();pm=regression_metrics(pts[sel],2*prob[sel]).as_dict();bm.update({'mean_pred':float(prob[sel].mean()),'event_rate':float(actual[sel].mean())});return {'count':rm,'threshold_probability':bm,'expected_dc_points':pm},mu,prob

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',type=Path,default=Path('data_v1_1/normalized/fpl_v1_1.sqlite3'));ap.add_argument('--minutes-fit',type=Path,default=Path('outputs/v1_1/phase3a_minutes/continuous_half_life_fit.json'));ap.add_argument('--pstart-fit',type=Path,default=Path('outputs/v1_1/phase3a_minutes/pstart_regularization.json'));ap.add_argument('--out',type=Path,default=Path('outputs/v1_1/phase3d_defcon'));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rows=load(a.db);minfit=json.loads(a.minutes_fit.read_text());preg=json.loads(a.pstart_fit.read_text());xm=xmins_context(rows,minfit,preg)
    # Coarse half-life search on the early-season fit block only; no validation-GW selection.
    candidates=[]
    for hp in (2.,6.,16.,40.):
        for ho in (2.,6.,16.,40.):
            loss,rec,tau,gamma,alphas=fit_for_half_lives(rows,xm,hp,ho);candidates.append((loss,hp,ho,rec,tau,gamma,alphas))
    best=min(candidates,key=lambda x:x[0]);loss,hp,ho,rec,tau,gamma,alphas=best;fit,val=masks(rec);fm,_,_=evaluate(rec,tau,gamma,alphas,fit);vm,mu,prob=evaluate(rec,tau,gamma,alphas,val)
    # Ablation: same selected player model but neutral opponent factor.
    neutral=evaluate(rec,tau,0.0,alphas,val)[0]
    # Poisson distribution ablation (same mean model).
    pois=evaluate(rec,tau,gamma,{'DEF':0.,'MID':0.,'FWD':0.},val)[0]
    result={'data_limit':'Historical fixture DC exists only for 2025/26, so this uses an internal temporal split rather than a separate season holdout.','fit_gws':list(FIT_GW),'validation_gws':list(VAL_GW),'selected':{'player_dc_half_life':hp,'opponent_induced_half_life':ho,'position_prior_minutes_tau':tau,'opponent_factor_exponent_gamma':gamma,'nb2_dispersion_alpha':alphas,'fit_nb_nll':loss},'fit_metrics':fm,'validation_metrics':vm,'validation_ablations':{'no_opponent_factor':neutral,'poisson_instead_of_negative_binomial':pois},'candidate_grid':[{'fit_nb_nll':x[0],'player_h':x[1],'opponent_h':x[2]} for x in sorted(candidates,key=lambda x:x[0])],'notes':['Official 2026/27 thresholds are DEF CBIT>=10 and MID/FWD CBIRT>=12, worth 2 points and capped at 2.','No previous-season DC values are used because the metric was introduced in 2025/26.','Opponent factor is position-specific: how many relevant DC actions that opponent has induced from opposing DEF/MID/FWD units relative to the league rate.','Parameters remain candidates until 2026/27 provides a genuinely later validation sample.']}
    (a.out/'defcon_fit.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.out/'defcon_validation_predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['gw','fixture_uuid','player_uuid','position','actual_dc_count','actual_dc_points','xmins','mu_dc','p_dc_points']);
        for r,m,p,k in zip(rec,mu,prob,val):
            if k:w.writerow([r[0],r[1],r[2],r[3],r[4],r[5],r[6],m,p])
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
