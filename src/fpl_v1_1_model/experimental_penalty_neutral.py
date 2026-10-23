"""Opt-in non-penalty scorer allocation; no production imports/default changes.

FPL-scale npxG is a count-based estimate: inclusive FPL xG minus 0.79 per
verified penalty attempt, not a claim of native provider-equivalent shot xG.
Both individual history and broad/soft-role priors use the same event boundary.
Existing predictive performance covariates/coefficients remain frozen.
"""
import math
import numpy as np
import pandas as pd
from .deadline_components import weighted_totals
from .attack import shrunk_rate_per90
from .role_event_priors import validate_roles, QCOLS, KEYS

PENALTY_XG = .79


def occurrence_probability(rate):
    if not math.isfinite(rate) or rate < 0:raise ValueError('Invalid penalty occurrence rate')
    return -math.expm1(-rate)


def remove_penalty_xg(history, attempts):
    """Exact identities required; unknown event coverage must be checked upstream.

    The event ledger contains all positive counts. Its absence represents zero
    only after the caller verifies complete match coverage (including misses).
    """
    key=['season','fixture_uuid','player_uuid']
    if history.duplicated(key).any() or attempts.duplicated(key).any():raise ValueError('Duplicate penalty/history identity')
    if not set(map(tuple,attempts[key].to_numpy())) <= set(map(tuple,history[key].to_numpy())):raise ValueError('Unmatched penalty event')
    if not np.isfinite(attempts.attempts).all() or (attempts.attempts<0).any() or (attempts.attempts%1!=0).any():raise ValueError('Invalid penalty count')
    result=history.merge(attempts[key+['attempts']],on=key,how='left',validate='one_to_one')
    count=result.attempts.fillna(0).to_numpy(float);xg=result.xg.to_numpy(float)
    if not np.isfinite(xg).all() or (xg<0).any():raise ValueError('Missing/invalid historical xG')
    residual=xg-PENALTY_XG*count
    # FPL exports are rounded to two decimals. Permit only that resolution;
    # incompatible event/source joins fail rather than being silently clipped.
    if (residual < -.0051).any():raise ValueError('Penalty xG exceeds observed FPL xG')
    result['inclusive_xg']=xg;result['xg']=np.maximum(0.,residual)
    return result.drop(columns='attempts')


def goal_role_priors(history,roles,target,cutoff):
    """The existing soft-role pooling equation, projected onto goal data only.

    Earlier seasons lack defensive-contribution observations. They are neither
    needed nor imputed here; only xG/minutes and predeadline role states enter.
    """
    validate_roles(roles);validate_roles(target)
    h=history.copy()
    cut=pd.Timestamp(cutoff)
    if (pd.to_datetime(h.available_at,utc=True)>=cut).any():raise ValueError('Future goal history')
    if (pd.to_datetime(target.cutoff,utc=True)>cut).any():raise ValueError('Future target role')
    if h[KEYS].duplicated().any():raise ValueError('Duplicate goal history')
    values=h[['minutes','xg']].to_numpy(float)
    if not np.isfinite(values).all()or(values<0).any():raise ValueError('Missing/invalid goal history')
    if (pd.to_datetime(h.available_at,utc=True)<pd.to_datetime(h.kickoff_at,utc=True)).any():raise ValueError('Goal history known before kickoff')
    h=h.merge(roles[KEYS+QCOLS+['cutoff']].rename(columns={'cutoff':'role_cutoff'}),on=KEYS,how='left',validate='one_to_one')
    if ((h[QCOLS].fillna(0).sum(axis=1)>0)&(pd.to_datetime(h.role_cutoff,utc=True)>pd.to_datetime(h.kickoff_at,utc=True))).any():raise ValueError('Historical role known after kickoff')
    h['pos']=h.fpl_position.replace({'GKP':'GK'});out={}
    target=target.copy();target['pos']=target.pos.replace({'GKP':'GK'})
    for pos,g in target.groupby('pos',sort=False):
        past=h[h.pos.eq(pos)];minutes=float(past.minutes.sum())
        if minutes<=0:raise ValueError('No historical goal prior exposure')
        broad=90*float(past.xg.sum())/minutes;q=past[QCOLS].fillna(0).to_numpy(float)
        byrole=90*(q.T@past.xg.to_numpy(float)+900*broad/90)/(q.T@past.minutes.to_numpy(float)+900)
        qt=g[QCOLS].fillna(0).to_numpy(float);mixed=np.where(qt.sum(axis=1)>0,qt@byrole,broad)
        out.update({(r.fixture_uuid,r.player_uuid):float(v)for r,v in zip(g.itertuples(),mixed)})
    return out


