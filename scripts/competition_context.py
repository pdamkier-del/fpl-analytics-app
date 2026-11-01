"""Observed competition context; no inferred injury/rest reason or probability boost.

Physical load follows player identity across clubs; role evidence stays at the
current club. Missing games/minutes cannot prove rest or complete coverage.
"""
import numpy as np
import pandas as pd

KEY=['season','fixture_uuid','player_uuid']


def context_features(target,events):
    required={'season','player_uuid','club','match_id','kickoff','known_at','competition','minutes','started'}
    if required-set(events):raise ValueError('Incomplete competition event contract')
    needed={'season','player_uuid','club','cutoff'}
    if needed-set(target):raise ValueError('Incomplete target identity/cutoff')
    if {'y','minutes','started','actual_minutes','actual_start'}&set(target):raise ValueError('Target outcomes forbidden')
    e=events.copy();e=e[e.player_uuid.notna()].copy()
    for c in ['kickoff','known_at']:
        # Reject naive clocks instead of assuming UTC.
        if any(pd.Timestamp(v).tzinfo is None for v in e[c]):raise ValueError('Timezone required')
        e[c]=pd.to_datetime(e[c],utc=True,format='mixed')
    if (e.known_at<e.kickoff).any():raise ValueError('Outcome before kickoff')
    if e.duplicated(['season','player_uuid','match_id']).any() or e.duplicated(['season','player_uuid','kickoff']).any():raise ValueError('Duplicate player event')
    minutes=pd.to_numeric(e.minutes,errors='raise')
    if not(minutes.isna()|minutes.between(0,120)).all():raise ValueError('Invalid competition minutes')
    if not(e.started.isna()|e.started.isin([True,False])).all():raise ValueError('Invalid start label')
    e['minutes']=minutes
    groups={(s,str(p)):g.sort_values(['kickoff','match_id']) for(s,p),g in e.groupby(['season','player_uuid'])}
    rows=[];cache={}
    for r in target.itertuples():
        cut=pd.Timestamp(r.cutoff)
        if cut.tzinfo is None:raise ValueError('Timezone required')
        key=(r.season,str(r.player_uuid),str(r.club),str(cut))
        if key in cache:rows.append(cache[key]);continue
        g=groups.get((r.season,str(r.player_uuid)),e.iloc[:0]);g=g[g.known_at.lt(cut)]
        if (g.kickoff.ge(cut)).any():raise ValueError('Future kickoff in history')
        if 'fixture_uuid' in target and len(g) and g.match_id.astype(str).eq(str(r.fixture_uuid)).any():raise ValueError('Target event in history')
        age=(cut-g.kickoff).dt.total_seconds()/86400;valid=g.minutes.notna();played=g[valid&g.minutes.gt(0)]
        club=g[g.club.eq(r.club)&g.started.notna()];known_starts=club.started.astype(float)
        recent=known_starts.tail(3);prior=known_starts.iloc[:-3].tail(6)
        v=dict(context_max_known_at=g.known_at.max()if len(g)else pd.NaT,
            context_rest_days=(cut-played.kickoff.max()).total_seconds()/86400 if len(played)else np.nan,
            context_minutes_7d=float(g.loc[valid&age.le(7),'minutes'].sum()),context_minutes_14d=float(g.loc[valid&age.le(14),'minutes'].sum()),
            context_nonpl_minutes_7d=float(g.loc[valid&age.le(7)&g.competition.ne('Premier League'),'minutes'].sum()),
            context_missing_minutes_14d=int((age.le(14)&~valid).sum()),context_recorded_games_14d=int(age.le(14).sum()),
            context_recent_start_share3=float(recent.mean())if len(recent)else np.nan,
            context_prior_start_share6=float(prior.mean())if len(prior)else np.nan,
            context_role_start_share_change=float(recent.mean()-prior.mean())if len(recent)==3 and len(prior)>=3 else np.nan,
            context_role_games=len(club),context_last_competition=str(club.competition.iloc[-1])if len(club)else None,
            context_last_started=float(club.started.iloc[-1])if len(club)else np.nan,
            context_history_missing=len(g)==0,context_coverage_complete=False)
        cache[key]=v;rows.append(v)
    return pd.concat([target.reset_index(drop=True),pd.DataFrame(rows)],axis=1)


def apply_physical_context(frame,context):
    """Explicit shadow adapter: no default inference entry point calls this."""
    keys=['season','fixture_uuid','player_uuid'];extra=['context_rest_days','context_minutes_7d','context_minutes_14d','context_max_known_at']
    if frame.duplicated(keys).any()or context.duplicated(keys).any():raise ValueError('Duplicate context identity')
    m=frame[keys+['cutoff']].merge(context[keys+['cutoff']+extra],on=keys,how='left',validate='one_to_one',indicator=True,suffixes=('','_context'))
    if not m._merge.eq('both').all():raise ValueError('Missing physical context')
    if not pd.to_datetime(m.cutoff,utc=True,format='mixed').eq(pd.to_datetime(m.cutoff_context,utc=True,format='mixed')).all():raise ValueError('Physical context cutoff mismatch')
    result=frame.copy()
    for original,new in [('rest_days','context_rest_days'),('minutes_7d','context_minutes_7d'),('minutes_14d','context_minutes_14d'),('physical_last_known_at','context_max_known_at')]:result[original]=m[new].to_numpy()
    # A partial sum is only a lower bound, never a measured zero workload.
    missing=context.set_index(keys).reindex(pd.MultiIndex.from_frame(frame[keys]))
    uncertain=missing.context_missing_minutes_14d.gt(0).to_numpy()|missing.context_history_missing.to_numpy(bool)
    result.loc[uncertain,['rest_days','minutes_7d','minutes_14d']]=np.nan
    result['physical_last_known_at']=pd.to_datetime(result.physical_last_known_at,utc=True,format='mixed')
    if not(pd.to_datetime(result.physical_last_known_at,utc=True,format="mixed").isna()|pd.to_datetime(result.physical_last_known_at,utc=True,format="mixed").lt(pd.to_datetime(result.cutoff,utc=True,format="mixed"))).all():raise ValueError('Future physical context')
    return result
