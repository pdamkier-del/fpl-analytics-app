"""Opt-in B MM→PM→TS contract. No production entry point imports this module."""
from dataclasses import replace
import numpy as np
from scipy.special import ndtr
from fpl_v1_1_model.experimental_mean_preserving_minutes import normal_location

VERSION = 'B-MM-PM-TS-v1'
SCENARIOS = 'shared-PM-match-draws-v1'


def duration_pmf(mean, sigma):
    mean=float(mean)
    if mean<=1:
        mass=np.zeros(91);mass[1]=1.;return mass
    if mean>=90:
        mass=np.zeros(91);mass[90]=1.;return mass
    location=normal_location(mean,sigma)
    cdf=ndtr((np.arange(1,90)+.5-location)/sigma)
    return np.r_[0.,cdf[0],np.diff(cdf),1-cdf[-1]]


def field_marginals(player):
    p,q=player.p_start,player.p_cameo_given_bench
    mass=p*duration_pmf(player.start_minutes_mean,10.)+(1-p)*q*duration_pmf(player.cameo_minutes_mean,7.)
    mass[0]+=(1-p)*(1-q)
    return mass


def prepare_match(inp, catalogue=None):
    """Official ranks affect only takers actually on the pitch at the event.

    Missing ranks retain the frozen historical-attempt fallback. They do not
    create invented equal-choice competitors. A tied published rank retains
    historical relative weights. Historical callers must supply a pre-cutoff
    catalogue or omit ranks entirely; today's roles cannot be replayed backward.
    """
    catalogue=catalogue or {}
    players=[]
    for p in inp.players:
        raw=catalogue.get(p.player_id,{}).get('penalties_order')
        order=int(raw) if isinstance(raw,(int,float)) and np.isfinite(raw) and raw>0 and raw==int(raw) else None
        players.append(replace(p,penalty_order=order,
            penalty_weight=max(p.penalty_weight,1e-12) if order else p.penalty_weight))
    return replace(inp,players=tuple(players),experimental_mean_preserving_minutes=True,
                   experimental_penalty_hierarchy=bool(catalogue))


def validate_forecast(f):
    if f.get('model')!=VERSION or f.get('scope')!='prospective_preview' or f.get('locked_model_active') is not False:
        raise ValueError('Invalid unified B chain contract')
    audit=f.get('minute_sampler_audit',{})
    if audit.get('sampler')!=VERSION or not audit.get('all_MM_to_PM_means_consistent'):
        raise ValueError('Missing unified minute contract')
    n=f.get('scenario_contract',{}).get('draws')
    if f.get('scenario_contract',{}).get('version')!=SCENARIOS or not isinstance(n,int) or n<1:
        raise ValueError('Missing shared PM scenarios')
    for p in f['players']:
        if sorted(w['gw'] for w in p['weeks'])!=sorted(f['gws']):
            raise ValueError('Incomplete unified horizon')
        for w in p['weeks']:
            samples=w.get('scenarios',{})
            pts=np.asarray(samples.get('points',[]),float)
            mins=np.asarray(samples.get('minutes',[]),float)
            if pts.shape!=(n,) or mins.shape!=(n,) or not np.isfinite(pts).all() or not np.isfinite(mins).all():
                raise ValueError('Missing or invalid aligned PM scenarios')
            if (mins<0).any() or (mins>90*len(w['fixtures'])).any() or ((mins==0)&(pts!=0)).any():
                raise ValueError('Invalid PM appearance/scoring scenario')
            if abs(pts.mean()-w['xpts'])>1e-9:
                raise ValueError('TS scenarios do not reproduce PM xP')
            if abs(w['xmins']-w['pm_analytic_minutes'])>1e-7:
                raise ValueError('MM/PM week mean mismatch')
            if any(abs(x['xmins']-x['pm_analytic_minutes'])>1e-7 for x in w['fixtures']):
                raise ValueError('MM/PM fixture mean mismatch')
    return True
