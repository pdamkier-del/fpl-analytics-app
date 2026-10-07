from __future__ import annotations
from collections import defaultdict
import math
import numpy as np
from scipy.optimize import minimize

def fit_team_latent(history,target,origin_gw,ridge=.25,half_life=16.):
    h=history.copy()
    teams=sorted(set(h.team_id.astype(int))|set(target.home_team_id.astype(int))|set(target.away_team_id.astype(int)))
    idx={t:i for i,t in enumerate(teams)};T=len(teams)
    yy=h.xg.to_numpy(float);home=h.was_home.astype(int).to_numpy()
    ti=np.array([idx[int(x)] for x in h.team_id]);oi=np.array([idx[int(x)] for x in h.opponent_team_id])
    ages=np.array([max(0,int(origin_gw)-int(x)) for x in h.gw],float);w=2**(-ages/half_life)
    def unpack(z):
        a=np.r_[z[2:2+T-1],-np.sum(z[2:2+T-1])]
        d=np.r_[z[2+T-1:2+2*(T-1)],-np.sum(z[2+T-1:2+2*(T-1)])]
        return z[0],z[1],a,d
    def obj(z):
        mu,hh,a,d=unpack(z);eta=mu+hh*home+a[ti]+d[oi]
        lam=np.exp(np.clip(eta,-4,3))
        return float(np.sum(w*(lam-yy*eta))/np.sum(w)+ridge*(np.mean(a*a)+np.mean(d*d)))
    z=np.zeros(2+2*(T-1));z[0]=math.log(max(.2,float(np.average(yy,weights=w))))
    z=minimize(obj,z,method='L-BFGS-B',options={'maxiter':160,'ftol':1e-9}).x
    mu,hh,a,d=unpack(z);out={}
    for r in target.itertuples(index=False):
        out[str(r.match_id)]=(
          float(np.clip(math.exp(mu+hh+a[idx[int(r.home_team_id)]]+d[idx[int(r.away_team_id)]]),.05,5)),
          float(np.clip(math.exp(mu+a[idx[int(r.away_team_id)]]+d[idx[int(r.home_team_id)]]),.05,5)))
    return out

def penalty_state(origin_gw,roster,pen_sides,pen,team_code_to_id,summary):
    half=float(summary['selected']['taker_half_life']);tau=float(summary['selected']['occurrence_tau'])
    tc=float(summary['selected']['conversion_tau']);decay=2**(-1/half)
    attempts=defaultdict(float);scored=defaultdict(float)
    for gw in range(1,int(origin_gw)):
        for k in list(attempts):attempts[k]*=decay;scored[k]*=decay
        for r in pen[pen.gw==gw].itertuples(index=False):
            attempts[str(r.player_uuid)]+=float(r.attempts);scored[str(r.player_uuid)]+=float(r.penalties_scored)
    past=pen[pen.gw<int(origin_gw)]
    league_conv=float(past.penalties_scored.sum()/past.attempts.sum()) if float(past.attempts.sum())>0 else .78
    ps={}
    for r in roster.itertuples(index=False):
        pid=str(r.player_uuid);a=attempts[pid];s=scored[pid]
        ps[pid]=(a,(s+tc*league_conv)/(a+tc))
    awarded=defaultdict(lambda:[0.,0.]);conceded=defaultdict(lambda:[0.,0.]);league=[0.,0.]
    for gw in sorted(int(x) for x in pen_sides.gw.unique() if int(x)<origin_gw):
        for r in pen_sides[pen_sides.gw==gw].itertuples(index=False):
            t=team_code_to_id.get(int(r.team_code));o=team_code_to_id.get(int(r.opp_code))
            if t is None or o is None:continue
            att=float(r.attempts);awarded[t][0]+=att;awarded[t][1]+=1
            conceded[o][0]+=att;conceded[o][1]+=1;league[0]+=att;league[1]+=1
    lg=league[0]/league[1] if league[1] else .12
    def lam(t,o):
        a,n=awarded[t];c,m=conceded[o]
        return max(1e-6,.5*((a+tau*lg)/(n+tau))+.5*((c+tau*lg)/(m+tau)))
    return ps,lam
