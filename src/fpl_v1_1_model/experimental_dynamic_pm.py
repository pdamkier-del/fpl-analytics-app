"""Offline reliability gates and a bridge to the EXISTING joint-XI sampler.

No production import. Weight w is player share, fixed before deadline. Contexts
are serial only and restore all patched functions even after exceptions.
"""
from contextlib import contextmanager
import inspect
import numpy as np
from scipy.optimize import minimize,nnls
from scipy.special import expit,logit
from . import joint_simulator as sim
from . import experimental_correctness_simulator as legal
from . import experimental_player_pm as player
from .experimental_survival_sampler import distribution

FEATURES=['log_minutes','coverage','relative_variance','new_fraction','club_fraction','role_fraction','lineup_change','stability','disagreement','return_proxy','lineup_missing','stability_missing']


@contextmanager
def shadow_legal_minutes(hazards=None,diagnostics=None):
    """Reuse legal.sample_intervals; keep original OG/CS/scoring in BOTH arms.

    With empirical-MM starter hazards, a draw of zero is clamped to one by
    the reused sampler's existing starter-duration rule. Count and disclose it.
    """
    saved_match=sim.simulate_match;saved_minutes=sim._sample_minutes
    diag=diagnostics if diagnostics is not None else {};state={};dists={str(k):distribution(v) for k,v in (hazards or {}).items() if v is not None}
    class DurationRng:
        def __init__(self,rng):self.rng=rng
        def __getattr__(self,k):return getattr(self.rng,k)
        def normal(self,mean,sd,*args,**kw):
            caller=inspect.currentframe().f_back;p=caller.f_locals.get('p')
            if caller.f_code is legal.sample_intervals.__code__ and sd==10. and p is not None and p.player_id in dists:
                value=int(self.rng.choice(91,p=dists[p.player_id]));diag['zero_duration_clamped']=diag.get('zero_duration_clamped',0)+int(value==0);return float(value)
            return self.rng.normal(mean,sd,*args,**kw)
    def minutes(rng,p):
        if 'intervals' not in state:
            inp=state['input'];trace={};intervals,starters=legal.sample_intervals(inp,DurationRng(rng),trace)
            for team in [inp.home_team,inp.away_team]:
                ps=[q for q in inp.players if q.team==team];chosen=[q for q in ps if q.player_id in starters]
                if len(chosen)!=11 or sum(legal.position(q)=='GK' for q in chosen)!=1:raise AssertionError('Illegal starting XI')
                changes=np.zeros(91);gk=np.zeros(91)
                for q in ps:
                    a,b=intervals[q.player_id]
                    if b>a:
                        changes[a]+=1;changes[b]-=1
                        if legal.position(q)=='GK':gk[a]+=1;gk[b]-=1
                    if q.p_start==0 and q.p_cameo_given_bench==0 and b>a:raise AssertionError('Hard unavailable player active')
                if np.cumsum(changes).max()>11 or np.cumsum(gk).max()>1:raise AssertionError('Overlapping lineup')
            diag['legal_draws']=diag.get('legal_draws',0)+1;diag['cameos_capped']=diag.get('cameos_capped',0)+trace['cameos_capped'];diag['cameos_rejected']=diag.get('cameos_rejected',0)+trace['cameos_rejected']
            state['intervals']=intervals
        a,b=state['intervals'][p.player_id];return b-a,a,b
    def match(inp,rng):
        state.clear();state['input']=inp
        return saved_match(inp,rng)
    try:
        sim._sample_minutes=minutes;sim.simulate_match=match
        yield diag
    finally:
        sim._sample_minutes=saved_minutes;sim.simulate_match=saved_match


