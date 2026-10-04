"""Original frozen keeper equations with common deadline state and explicit side."""
import numpy as np
import pandas as pd

from .keeper import SaveRateParams, forecast_fpl_save_mean


def keeper_saves_at_deadline(history, sides, cutoff, fit, *, season='2025-26'):
    """Return save means keyed by DEFENDING team, not source attacking team.

Each target side supplies fixture_uuid, team_id, opponent_team_id, was_home.
History supplies explicit available_at and source-definition team SOT counts.
"""
    cutoff=pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError('Timezone-aware cutoff required')
    if fit['selected_sot']['model']!='arithmetic' or fit['selected_save']['model']!='sot_only':
        raise ValueError('Original frozen keeper structures required')
    h=history.copy();r=sides.copy()
    if r.empty or r[['fixture_uuid','team_id']].duplicated().any():
        raise ValueError('Unique target sides required')
    h['available_at']=pd.to_datetime(h.available_at,utc=True,errors='raise')
    h['kickoff_at']=pd.to_datetime(h.kickoff_at,utc=True,errors='raise')
    if h.available_at.isna().any() or (h.available_at<h.kickoff_at).any():
        raise ValueError('Explicit valid SOT availability required')
    h=h[(h.available_at<=cutoff)&(h.season==season)].copy()
    if h[['fixture_uuid','team_id']].duplicated().any():
        raise ValueError('Deduplicated SOT history required')
    if set(h.fixture_uuid)&set(r.fixture_uuid):
        raise ValueError('Target SOT cannot enter keeper history')
    vals=h[['shots_on_target','shots_on_target_conceded']].to_numpy(float)
    if not np.isfinite(vals).all() or (vals<0).any():
        raise ValueError('Missing source SOT cannot be replaced with FPL events')
    h=h.sort_values(['kickoff_at','fixture_uuid','team_id'])
    groups={int(t):g for t,g in h.groupby('team_id')}
    protocol=fit['selection_protocol'];half=protocol['half_lives_fixed_not_tuned']
    sot=fit['selected_sot'];save=fit['selected_save']
    params=SaveRateParams(intercept=save['intercept'],sot_exponent=save['sot_exponent'],
        attacker_home_log_effect=save['attacker_home_log_effect'])
    def rate(g,event,hl):
        w=2.0**(-np.arange(len(g)-1,-1,-1)/hl)
        return float(np.dot(w,g[event])/w.sum())
    result=[]
    for s in r.itertuples(index=False):
        defending=int(s.team_id);attacking=int(s.opponent_team_id)
        if defending==attacking or s.was_home not in [0,1,False,True]:
            raise ValueError('Valid defending side/home flag required')
        a=groups.get(attacking,h.iloc[:0]);d=groups.get(defending,h.iloc[:0])
        if min(len(a),len(d))<protocol['min_history_matches']:
            raise ValueError('Insufficient source-definition SOT history')
        attack=rate(a,'shots_on_target',half['attack'])
        allow=rate(d,'shots_on_target_conceded',half['defence'])
        attacker_home=not bool(s.was_home)
        # Exact original experiment arithmetic, including its clipping bounds.
        mean=float(np.clip(np.exp(sot['intercept']+sot['attacker_home_log_effect']*attacker_home)*
            (sot['opponent_sot_for_weight']*attack+sot['team_sot_allowed_weight']*allow),.05,15))
        saves=float(np.clip(forecast_fpl_save_mean(mean,attacker_was_home=attacker_home,params=params),.01,12))
        result.append(dict(fixture_uuid=s.fixture_uuid,team_id=defending,attacking_team_id=attacking,
            cutoff=cutoff.isoformat(),lambda_source_sot=mean,lambda_saves=saves,
            history_latest_available_at=h.available_at.max().isoformat()))
    return pd.DataFrame(result)
