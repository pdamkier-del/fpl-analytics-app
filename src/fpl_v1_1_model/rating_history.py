"""Cutoff-safe external match-rating features for MM v2.

Expected input ledger (one row per provider/player/match):
    provider, player_uuid, match_id, available_at, rating
Optional:
    role, minutes, competition

Ratings are never used from the target match.  Features are computed only from
rows with available_at < forecast cutoff.

Provider raw ratings are normalized before entering selection math.  We use
player-relative recency plus role-relative z-scores so a 7.0 at CB is not
implicitly treated as identical evidence to a 7.0 at CAM.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

REQUIRED=('provider','player_uuid','match_id','available_at','rating')


def validate_rating_ledger(frame:pd.DataFrame)->pd.DataFrame:
    missing=[c for c in REQUIRED if c not in frame.columns]
    if missing:
        raise ValueError('Missing rating columns: '+','.join(missing))
    x=frame.copy()
    x['provider']=x.provider.astype(str).str.lower().str.strip()
    x['player_uuid']=x.player_uuid.astype(str)
    x['match_id']=x.match_id.astype(str)
    x['available_at']=pd.to_datetime(x.available_at,utc=True,errors='raise')
    x['rating']=pd.to_numeric(x.rating,errors='raise')
    if x.available_at.isna().any() or not np.isfinite(x.rating).all():
        raise ValueError('Invalid rating ledger')
    if ((x.rating<0)|(x.rating>10)).any():
        raise ValueError('Ratings must be on provider 0-10 scale')
    if x.duplicated(['provider','player_uuid','match_id']).any():
        raise ValueError('Duplicate provider/player/match rating')
    if 'role' not in x:
        x['role']='UNKNOWN'
    x['role']=x.role.fillna('UNKNOWN').astype(str)
    if 'minutes' not in x:
        x['minutes']=np.nan
    return x.sort_values(['player_uuid','available_at','match_id','provider']).reset_index(drop=True)


def combine_providers(frame:pd.DataFrame)->pd.DataFrame:
    """Collapse multiple providers to one player-match rating without leakage.

    Providers are equally weighted initially.  This can later be learned on
    independent data, but must not be tuned on the reused diagnostic.
    """
    x=validate_rating_ledger(frame)
    keys=['player_uuid','match_id']
    agg=x.groupby(keys,as_index=False).agg(
        available_at=('available_at','max'),
        rating=('rating','mean'),
        role=('role',lambda s: next((v for v in s if v!='UNKNOWN'),'UNKNOWN')),
        minutes=('minutes','mean'),
        provider_count=('provider','nunique'),
    )
    return agg.sort_values(['player_uuid','available_at','match_id']).reset_index(drop=True)


def _weighted(values):
    values=np.asarray(values,float)
    if not len(values):
        return np.nan
    w=2.0**np.arange(len(values)-1,-1,-1,dtype=float)
    w=w[::-1]  # newest highest after chronological input? corrected below
    # explicit chronological oldest->newest weights
    w=np.array([0.125,0.25,0.5,1.0])[-len(values):]
    return float(np.average(values,weights=w))


def build_rating_features(targets:pd.DataFrame,ledger:pd.DataFrame,*,lookback_matches:int=4,
                          long_lookback_matches:int=12,role_reference_matches:int=200,
                          min_role_reference:int=20)->pd.DataFrame:
    """Attach cutoff-safe recent rating features to target player-fixture rows.

    targets requires player_uuid and cutoff, and may include expected_role.
    Returned performance_score is in [0,1], centered at 0.5.  It combines:
    - recent weighted raw rating;
    - player rating trend;
    - role-relative historical z-score where enough reference exists.
    """
    x=combine_providers(ledger)
    if 'player_uuid' not in targets or 'cutoff' not in targets:
        raise ValueError('targets require player_uuid and cutoff')
    hist={pid:g for pid,g in x.groupby('player_uuid',sort=False)}
    rows=[]
    for r in targets.itertuples(index=False):
        cutoff=pd.to_datetime(getattr(r,'cutoff'),utc=True)
        pid=str(getattr(r,'player_uuid'))
        g=hist.get(pid)
        all_past=x.iloc[0:0] if g is None else g[g.available_at<cutoff]
        past=all_past.tail(lookback_matches)
        long_past=all_past.tail(long_lookback_matches)
        vals=past.rating.to_numpy(float)
        recent=_weighted(vals)
        last=float(vals[-1]) if len(vals) else np.nan
        prev=_weighted(vals[:-1]) if len(vals)>1 else np.nan
        trend=(last-prev) if np.isfinite(last) and np.isfinite(prev) else 0.0
        long_vals=long_past.rating.to_numpy(float)
        long_mean=float(np.mean(long_vals)) if len(long_vals) else np.nan
        self_delta=(recent-long_mean) if np.isfinite(recent) and np.isfinite(long_mean) else 0.0

        role=str(getattr(r,'expected_role','UNKNOWN') or 'UNKNOWN')
        ref=x[(x.available_at<cutoff)&(x.role==role)] if role!='UNKNOWN' else x.iloc[0:0]
        ref=ref.tail(role_reference_matches)
        if len(ref)>=min_role_reference and float(ref.rating.std(ddof=0))>1e-8 and np.isfinite(recent):
            role_z=(recent-float(ref.rating.mean()))/float(ref.rating.std(ddof=0))
        else:
            role_z=0.0

        # Stable monotonic 0-1 score. Raw 6.5 ~= neutral, one rating point is
        # meaningful but not allowed to dominate hierarchy on its own.
        raw_component=0.0 if not np.isfinite(recent) else (recent-6.5)
        latent=.65*raw_component+.25*role_z+.10*trend
        score=float(1/(1+np.exp(-latent)))
        rows.append({
            'rating_hist_n':int(len(past)),
            'rating_recent':float(recent) if np.isfinite(recent) else 0.0,
            'rating_last':float(last) if np.isfinite(last) else 0.0,
            'rating_trend':float(trend),
            'rating_long_mean':float(long_mean) if np.isfinite(long_mean) else 0.0,
            'rating_self_delta':float(self_delta),
            'rating_role_z':float(role_z),
            'performance_score':score if len(past) else 0.5,
            'rating_provider_matches':int(past.provider_count.sum()) if len(past) else 0,
        })
    out=targets.reset_index(drop=True).copy()
    feat=pd.DataFrame(rows)
    for c in feat:
        out[c]=feat[c].to_numpy()
    return out