@contextmanager
def shadow_team_weights(weights):
    """Reuse unchanged player formula with a different scalar h per team."""
    if not weights or any(not np.isfinite(v) or not 0<=v<=1 for v in weights.values()):raise ValueError('Invalid player weights')
    original=player.lineup_rates
    def rates(inp,spec,exposure):
        result={};individual={}
        # A uniform map is one base-function call, retaining float operations.
        if len(set(weights.values()))==1:return original(inp,dict(spec,anchor_weight=1-next(iter(weights.values()))),exposure)
        for team in [inp.home_team,inp.away_team]:
            r,i=original(inp,dict(spec,anchor_weight=1-weights[str(team)]),exposure);result[str(team)]=r[str(team)]
            individual.update({p.player_id:i[p.player_id] for p in inp.players if p.team==team})
        return result,individual
    try:
        player.lineup_rates=rates;yield
    finally:player.lineup_rates=original


def moment_weight(player_mse,team_mse,cross,prior=.75):
    """E[e^2] includes bias. Cross-moment is NOT assumed zero."""
    if min(player_mse,team_mse)<0 or not np.isfinite([player_mse,team_mse,cross]).all():raise ValueError('Bad error moments')
    bound=np.sqrt(player_mse*team_mse);cross=float(np.clip(cross,-bound,bound));den=player_mse+team_mse-2*cross
    return float(np.clip((team_mse-cross)/den,0,1)) if den>1e-12 else prior


def fit_gate(past,target,cfg):
    """All training outcomes must be known strictly before target.cutoff."""
    past=past[past.known<target.cutoff].copy()
    family=cfg['family'];k=float(cfg.get('k',1.))
    if family=='fixed':return .75,dict(training_rows=len(past))
    if family=='minutes':return float(target['amount_'+str(int(k))]),dict(training_rows=len(past))
    if family=='detailed':return float(target['detail_'+str(int(k))]),dict(training_rows=len(past))
    if family=='uncertainty':return float(1/(1+k*target.relative_variance)),dict(training_rows=len(past))
    if len(past)<40:return .75,dict(training_rows=len(past),fallback='Explicit warm-start prior, fewer than40 resolved sides')
    ep=past.player_xg.to_numpy()-past.xg.to_numpy();et=past.team_xg.to_numpy()-past.xg.to_numpy()
    info=dict(training_rows=len(past),max_known=str(past.known.max()),player_mse=float(np.mean(ep**2)),team_mse=float(np.mean(et**2)),error_cross=float(np.mean(ep*et)),residual_correlation=float(np.corrcoef(ep,et)[0,1]) if np.std(ep)>0 and np.std(et)>0 else None)
    if family=='covariance':
        ab=nnls(np.column_stack([np.ones(len(past)),past.profile_variance]),ep**2)[0]
        pmse=float(ab[0]+ab[1]*target.profile_variance);cross=info['error_cross']*k
        return moment_weight(pmse,info['team_mse'],cross),dict(info,variance_floor=float(ab[0]),variance_scale=float(ab[1]))
    if family!='learned':raise ValueError('Unknown reliability gate')
    x=past[FEATURES].to_numpy(float);center=x.mean(0);scale=x.std(0);scale[scale<1e-8]=1.;z=(x-center)/scale;new=(target[FEATURES].to_numpy(float)-center)/scale
    z=np.column_stack([np.ones(len(z)),z]);new=np.r_[1.,new]
    if cfg.get('hierarchical'):
        keys=list(dict.fromkeys(past.team_key));z=np.column_stack([z]+[past.team_key.eq(t).to_numpy(float) for t in keys]);new=np.r_[new,[float(target.team_key==t) for t in keys]]
    base=np.zeros(z.shape[1]);base[0]=logit(.75);d=past.player_xg.to_numpy()-past.team_xg.to_numpy();y=past.xg.to_numpy();t=past.team_xg.to_numpy();alpha=k/len(past)
    def objective(b):
        w=expit(z@b);err=t+w*d-y;dev=b-base
        return float(np.mean(err**2)+alpha*np.sum(dev**2)),2*z.T@(err*d*w*(1-w))/len(y)+2*alpha*dev
    result=minimize(objective,base,jac=True,method='L-BFGS-B',options={'maxiter':150,'ftol':1e-10})
    if not result.success:raise ValueError('Gate fit did not converge: '+result.message)
    return float(expit(new@result.x)),dict(info,coefficient_norm=float(np.linalg.norm(result.x-base)),team_effects=int(z.shape[1]-1-len(FEATURES)))
