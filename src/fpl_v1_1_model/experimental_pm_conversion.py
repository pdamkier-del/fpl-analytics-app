"""Offline conversion/assist calibration candidates. Never imported by production."""
from dataclasses import replace
from contextlib import contextmanager
import inspect
import numpy as np
from scipy.special import xlogy,gammaln
from . import joint_simulator as simulator


def gamma_mean(events,exposure,tau,prior=1.):
    y,x,m=np.broadcast_arrays(np.asarray(events,float),np.asarray(exposure,float),np.asarray(prior,float))
    if not np.isfinite(y+x+m).all() or (y<0).any() or (x<0).any() or (m<=0).any() or not np.isfinite(tau) or tau<=0:raise ValueError('Invalid conversion evidence/prior')
    return (y+tau*m)/(x+tau)


def poisson_deviance(y,mu):
    y=np.asarray(y,float);mu=np.asarray(mu,float)
    if (y<0).any() or (mu<=0).any() or not np.isfinite(y+mu).all():raise ValueError('Invalid Poisson score')
    return 2*(xlogy(y,y/mu)-y+mu)


def event_weights(inp,goal_factor=None,assist_factor=None,change_total=False):
    """Relative conversion once; optional exposure-weighted ordinary-goal mass once.

    Penalty occurrence/conversion/taker parameters never change here. All-xG
    factors are effective calibration proxies, not identified NPG finishing.
    """
    goal_factor=goal_factor or {};assist_factor=assist_factor or {}
    players=[];multipliers={}
    for p in inp.players:
        g=float(goal_factor.get(p.player_id,1.));a=float(assist_factor.get(p.player_id,1.))
        if not np.isfinite(g+a) or min(g,a)<=0:raise ValueError('Invalid conversion multiplier')
        multipliers[p.player_id]=g
        players.append(replace(p,goal_weight=p.goal_weight*g,assist_weight=p.assist_weight*a))
    totals={}
    for team,lam,pen,conversion in [(inp.home_team,inp.lambda_home_goals,inp.lambda_home_penalties,inp.home_penalty_conversion),(inp.away_team,inp.lambda_away_goals,inp.lambda_away_penalties,inp.away_penalty_conversion)]:
        ps=[p for p in inp.players if p.team==team]
        exposure=np.array([(p.p_start*p.start_minutes_mean+(1-p.p_start)*p.p_cameo_given_bench*p.cameo_minutes_mean)/90 for p in ps])
        w=exposure*np.array([p.goal_weight for p in ps]);den=w.sum()
        factor=float(w@np.array([multipliers[p.player_id] for p in ps])/den) if den>0 else 1.
        # Same ordinary/penalty split as the unchanged production sampler.
        totals[team]=max(0.,lam-pen*conversion)*factor+min(lam,pen*conversion) if change_total else lam
    return replace(inp,players=tuple(players),lambda_home_goals=totals[inp.home_team],lambda_away_goals=totals[inp.away_team])


def independent_pair_probabilities(goal_weights,assist_weights):
    """Existing shared goal→assist event, conditional on active roster; no self assist."""
    g=np.asarray(goal_weights,float);a=np.asarray(assist_weights,float)
    if len(g)!=len(a) or not np.isfinite(g+a).all() or (g<0).any() or (a<0).any():raise ValueError('Invalid pair weights')
    if g.sum()<=0:return np.zeros((len(g),len(g)))
    g=g/g.sum();out=np.zeros((len(g),len(g)))
    for j in range(len(g)):
        w=a.copy();w[j]=0
        if w.sum()>0:out[:,j]=g[j]*w/w.sum()
    return out


def marginal_pair_probabilities(goal_weights,assist_weights,tolerance=1e-9,max_iter=500):
    """Max-entropy joint, fixed scorer and creator marginals, diagonal structural zero.

    No observed pair-specific skill is invented. Infeasible margins are rejected,
    never silently assigned to impossible self-assists.
    """
    g=np.asarray(goal_weights,float);a=np.asarray(assist_weights,float)
    if len(g)!=len(a) or not np.isfinite(g+a).all() or (g<0).any() or (a<0).any() or min(g.sum(),a.sum())<=0:raise ValueError('Missing joint marginal mass')
    g=g/g.sum();a=a/a.sum()
    if (g+a>1+tolerance).any():raise ValueError('Infeasible self-excluding joint marginals')
    q=np.outer(a,g);np.fill_diagonal(q,0.)
    for _ in range(max_iter):
        rs=q.sum(1);q*=np.divide(a,rs,out=np.zeros_like(a),where=rs>0)[:,None]
        cs=q.sum(0);q*=np.divide(g,cs,out=np.zeros_like(g),where=cs>0)[None,:]
        if max(abs(q.sum(1)-a).max(),abs(q.sum(0)-g).max())<tolerance:return q
    raise ValueError('Joint marginal solver did not converge')


@contextmanager
def shadow_joint_assists(enabled=True):
    """Only conditional ordinary-assist choice changes; goals/coin/points unchanged.

    The original sampler already couples assists to goals. This candidate tests
    whether enforcing intended assist marginals adds value. Sparse/infeasible
    active sets use the original legal choice and are counted, not concealed.
    """
    original=simulator._weighted_choice;diagnostics=dict(applied=0,fallback=0)
    cache={}
    def choose(rng,players,weights):
        caller=inspect.currentframe().f_back.f_locals
        if caller.get('cand') is not players or not caller.get('scorer'):return original(rng,players,weights)
        active=caller['active'];scorer=caller['scorer']
        key=tuple((p.player_id,p.goal_weight,p.assist_weight) for p in active)
        if key not in cache:
            try:cache[key]=marginal_pair_probabilities([p.goal_weight for p in active],[p.assist_weight for p in active])
            except ValueError:cache[key]=None
        q=cache[key]
        if q is None:diagnostics['fallback']+=1;return original(rng,players,weights)
        indices={p.player_id:i for i,p in enumerate(active)};j=indices[scorer.player_id]
        if q[:,j].sum()<=0:diagnostics['fallback']+=1;return original(rng,players,weights)
        diagnostics['applied']+=1
        return original(rng,players,[q[indices[p.player_id],j] for p in players])
    if enabled:simulator._weighted_choice=choose
    try:yield diagnostics
    finally:simulator._weighted_choice=original
