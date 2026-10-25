"""Observed context from canonical all-competition events, never PL-only CSVs.

Provider team_code differs from canonical team_id. Only the canonical ID is
joined to the target roster. Actual captured-at clocks bound live evidence;
historical reconstructed publication clocks alone never establish ingestion.
"""
import argparse,gzip,hashlib,json
from pathlib import Path
import pandas as pd
from competition_context import context_features

COMP={'prem':'Premier League','cl':'Champions League','el':'Europa League','conf':'Conference League','conf_qual':'Conference qualification','efl':'League Cup','fa':'FA Cup'}


def canonical_events(games,players,clubs,season):
    by={g['match_id']:g for g in games}
    if len(by)!=len(games):raise ValueError('Duplicate source match')
    names=clubs.set_index('team_id').team.to_dict();rows=[]
    for p in players:
        if not p.get('player_uuid'):continue
        if p['team_id']not in names:continue
        g=by[p['match_id']]
        if g['finished']is not True:continue
        if g['tournament']not in COMP:raise ValueError('Unknown competition')
        observed=pd.Timestamp(g['observed_at']);available=pd.Timestamp(p['available_at']);kick=pd.Timestamp(g['kickoff_time'])
        if any(c.tzinfo is None for c in [observed,available,kick]):raise ValueError('Timezone required')
        if observed<kick or available<kick:raise ValueError('Outcome before kickoff')
        rows.append(dict(season=season,match_id=p['match_id'],player_uuid=p['player_uuid'],club=names[p['team_id']],canonical_team_id=p['team_id'],provider_team_code=p.get('team_code'),competition=COMP[g['tournament']],kickoff=kick.isoformat(),known_at=max(observed,available).isoformat(),observed_at=observed.isoformat(),minutes=p.get('minutes_played'),started=p.get('started')))
    return pd.DataFrame(rows)


def combine_current_load(target,cups,descriptive):
    """Keep the authoritative PL NUM inputs; add only captured non-PL games.

    A retained all-competition archive may predate the latest PL rebuild.
    Never overwrite fresher PL evidence or count an old PL game twice.
    """
    keys=['season','fixture_uuid','player_uuid'];result=descriptive.copy()
    base=target.set_index(keys).reindex(pd.MultiIndex.from_frame(result[keys]))
    cup=cups.set_index(keys).reindex(pd.MultiIndex.from_frame(result[keys]))
    for days in (7,14):result[f'context_minutes_{days}d']=base[f'minutes_{days}d'].to_numpy()+cup[f'context_minutes_{days}d'].to_numpy()
    a=base.rest_days.to_numpy(float);b=cup.context_rest_days.to_numpy(float)
    import numpy as np
    result['context_rest_days']=np.fmin(a,b)
    result['context_missing_minutes_14d']=cup.context_missing_minutes_14d.to_numpy()
    clocks=pd.concat([pd.to_datetime(base.physical_last_known_at,utc=True,format='mixed').reset_index(drop=True),pd.to_datetime(cup.context_max_known_at,utc=True,format='mixed').reset_index(drop=True)],axis=1)
    result['context_max_known_at']=clocks.max(axis=1)
    result['context_history_missing']=clocks.isna().all(axis=1)
    result['context_load_source']='authoritative PL NUM inputs plus captured non-PL events'
    return result


def build(capture,inputs,out):
    capture,inputs,out=map(Path,(capture,inputs,out));out.mkdir(parents=True,exist_ok=True)
    sourcefiles=[capture/'match_actuals.jsonl.gz',capture/'player_match_events.jsonl.gz',inputs/'pm.csv.gz',inputs/'target.csv.gz']
    load=lambda p:[json.loads(l)for l in gzip.open(p,'rt')]
    games,players=map(load,sourcefiles[:2]);frame=pd.read_csv(sourcefiles[2],low_memory=False)
    if frame.cutoff.nunique()!=1 or frame.season.nunique()!=1:raise ValueError('Mixed target origin/season')
    clubs=frame[['team_id','team']].drop_duplicates()
    if clubs.team_id.duplicated().any():raise ValueError('Ambiguous target club')
    events=canonical_events(games,players,clubs,str(frame.season.iloc[0]))
    target=frame[['season','fixture_uuid','player_uuid','team_id','cutoff']].merge(clubs.rename(columns={'team':'club'}),on='team_id',validate='many_to_one')
    context=context_features(target,events)
    cup_context=context_features(target,events[events.competition.ne('Premier League')])
    authoritative=pd.read_csv(inputs/'target.csv.gz',low_memory=False,float_precision='round_trip')
    context=combine_current_load(authoritative,cup_context,context)
    context.to_csv(out/'current-context.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    events.to_csv(out/'observed-events.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    cov=events.groupby('competition').agg(player_rows=('player_uuid','size'),games=('match_id','nunique'),missing_minutes=('minutes',lambda s:int(s.isna().sum()))).reset_index();cov.to_csv(out/'coverage.csv',index=False)
    receipt=dict(version='competition-context-sidecar-v2',players=int(target.player_uuid.nunique()),fixture_rows=len(context),cutoff=str(frame.cutoff.iloc[0]),source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in sourcefiles},context_sha256=hashlib.sha256((out/'current-context.csv.gz').read_bytes()).hexdigest(),coverage_complete=False,source_clock_type='max(actual per-match observed_at, recorded availability); no backdating before capture',earliest_capture=str(pd.to_datetime(events.observed_at,utc=True).min()),latest_capture=str(pd.to_datetime(events.observed_at,utc=True).max()),missing_minutes=int(events.minutes.isna().sum()),identity_scope='canonical team_id and player_uuid; provider team_code never treated as canonical club ID',minute_input_recipe='Preserve authoritative PL feature values, add only non-PL events; never replace fresh PL history with an older retained archive',numbers_reweighted=False,activated=False,production_changed=False)
    (out/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='source_sha256'}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();build(a.capture,a.inputs,a.out)

if __name__=='__main__':main()
