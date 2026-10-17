"""Current-origin implementation of PR9's existing prior-only NUM contract.

Normal role and durations are inputs from the original PR4/PR8 upstream, not
invented here. Unknown historical health never becomes healthy by default.
Actual labels are accepted only in strictly prior observations, not targets.
"""
import numpy as np
import pandas as pd
from scipy.special import logit
from research_individual_mm_refinement import NUM

KEY=['season','fixture_uuid','player_uuid']
FORBIDDEN={'y','minutes','started','observed_minutes','outcome_known_at','actual_formation'}


def prior_features(target,observations,previous_forecasts):
    if FORBIDDEN & set(target):raise ValueError('Target outcomes forbidden')
    if target.empty or target.cutoff.nunique()!=1:raise ValueError('One target cutoff required')
    if target.duplicated(KEY).any():raise ValueError('Duplicate target')
    f=target.copy().reset_index(drop=True)
    cut=pd.Timestamp(f.cutoff.iloc[0])
    if cut.tzinfo is None:raise ValueError('Timezone required')
    h=observations.copy()
    for c in ['known_at','kickoff_at']:h[c]=pd.to_datetime(h[c],utc=True,format='mixed')
    if h.duplicated(KEY).any():raise ValueError('Duplicate historical observation')
    if set(map(tuple,h[KEY].to_numpy())) & set(map(tuple,f[KEY].to_numpy())):
        raise ValueError('Target fixture outcome in feature history')
    # Later records are safely filtered; they never affect target features.
    h=h[h.known_at.lt(cut)].copy()
    if (h.kickoff_at.ge(cut)).any():raise ValueError('Historical kickoff in future')
    old=previous_forecasts.copy()
    if len(old):
        old['cutoff']=pd.to_datetime(old.cutoff,utc=True,format='mixed')
        old=old[old.cutoff.lt(cut)&old.news_eligible&old.news_state.isin(['AVAILABLE','RETURNED_AVAILABLE'])]
    histories={(s,p,int(t)):g.sort_values(['known_at','fixture_uuid']) for (s,p,t),g in h.groupby(['season','player_uuid','team_id'])}
    physical={(s,p):g.sort_values(['known_at','fixture_uuid']) for (s,p),g in h.groupby(['season','player_uuid'])}
    teamhist={(s,int(t)):g[['fixture_uuid','kickoff_at','known_at']].drop_duplicates().sort_values('known_at') for (s,t),g in h.groupby(['season','team_id'])}
    previous={(s,p,int(t)):g.sort_values(['cutoff','fixture_uuid']) for (s,p,t),g in old.groupby(['season','player_uuid','team_id'])} if len(old) else {}
    features=[]
    for r in f.itertuples():
        key=(r.season,r.player_uuid,int(r.team_id));past=histories.get(key,h.iloc[:0])
        av=past[past.role_available.eq(True)]
        starts=av[av.started.eq(1)];cameos=av[av.started.eq(0)&av.minutes.gt(0)]
        weights=np.exp2(-(cut-av.known_at).dt.total_seconds().to_numpy()/86400/180)
        normal=float(r.normal_role_p) if pd.notna(r.normal_role_p) else float(r.p_role)
        stable=(8*normal+float(weights@av.started.to_numpy()))/(8+weights.sum())
        def sums(g):
            w=np.exp2(-(cut-g.known_at).dt.total_seconds().to_numpy()/86400/180)
            return float(w.sum()),float(w@g.minutes.to_numpy()/w.sum()) if w.sum() else np.nan
        sn,sm=sums(starts);cn,cm=sums(cameos)
        latest=av.iloc[-1] if len(av) else None
        oldrows=previous.get(key);prev=oldrows.iloc[-1] if oldrows is not None and len(oldrows) else None
        allpast=physical.get((r.season,r.player_uuid),h.iloc[:0]);played=allpast[allpast.minutes.gt(0)]
        team=teamhist.get((r.season,int(r.team_id)),h.iloc[:0]);last6=past.tail(6)
        role='regular' if len(last6)>=6 and last6.started.eq(1).all() else 'reserve' if len(last6)>=3 and last6.started.mean()<=.2 else 'rotation_or_short_history'
        features.append(dict(logit_p=float(logit(np.clip(r.p,1e-6,1-1e-6))),logit_q=float(logit(np.clip(r.q,1e-6,1-1e-6))),
            normal_p=normal,stable_p=stable,history_n=float(weights.sum()),start_n=sn,cameo_n=cn,starter_mean=sm,cameo_mean=cm,
            last_start_minutes=float(starts.minutes.iloc[-1]) if len(starts) else np.nan,
            last_started=float(latest.started) if latest is not None else np.nan,
            rest_days=(cut-played.kickoff_at.iloc[-1]).total_seconds()/86400 if len(played) else np.nan,
            team_rest_days=(cut-team.kickoff_at.iloc[-1]).total_seconds()/86400 if len(team) else np.nan,
            minutes_7d=float(allpast.loc[allpast.kickoff_at.gt(cut-pd.Timedelta(days=7)),'minutes'].sum()),
            minutes_14d=float(allpast.loc[allpast.kickoff_at.gt(cut-pd.Timedelta(days=14)),'minutes'].sum()),
            role_jump=normal-float(prev.p) if prev is not None else 0.,prior_type=role,
            max_history_known_at=past.known_at.max() if len(past) else pd.NaT,
            physical_last_known_at=allpast.known_at.max() if len(allpast) else pd.NaT))
    extra=pd.DataFrame(features)
    f=f.drop(columns=[c for c in extra if c in f])
    f=pd.concat([f,extra],axis=1)
    if set(NUM)-set(f):raise ValueError('Incomplete PR9 feature contract')
    return f
