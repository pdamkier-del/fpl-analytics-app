#!/usr/bin/env python3
"""Reconstruct current-season training covariates, with explicit quality gaps.

No present-day q/H, workload, performance or news is copied into past GWs.
The retrospective official player-GW roster is NOT claimed to be an archived
predeadline roster. This reconstruction permits diagnostic inference only.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_current_locked_inputs import readjl, csvgz, dump
from fpl_v1_1_model.role_history import RoleHistory,summarize_state
from fpl_v1_1_model.role_classifier import ROLES
from fpl_v1_1_model.workload import WorkloadHistory
from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import build_strict_team_news_features,normalize_team_news
from fpl_v1_1_model.archived_current_season_cohorts import load_archived_rosters,filter_observed_against_snapshots
from run_v4_three_state_sequence_experiment import add_sequence_features
from build_locked_live_performance_features import build as performance
from build_locked_live_v2_baseline import build as baseline
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'


def build():
    actual=pd.read_csv(BASE/'player_fixture_observations.csv.gz')
    archive,archive_evidence=load_archived_rosters(WORK/'predeadline_2026_archives')
    audited=filter_observed_against_snapshots(actual,archive)
    rejected=audited.loc[~audited._archive_eligibility].copy()
    actual=audited.loc[audited._archive_eligibility].drop(columns=['_archive_eligibility','_archive_reason']).copy()
    if actual.empty or actual.gw.nunique()!=5:
        raise ValueError('Archived predeadline historical roster rejects full GW1-5 training source')
    source=pd.read_csv(BASE/'source_feature_matrix.csv.gz',low_memory=False)
    origin=int(source.gw.iloc[0]); current_cut=pd.Timestamp(source.cutoff.iloc[0])
    bootstrap=json.loads((WORK/'bootstrap.json').read_text())
    cuts={int(e['id']):pd.Timestamp(e['deadline_time']) for e in bootstrap['events']}
    roster=source.drop_duplicates('player_uuid').set_index('player_uuid')
    events=readjl(WORK/'player_match_events.jsonl.gz')
    event_map={(r['match_id'],str(r['player_uuid'])):r for r in events}
    games=readjl(WORK/'match_actuals.jsonl.gz')
    classified=pd.read_csv(BASE/'classified_starters.csv.gz')
    rh=RoleHistory();wh=WorkloadHistory()
    for (mid,tid),g in classified.groupby(['match_id','team_id']):
        players=[]
        for r in g.itertuples():
            e=event_map[(mid,str(r.player_uuid))]
            players.append(dict(player_uuid=str(r.player_uuid),role=r.final_role,
                                started=True,minutes=float(e['minutes_played'])))
        if len(players)==11:
            rh.add_game(int(tid),pd.Timestamp(g.available_at.iloc[0]),mid,players,
                        importance=float(g.importance.iloc[0]))
    for game in games:
        mid=game['match_id']
        by_team={r['team_id'] for r in events if r['match_id']==mid}
        for tid in by_team:
            rows={str(r['player_uuid']):dict(minutes=float(r['minutes_played']),started=bool(r['started']))
                  for r in events if r['match_id']==mid and r['team_id']==tid and r.get('minutes_played') is not None}
            wh.add_game(int(tid),mid,pd.Timestamp(game['kickoff_time']),
                        pd.Timestamp(game['available_at']),game['tournament'],rows,
                        player_stats_complete=len(rows)>=11)
    target=[]
    actual['outcome_known_at']=pd.to_datetime(actual.available_at,utc=True)
    actual=actual[(actual.gw<origin)&(actual.outcome_known_at<current_cut)].copy()
    for (gw,tid),group in actual.groupby(['gw','team_id'],sort=True):
        cut=cuts[int(gw)]
        states={speed:rh.state(tid,cut,half,q_importance_scale=.1,h_importance_scale=.4,importance_floor=.35)
                for speed,half in [('fast',3),('slow',10)]}
        ws,default,_=wh.state(tid,cut)
        for o in group.itertuples():
            historical=archive[int(gw)][int(o.fpl_element)]
            name=roster.loc[o.player_uuid]
            if int(historical['team'])!=int(tid):raise ValueError('Historical team mismatched archived official snapshot')
            row=dict(season='2026-27',gw=int(gw),target_gw=int(gw),team_id=int(tid),
                     fixture_uuid=o.fixture_uuid,player_uuid=o.player_uuid,player=str(historical['name']),
                     team=next(t['name'] for t in bootstrap['teams'] if t['id']==int(tid)),pos=o.fpl_position,fpl_element=o.fpl_element,
                     cutoff=cut.isoformat(),outcome_known_at=o.outcome_known_at,
                     y=int(o.started),minutes=float(o.minutes))
            for speed,(ss,caps,hist) in states.items():
                state=ss.get(str(o.player_uuid),{})
                for k,v in summarize_state(state,caps).items():
                    if k.startswith('role_'):row[k+'_'+speed]=v
                for kind in ('q','H'):
                    for role in ROLES:row[f'{kind}_{role}_{speed}']=state.get(kind,{}).get(role,0.)
                if speed=='slow':
                    q=state.get('q',{})
                    row['expected_role']=max(sorted(q),key=q.get) if q else 'UNKNOWN'
                    row['role_started_last_gw']=float(bool(hist and any(p['player_uuid']==str(o.player_uuid) and p['started'] for p in hist[-1]['players'])))
            row.update(ws.get(str(o.player_uuid),default));target.append(row)
    frame=add_sequence_features(pd.DataFrame(target).reset_index(drop=True))
    frame=performance(frame,persist=False)
    parts=[]
    for gw,group in frame.groupby('gw',sort=True):
        history=actual[(actual.gw<gw)&(actual.outcome_known_at<cuts[int(gw)])]
        parts.append(baseline(group.reset_index(drop=True),history,persist=False))
    frame=pd.concat(parts,ignore_index=True)
    ratings=pd.read_csv(ROOT/'data_v1_1/derived/mm_v2_ratings/player_match_ratings_2026_27.csv.gz')
    frame=build_rating_features(frame,ratings)
    # Archived 2026 official snapshots supply VERIFIED SOURCE-TIMED Team News
    # for GW1-5. Do not carry origin GW6 news backward.
    identities=actual[['gw','fpl_element','player_uuid','team_id']].drop_duplicates()
    archived_news=[]
    for r in identities.itertuples(index=False):
        gw=int(r.gw);snapshot=archive[gw][int(r.fpl_element)]
        observed=archive_evidence[gw]['snapshot_at_utc']
        if pd.Timestamp(observed)>=cuts[gw]:
            raise ValueError('Post-cutoff archived Team News observation')
        prob=snapshot.get('chance_next')
        archived_news.append(dict(
            season='2026-27',gw=gw,cutoff=cuts[gw].isoformat(),
            player_uuid=str(r.player_uuid),fpl_element=int(r.fpl_element),
            effective_at=observed,observed_at=observed,
            identity_status='mapped',timing_verified=True,tier='strict',
            normalized_availability_state=normalize_team_news(
                snapshot.get('status'),snapshot.get('news'),prob),
            scoped_chance=prob,raw_status=snapshot.get('status'),
            raw_news=snapshot.get('news'),news_added=snapshot.get('news_added'),
            source='Official FPL bootstrap-static archived by Randdalf/fplcache',
            source_id=archive_evidence[gw]['source_sha256'],
            carried_from_earlier_gw=False,unchanged_news_since_previous_gw=False))
    if len(archived_news)!=len(frame):
        raise ValueError('Historical archive Team News row count differs from training cohort')
    # Historical GW1-5 training must use only the independently archived
    # strictly predeadline snapshots above. The separate origin-GW6 strict
    # file contains live/nullable publication timestamps and belongs to
    # CURRENT forecast features, never to past training rows.
    strict=pd.DataFrame(archived_news)
    if set(strict.gw.astype(int)) != set(frame.gw.astype(int)):
        raise ValueError('Archived Team News GW coverage differs from historical training')
    frame=build_strict_team_news_features(frame,strict)
    if frame.team_news_known.sum()<len(frame)*.7:
        raise ValueError('Predeadline archive historical Team News coverage unexpectedly low')
    if frame.loc[frame.gw.lt(origin),'team_news_source'].isna().any():
        raise ValueError('Missing archived scoped historical source evidence')
    if (pd.to_datetime(frame.cutoff,utc=True)>=pd.to_datetime(frame.outcome_known_at,utc=True)).any():
        raise ValueError('Training observation occurs before its forecast cutoff')
    csvgz(BASE/'reconstructed_training_features.csv.gz',frame)
    cohort_coverage=[]
    for gw in sorted(map(int,frame.gw.unique())):
        have=set(frame.loc[frame.gw.eq(gw),'fpl_element'].astype(int))
        registered={fid for fid,r in archive[gw].items() if r['position'] in (1,2,3,4)}
        cohort_coverage.append(dict(gw=gw,registered=len(registered),training_players=len(have),
                                    unresolved_registered_ids=sorted(registered-have)))
    report=dict(classification='ARCHIVED_PREDEADLINE_SNAPSHOT_TRAINING_WITH_VERIFIED_PARTIAL_COHORT_NOT_CERTIFIED',
                rows=len(frame),gws=sorted(map(int,frame.gw.unique())),
                source_capture=str(source.roster_observed_at.iloc[0]),
                historical_news_known=int(frame.team_news_known.sum()),
                archived_roster_snapshot_gws=sorted(archive),
                registered_cohort_coverage=cohort_coverage,
                historical_postmatch_rows_before_archived_validation=int(len(audited)),
                historical_rows_rejected_not_registered_or_wrong_club=int(len(rejected)),
                historical_rejected_reasons=rejected._archive_reason.value_counts().to_dict(),
                verified_predeadline_source_rows=int(len(frame)),
                blockers=['Archived snapshots are taken between 76 and 387 minutes before each deadline and may miss late changes',
                          f"{sum(len(r['unresolved_registered_ids']) for r in cohort_coverage)} archived registrations lack a compatible observed fixture/club; they remain excluded",
                          'tackles_won FotMob provider semantics remain unverified'],
                historical_covariates_use_only_pre_cutoff_outcomes=True,
                live_certified=False)
    dump(WORK/'live_training_provenance.json',report)
    print(json.dumps(report),flush=True)
    return frame
if __name__=='__main__':build()

