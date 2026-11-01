"""Versioned B physical ledger, separate from PL role/outcome history.

The same computation serves historical calibration and live inference. Missing
cup coverage is an explicit subset/fallback, never invented player minutes.
"""
import gzip,json,sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
VERSION='B-verified-physical-workload-v2'
FIELDS=['rest_days','team_rest_days','minutes_7d','minutes_14d']

def validate(ledger):
    f=ledger.copy()
    for c in ['kickoff','known_at']:f[c]=pd.to_datetime(f[c],utc=True,format='mixed')
    if f.duplicated(['season','match_id','team_id','player_uuid']).any():raise ValueError('Duplicate physical player-match')
    if f[['season','match_id','team_id','player_uuid','minutes','kickoff','known_at']].isna().any().any():raise ValueError('Unknown physical ledger field')
    if not np.isfinite(f.minutes).all()or not f.minutes.between(0,120).all():raise ValueError('Invalid physical minutes')
    if (f.known_at<f.kickoff).any():raise ValueError('Physical outcome known before kickoff')
    if (f.groupby(['season','match_id']).kickoff.nunique()>1).any():raise ValueError('Physical match has inconsistent kickoffs')
    return f

def current_ledger(pl,events,games,cutoff):
    rows=[];cut=pd.Timestamp(cutoff);by={g['match_id']:g for g in games}
    for r in pl.itertuples():rows.append(dict(season=r.season,match_id=r.fixture_uuid,player_uuid=r.player_uuid,team_id=r.team_id,minutes=r.minutes,kickoff=r.kickoff_at,known_at=r.known_at,competition='prem'))
    seen=set()
    for e in events:
        g=by[e['match_id']]
        if g['tournament']=='prem':continue # PL canonical rows already above.
        if not g.get('finished')or not e.get('player_uuid')or e.get('minutes_played')is None:continue
        if g['tournament']not in ['cl','el','conf','conf_qual','fa','efl']:continue
        key=(e['match_id'],int(e['team_id']),e['player_uuid'])
        if key in seen:raise ValueError('Duplicate cup physical event')
        seen.add(key);known=max(pd.Timestamp(e['available_at']),pd.Timestamp(g['available_at']))
        if known>=cut:continue
        rows.append(dict(season='2026-27',match_id=e['match_id'],player_uuid=e['player_uuid'],team_id=e['team_id'],minutes=e['minutes_played'],kickoff=g['kickoff_time'],known_at=known,competition=g['tournament']))
    return validate(pd.DataFrame(rows))

def historical_ledger(root):
    root=Path(root)
    with sqlite3.connect(f'file:{root/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        core=pd.read_sql_query("SELECT season,fixture_uuid AS match_id,player_uuid,team_id,minutes,kickoff_at AS kickoff FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
    core['competition']='prem';core['known_at']=pd.to_datetime(core.kickoff,utc=True)+pd.to_timedelta(np.where(core.season.eq('2025-26'),3,4),unit='h')
    recovered=pd.read_csv(root/'analysis/results/workload-recovered-v4/official_player_minutes.csv');recovered=recovered[recovered.competition.ne('prem')].rename(columns={'available_at':'known_at'});recovered['season']='2025-26'
    source=root/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz'
    extra=[];mapping={};observations=[]
    if source.exists():
        observations=[json.loads(x)for x in gzip.open(source,'rt')]
        canonical={(r.player_uuid,pd.Timestamp(r.kickoff).value):int(r.team_id)for r in core[core.season.eq('2024-25')].itertuples()}
        for r in observations:
            if r.get('competition')!='prem' or not r.get('player_uuid')or not r.get('kickoff'):continue
            team=canonical.get((r['player_uuid'],pd.Timestamp(r['kickoff']).value));provider=r.get('provider_team_id')
            if team is None or provider is None:continue
            if provider in mapping and mapping[provider]!=team:raise ValueError('Ambiguous historical provider club')
            mapping[provider]=team
        for r in observations:
            team=mapping.get(r.get('provider_team_id'))
            if r.get('competition')=='prem' or team is None or not r.get('player_uuid')or r.get('minutes')is None or not r.get('available_at_proxy'):continue
            if r.get('identity_status')!='mapped':continue
            extra.append(dict(season='2024-25',match_id=r['match_id'],player_uuid=r['player_uuid'],team_id=team,minutes=r['minutes'],kickoff=r['kickoff'],known_at=r['available_at_proxy'],competition=r['competition']))
    pieces=[core,recovered[core.columns]]
    if extra:pieces.append(pd.DataFrame(extra)[core.columns])
    ledger=validate(pd.concat(pieces,ignore_index=True))
    return ledger,{'2024-25':f'verified PL + {len(extra)} mapped non-PL player-match observations; historical coverage is a sourced subset, not certified complete','2025-26':'verified PL + audited recovered cup/UEFA subset; completeness not claimed','availability':'historical +3/+4h proxies, not certified publication clocks'}

def features(target,ledger):
    h=validate(ledger);out=target.copy();physical={};teams={};cache={};result=[]
    for key,g in h.groupby(['season','player_uuid']):physical[key]=(g.kickoff.astype('int64').to_numpy(),g.known_at.astype('int64').to_numpy(),g.minutes.to_numpy(float))
    for key,g in h.groupby(['season','team_id']):
        g=g[['match_id','kickoff','known_at']].drop_duplicates('match_id');teams[key]=(g.kickoff.astype('int64').to_numpy(),g.known_at.astype('int64').to_numpy())
    for r in out.itertuples():
        cut=pd.Timestamp(r.cutoff)
        if cut.tzinfo is None:raise ValueError('Physical feature cutoff requires timezone')
        key=(r.season,r.player_uuid,int(r.team_id),cut.value)
        if key not in cache:
            ko,known,minutes=physical.get(key[:2],(np.array([],dtype=np.int64),np.array([],dtype=np.int64),np.array([])));safe=known<cut.value
            if np.any(ko[safe]>=cut.value):raise ValueError('Future physical outcome')
            played=safe&(minutes>0);teamko,teamknown=teams.get((r.season,int(r.team_id)),(np.array([],dtype=np.int64),np.array([],dtype=np.int64)));tsafe=teamknown<cut.value;day=pd.Timedelta(days=1).value
            cache[key]=dict(rest_days=(cut.value-ko[played].max())/day if played.any()else np.nan,team_rest_days=(cut.value-teamko[tsafe].max())/day if tsafe.any()else np.nan,minutes_7d=float(minutes[safe&(ko>cut.value-7*day)].sum()),minutes_14d=float(minutes[safe&(ko>cut.value-14*day)].sum()),physical_last_known_at=pd.Timestamp(known[safe].max(),tz='UTC')if safe.any()else pd.NaT,physical_feature_version=VERSION)
        result.append(cache[key])
    values=pd.DataFrame(result,index=out.index)
    for c in values:out[c]=values[c]
    return out