class PenaltyNeutralState:
    def __init__(self,history,attempts,historical_roles,attack):
        self.history=history.copy();self.neutral=remove_penalty_xg(history,attempts)
        self.roles=historical_roles.copy();self.attack=attack

    def factors(self,roster,cutoff,season):
        cut=pd.Timestamp(cutoff)
        if cut.tzinfo is None:raise ValueError('Timezone-aware penalty cutoff required')
        target=roster.copy();target['cutoff']=cut
        if target[KEYS].duplicated().any():raise ValueError('Duplicate penalty target')
        factors={};audit=[];priors=[]
        for history in [self.history,self.neutral]:
            past=history[history.season.eq(season)&pd.to_datetime(history.available_at,utc=True).lt(cut)].copy()
            if set(past.fixture_uuid)&set(target.fixture_uuid):raise ValueError('Target outcome in penalty history')
            past=past.sort_values(['kickoff_at','fixture_uuid','team_id','player_uuid'])
            prior=goal_role_priors(past,self.roles,target,cut)
            by={pid:g for pid,g in past.groupby('player_uuid',sort=False)};values={}
            p=self.attack['goal'];tau=p['current_season_position_prior_minutes_tau'];half=p['recency_half_life']
            for (fixture,player),rate in prior.items():
                num,den=weighted_totals(by.get(player,past.iloc[:0]),'xg',half)
                values[(fixture,player)]=shrunk_rate_per90(num,den,rate,tau)
            priors.append((values,prior))
        original,neutral=priors[0][0],priors[1][0]
        for key,old in original.items():
            new=neutral[key]
            if new<0 or new>old+1e-10:raise ValueError('Penalty removal increased goal rate')
            factor=new/old if old>0 else 1.
            factors[key]=factor
            audit.append(dict(fixture_uuid=key[0],player_uuid=key[1],inclusive_rate90=old,nonpenalty_rate90=new,ordinary_goal_factor=factor))
        return factors,pd.DataFrame(audit)


def conditional_penalty_conversion(inp, intervals, team):
    """Expected scored-penalty probability for the actual on-pitch taker law.

    Integrate the same official-rank/history fallback as the event sampler over
    every lineup interval. No extra RNG calls; inactive takers have zero mass.
    """
    players=[p for p in inp.players if p.team==team]
    edges=sorted({0,90,*[v for p in players for v in intervals[p.player_id]]})
    mean=0.
    for a,b in zip(edges,edges[1:]):
        if b<=a:continue
        active=[p for p in players if intervals[p.player_id][0]<=a and intervals[p.player_id][1]>=b]
        if inp.experimental_penalty_hierarchy:
            ranked=[p for p in active if p.penalty_order is not None and p.penalty_order>0]
            if ranked:active=[p for p in ranked if p.penalty_order==min(q.penalty_order for q in ranked)]
        weights=np.array([max(0.,p.penalty_weight)for p in active],float)
        if weights.sum()<=0:weights=np.array([max(0.,p.goal_weight)for p in active],float)
        if weights.sum()>0:
            conversion=np.array([min(1.,max(0.,p.penalty_conversion))for p in active])
            mean+=(b-a)/90*float(weights@conversion/weights.sum())
    return mean
