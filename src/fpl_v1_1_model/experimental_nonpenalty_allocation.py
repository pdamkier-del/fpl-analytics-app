"""Separate B ordinary-goal head, fitted only on nonpenalty xG.

Penalty occurrence, taker selection and conversion are independent inputs.
No ordinary-goal covariate is computed from penalty attempts or goals.
"""
import numpy as np
import pandas as pd
from .experimental_penalty_neutral import PenaltyNeutralState

FEATURES=['np_last_xg','np_recent3_xg']


def recent_features(neutral_history,target,cutoff):
    past=neutral_history[(pd.to_datetime(neutral_history.available_at,utc=True)<pd.Timestamp(cutoff))&neutral_history.minutes.gt(0)].sort_values(['kickoff_at','fixture_uuid','player_uuid'])
    by={p:g.tail(3) for p,g in past.groupby('player_uuid',sort=False)}
    rows=[]
    for r in target.itertuples():
        g=by.get(r.player_uuid);x=np.array([],float)if g is None else g.xg.to_numpy(float)
        rows.append(dict(fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,np_last_xg=float(x[-1])if len(x)else 0.,np_recent3_xg=float(np.average(x,weights=np.array([.25,.5,1.])[-len(x):]))if len(x)else 0.))
    return pd.DataFrame(rows)


def allocate(state,target,cutoff,season,model):
    _,rates=state.factors(target,cutoff,season)
    features=recent_features(state.neutral[state.neutral.season.eq(season)],target,cutoff)
    result=rates.merge(features,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    X=result[model['columns']].to_numpy(float)
    Z=(X-np.asarray(model['mean']))/np.asarray(model['scale'])
    result['ordinary_goal_weight']=np.maximum(result.nonpenalty_rate90.to_numpy(float),1e-12)*np.exp(np.clip(Z@np.asarray(model['coef']),-4,4))
    if not np.isfinite(result.ordinary_goal_weight).all():raise ValueError('Invalid nonpenalty goal weights')
    return result
