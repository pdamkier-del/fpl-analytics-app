#!/usr/bin/env python3
"""Observed multi-competition rotation/workload and source gates, MM only.

No future fixture calendar is relabelled as known at a past deadline. A
substitute appearance is counted from explicit nonstarter+positive minutes;
an early starter exit is NOT automatically a substitution event.
"""
import collections
import csv
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/mm-match-importance-20261016'
RAW25=ROOT/'data_v1_1/raw/all-competitions-2025-26'
RAW24=ROOT/'data_v1_1/derived/season_2024_25_v1'
COMP={'prem':'Premier League','cl':'Champions League','champions-league':'Champions League',
      'el':'Europa League','europa-league':'Europa League','conf':'Conference League',
      'conference-league':'Conference League','conf_qual':'Conference qualification',
      'fa':'FA Cup','efl':'League Cup','efl-cup':'League Cup'}


def jl(path):
    with gzip.open(path,'rt')as f:return [json.loads(x)for x in f]


def integer(x):
    try:
        a=float(x)
        return str(int(a))if np.isfinite(a)and a==int(a)else None
    except (TypeError,ValueError):return None


def bool_value(x):
    if str(x).lower()in ['true','1']:return True
    if str(x).lower()in ['false','0']:return False
    return None


def valid_intervals(rows):
    """Require whole-team interval/minute concordance, not merely endpoints."""
    played=rows[rows.minutes.gt(0)]
    if len(played)<11 or int(played.started.eq(True).sum())!=11:return False
    for r in played.itertuples():
        if pd.isna(r.start_min)or pd.isna(r.finish_min):return False
        if not 0<=r.start_min<=r.finish_min<=130:return False
        if abs((r.finish_min-r.start_min)-r.minutes)>2:return False
        if r.started is True and r.start_min!=0:return False
        if r.started is False and r.start_min<=0:return False
    return True


def lineup_changes(previous,current):
    if len(previous)!=11 or len(current)!=11:return None
    return 11-len(set(previous)&set(current))


def load24(core,names):
    matches={r['match_id']:r for r in jl(RAW24/'all_competition_match_actuals.jsonl.gz')}
    records=[]
    for r in jl(RAW24/'all_competition_player_observations.jsonl.gz'):
        m=matches[r['match_id']]
        pid=str(r.get('provider_player_id')or'')
        if not pid:continue
        records.append(dict(season='2024-25',club=r['team'],match_id=r['match_id'],
            competition=COMP.get(r['competition'],'Unknown'),raw_comp=r['competition'],
            kickoff=r['kickoff'],stage=str(m.get('stage')or'Unknown'),
            player_id='fotmob:'+pid,player_uuid=r.get('player_uuid'),minutes=r['minutes'],
            started=r.get('started'),start_min=np.nan,finish_min=np.nan,
            publication_verified=False,source_url=r['source_url'],
            available_proxy=r.get('available_at_proxy'),snapshot_before_deadline=False))
    frame=pd.DataFrame(records)
    prem=frame[frame.raw_comp.eq('prem') & frame.player_uuid.notna()].copy()
    prem['clock']=pd.to_datetime(prem.kickoff,utc=True,format='mixed')
    reference=core[core.season.eq('2024-25')].copy()
    reference['clock']=pd.to_datetime(reference.kickoff_at,utc=True,format='mixed')
    aligned=prem.merge(reference[['player_uuid','clock','team_id']],on=['player_uuid','clock'],validate='many_to_one')
    pairs=aligned[['club','team_id']].drop_duplicates()
    if pairs.club.duplicated().any() or len(pairs)!=20:raise ValueError('2024 source club identity mismatch')
    clubmap={r.club:names[('2024-25',int(r.team_id))]for r in pairs.itertuples()}
    if not frame.club.isin(clubmap).all():raise ValueError('Unmapped 2024 club')
    frame['club']=frame.club.map(clubmap)
    return frame,dict(source_player_rows=len(records),club_mapping=clubmap,
        strict_publication_rows=0,competition_stage_source='Pinned postmatch FotMob match ledger; not a historical schedule snapshot')


def load25(core,mapping,names):
    manifest=json.loads((RAW25/'SOURCE_MANIFEST.json').read_text())
    for entry in manifest['files']:
        raw=(RAW25/entry['path']).read_bytes()
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=entry['git_blob_sha']:
            raise ValueError('Raw source blob mismatch: '+entry['path'])
    matches=pd.concat([pd.read_csv(p)for p in sorted(RAW25.glob('GW*/matches.csv'))],ignore_index=True)
    if matches.match_id.duplicated().any():raise ValueError('Duplicate raw match key')
    lines=pd.concat([pd.read_csv(p)for p in sorted(RAW25.glob('GW*/lineups.csv'))],ignore_index=True)
    stats=pd.concat([pd.read_csv(p)for p in sorted(RAW25.glob('GW*/playermatchstats.csv'))],ignore_index=True)
    if lines.duplicated(['match_id','team_code','player_id']).any():
        # Do not accept conflicting duplicate identities, even across snapshots.
        known=lines[lines.player_id.notna()]
        if known.duplicated(['match_id','team_code','player_id']).any():raise ValueError('Duplicate lineup player')
    stats['pid']=stats.player_id.map(integer);lines['pid']=lines.player_id.map(integer)
    lines['player_uuid']=lines.pid.map(mapping)
    matches['kickoff']=pd.to_datetime(matches.kickoff_time,utc=True,errors='coerce',format='mixed')
    # Derive provider team code -> canonical club using exact PL player/time joins.
    prem=lines.merge(matches[matches.tournament.eq('prem')][['match_id','kickoff']],on='match_id',validate='many_to_one')
    co=core[core.season.eq('2025-26')].copy();co['kickoff']=pd.to_datetime(co.kickoff_at,utc=True,format='mixed')
    aligned=prem.merge(co[['player_uuid','kickoff','team_id']],on=['player_uuid','kickoff'],validate='many_to_one')
    pairs=aligned[['team_code','team_id']].dropna().drop_duplicates()
    if pairs.team_code.duplicated().any():raise ValueError('Conflicting team-code mapping')
    clubs={integer(r.team_code):names[('2025-26',int(r.team_id))]for r in pairs.itertuples()}
    quarantine=set(pd.read_csv(ROOT/'analysis/results/independent-europe-audit/workload_quarantine.csv').match_id)
    quarantined=matches[matches.match_id.isin(quarantine)]
    usable=matches[~matches.match_id.isin(quarantine)&matches.kickoff.notna()]
    valid_keys=set(usable.match_id)
    joined=lines[lines.match_id.isin(valid_keys)&lines.pid.notna()&lines.team_code.map(integer).isin(clubs)].merge(
        usable[['match_id','kickoff','tournament']],on='match_id',validate='many_to_one').merge(
        stats[['match_id','pid','minutes_played','start_min','finish_min']],on=['match_id','pid'],how='left',validate='one_to_one')
    records=[]
    for r in joined.itertuples():
        records.append(dict(season='2025-26',club=clubs[integer(r.team_code)],match_id=r.match_id,
            competition=COMP.get(r.tournament,'Unknown'),raw_comp=r.tournament,
            kickoff=r.kickoff.isoformat(),stage='Unknown: no verified stage in player payload',
            player_id='fpl2025:'+r.pid,player_uuid=r.player_uuid,minutes=r.minutes_played,
            started=bool_value(r.is_starting),start_min=r.start_min,finish_min=r.finish_min,
            publication_verified=False,source_url='olbauday/FPL-Core-Insights pinned source manifest',
            available_proxy=None,snapshot_before_deadline=False))
    coverage=[]
    for comp,g in matches.groupby('tournament'):
        coverage.append(dict(season='2025-26',competition=COMP.get(comp,comp),raw_match_keys=len(g),
            missing_kickoffs=int(g.kickoff.isna().sum()),quarantined_keys=int(g.match_id.isin(quarantine).sum()),
            surviving_keys=int((g.kickoff.notna()&~g.match_id.isin(quarantine)).sum())))
    return pd.DataFrame(records),dict(raw_matches=len(matches),raw_lineups=len(lines),
        raw_stats=len(stats),excluded_quarantine_keys=len(quarantined),club_mapping=clubs,
        no_id_lineup_rows=int(lines.pid.isna().sum()),coverage=coverage,
        FA_Cup='Not Available: no raw FA Cup matches',source_scope='Partial archive, not complete competition schedule')


def team_games(players):
    rows=[];xis={}
    for (season,club,mid),g in players.groupby(['season','club','match_id'],sort=True):
        if g.player_id.duplicated().any():raise ValueError('Duplicate team-match player')
        starters=set(g.loc[g.started.eq(True),'player_id'])
        xi_ok=len(starters)==11
        known=g.minutes.notna()&g.minutes.between(0,120)
        entry=g.started.eq(False)&g.minutes.gt(0)&known
        iv=valid_intervals(g)if 'start_min'in g else False
        r=g.iloc[0]
        row=dict(season=season,club=club,match_id=mid,competition=r.competition,stage=r.stage,
            kickoff=r.kickoff,complete_xi=xi_ok,starter_count=len(starters),observed_players=len(g),
            players_with_known_minutes=int(known.sum()),substitute_entries=int(entry.sum())if xi_ok else None,
            substitution_exits=None,mean_concordant_entry_minute=None,intervals_valid=iv,
            unknown_minute_rows=int((~known).sum()),entries_are_recorded_lower_bounds=True,
            starters_exact90=int((g.started.eq(True)&g.minutes.eq(90)).sum())if xi_ok else None,
            starters_atleast90=int((g.started.eq(True)&g.minutes.ge(90)).sum())if xi_ok else None,
            observed_extra_time=bool(g.minutes.gt(90).any()),
            mean_starter_minutes=float(g.loc[g.started.eq(True)&known,'minutes'].mean())if xi_ok else None,
            timing_note='Exit cause/event missing; minutes<90 is not a substitution event')
        if iv:
            # Entry endpoints validated against complete XI and observed minutes.
            row['mean_concordant_entry_minute']=float(g.loc[entry,'start_min'].mean())if entry.any()else None
        xis[(season,club,mid)]=starters if xi_ok else None
        rows.append(row)
    games=pd.DataFrame(rows);games['kickoff']=pd.to_datetime(games.kickoff,utc=True,format='mixed')
    enriched=[]
    for (_, _),g in games.groupby(['season','club']):
        g=g.sort_values(['kickoff','match_id']).copy();previous=None
        for r in g.to_dict('records'):
            key=(r['season'],r['club'],r['match_id']);current=xis[key]
            r['xi_changes_from_previous_recorded']=lineup_changes(previous['xi'],current)if previous and current is not None and previous['xi']is not None else None
            r['previous_recorded_competition']=previous['competition']if previous else None
            r['observed_rest_before_days']=(r['kickoff']-previous['kickoff']).total_seconds()/86400 if previous else None
            previous=dict(xi=current,competition=r['competition'],kickoff=r['kickoff'])
            enriched.append(r)
    games=pd.DataFrame(enriched)
    games=games.sort_values(['season','club','kickoff','match_id'])
    games['next_recorded_competition']=games.groupby(['season','club']).competition.shift(-1)
    nxt=games.groupby(['season','club']).kickoff.shift(-1)
    games['observed_rest_after_days']=(nxt-games.kickoff).dt.total_seconds()/86400
    games['observed_rest_before_days']=pd.to_numeric(games.observed_rest_before_days,errors='coerce')
    games['rest_band']=pd.cut(games.observed_rest_before_days,[-np.inf,3,6,np.inf],labels=['<=3 days','3-6 days','>6 days']).astype(str)
    return games


def individual_workload(players):
    """Recorded minutes only: missing competition observations are never zero."""
    p=players.copy();p['kickoff']=pd.to_datetime(p.kickoff,utc=True,format='mixed');out=[]
    for _,g in p.groupby(['season','club','player_id']):
        g=g.sort_values(['kickoff','match_id']);history=[]
        for r in g.to_dict('records'):
            row={k:r[k]for k in ['season','club','match_id','player_id','player_uuid','kickoff','competition','minutes','started']}
            appeared=[v for v in history if pd.notna(v['minutes'])and v['minutes']>0]
            row['observed_player_rest_before_days']=(r['kickoff']-appeared[-1]['kickoff']).total_seconds()/86400 if appeared else None
            for days in [7,14]:
                known=[v for v in history if 0<(r['kickoff']-v['kickoff']).total_seconds()/86400<=days]
                row[f'recorded_minutes_{days}d']=sum(v['minutes']for v in known if pd.notna(v['minutes']))
                row[f'observed_games_{days}d']=len(known)
                row[f'missing_minutes_{days}d']=sum(pd.isna(v['minutes'])for v in known)
            row['coverage_note']='Observed archive lower bound; not complete workload or a predeadline feature'
            out.append(row);history.append(r)
    result=pd.DataFrame(out);result['observed_player_rest_after_days']=np.nan
    for _,indexes in result.groupby(['season','club','player_id']).groups.items():
        future=None
        for i in reversed(list(indexes)):
            r=result.loc[i]
            if future is not None:result.loc[i,'observed_player_rest_after_days']=(future-r.kickoff).total_seconds()/86400
            if pd.notna(r.minutes)and r.minutes>0:future=r.kickoff
    return result


def summarize(games):
    rows=[]
    for (season,club,comp),g in games.groupby(['season','club','competition']):
        good=g[g.complete_xi]
        rows.append(dict(season=season,club=club,competition=comp,team_games=len(g),complete_xis=len(good),
            mean_xi_changes=float(good.xi_changes_from_previous_recorded.mean())if good.xi_changes_from_previous_recorded.notna().any()else None,
            xi_pairs=int(good.xi_changes_from_previous_recorded.notna().sum()),
            mean_recorded_substitute_entries=float(good.substitute_entries.mean())if len(good)else None,
            substitution_exits=None,mean_concordant_entry_minute=float(good.mean_concordant_entry_minute.mean())if good.mean_concordant_entry_minute.notna().any()else None,
            verified_interval_games=int(good.intervals_valid.sum()),
            starters_exact90_share=float(good.starters_exact90.sum()/(11*len(good)))if len(good)else None,
            starters_atleast90_share=float(good.starters_atleast90.sum()/(11*len(good)))if len(good)else None,
            mean_observed_rest_before_days=float(g.observed_rest_before_days.mean())if g.observed_rest_before_days.notna().any()else None,
            mean_observed_rest_after_days=float(g.observed_rest_after_days.mean())if g.observed_rest_after_days.notna().any()else None))
    return pd.DataFrame(rows)


def turnover_association(players,games):
    """Retrospective mechanism study, NOT MM or a deadline-eligible forecast.

    Competition/stage are recorded current-match categories, not arbitrary
    importance weights. Previous-XI start shares are empirical role proxies.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import Ridge
    p=players[players.season.eq('2024-25')].copy()
    p['kickoff']=pd.to_datetime(p.kickoff,utc=True,format='mixed')
    gp={key:g for key,g in p.groupby(['club','match_id'])}
    samples=[]
    for club,g in games[games.season.eq('2024-25')].groupby('club'):
        history=[]
        for r in g.sort_values('kickoff').to_dict('records'):
            past=[x for x in history if x['kickoff']+pd.Timedelta(hours=4)<r['kickoff']]
            if len(past)>=3 and pd.notna(r['xi_changes_from_previous_recorded']):
                previous=gp[(club,past[-1]['match_id'])]
                previous_xi=set(previous.loc[previous.started.eq(True),'player_id'])
                recent=past[-5:]
                shares=[]
                for pid in previous_xi:
                    shares.append(sum(pid in set(gp[(club,v['match_id'])].loc[lambda a:a.started.eq(True),'player_id'])for v in recent)/len(recent))
                v=dict(club=club,competition=r['competition'],stage=r['stage'],kickoff=r['kickoff'],match_id=r['match_id'],
                    changes=r['xi_changes_from_previous_recorded'],rest_days=(r['kickoff']-past[-1]['kickoff']).total_seconds()/86400,
                    prior_turnover=float(np.mean([x['xi_changes_from_previous_recorded']for x in past[-3:] if pd.notna(x['xi_changes_from_previous_recorded'])])),
                    prior_xi_start_share=float(np.mean(shares)))
                for days in [7,14]:
                    h=[x for x in past if (r['kickoff']-x['kickoff']).total_seconds()/86400<=days]
                    v['team_minutes_'+str(days)]=sum(float(gp[(club,x['match_id'])].minutes.sum())for x in h)
                samples.append(v)
            history.append(r)
    f=pd.DataFrame(samples)
    num=['rest_days','team_minutes_7','team_minutes_14','prior_turnover','prior_xi_start_share']
    early=f.kickoff.lt(pd.Timestamp('2024-12-01',tz='UTC'))
    validation=f.kickoff.ge(pd.Timestamp('2024-12-01',tz='UTC'))&f.kickoff.lt(pd.Timestamp('2025-01-01',tz='UTC'))
    development=f.kickoff.lt(pd.Timestamp('2025-01-01',tz='UTC'));test=~development
    result={};pred=f.loc[test,['club','competition','kickoff','match_id','changes']].copy()
    for label,cat in [('load_team_role_controls',['club']),('plus_competition_stage_categories',['club','competition','stage'])]:
        def model(alpha):
            return make_pipeline(ColumnTransformer([('numeric',StandardScaler(),num),('categorical',OneHotEncoder(handle_unknown='ignore'),cat)]),Ridge(alpha=alpha,solver='lsqr',tol=1e-12))
        losses=[]
        for alpha in [.1,1.,10.,100.]:
            fit=model(alpha).fit(f.loc[early],f.loc[early,'changes'])
            error=np.clip(fit.predict(f.loc[validation]),0,11)-f.loc[validation,'changes']
            losses.append((float(abs(error).mean()),alpha))
        alpha=min(losses)[1];fit=model(alpha).fit(f.loc[development],f.loc[development,'changes'])
        yhat=np.clip(fit.predict(f.loc[test]),0,11);pred[label]=yhat
        error=yhat-pred.changes
        result[label]=dict(alpha=alpha,development_rows=int(development.sum()),evaluation_rows=int(test.sum()),
            turnover_mae=float(abs(error).mean()),turnover_rmse=float(np.sqrt((error**2).mean())),
            coefficients=dict(zip(fit[0].get_feature_names_out(),map(float,fit[1].coef_))))
    delta=abs(pred.plus_competition_stage_categories-pred.changes)-abs(pred.load_team_role_controls-pred.changes)
    pred['paired_absolute_error_delta']=delta
    week=((pred.kickoff-pd.Timestamp('2025-01-01',tz='UTC')).dt.days//7).astype(int)
    blocks=pd.DataFrame({'week':week,'delta':delta}).groupby('week').agg(n=('delta','size'),total=('delta','sum')).reindex(range(int(week.min()),int(week.max())+1),fill_value=0)
    rng=np.random.default_rng(20261016);starts=rng.integers(len(blocks),size=(1000,int(np.ceil(len(blocks)/4))))
    ix=((starts[:,:,None]+np.arange(4))%len(blocks)).reshape(1000,-1)[:,:len(blocks)]
    boot=blocks.total.to_numpy()[ix].sum(1)/blocks.n.to_numpy()[ix].sum(1)
    result['paired_turnover_mae_delta']=dict(delta=float(delta.mean()),interval95=np.quantile(boot,[.025,.975]).tolist())
    result['scope']='2024/25 retrospective XI turnover association, not player-minute MM or causal importance'
    result['roles']='Controls previous-XI empirical start share and continuity; not fully verified individual normal-role/medical effects'
    result['timing']='Past-match availability uses +4h proxy; current stage has no verified historical publication; NOT a deadline-eligible MM forecast'
    result['split']='Tune alpha: pre-Dec2024 train/Dec2024 validation; refit pre-Jan2025; evaluate Jan2025 onward. Reused research season, not untouched holdout.'
    pred.to_csv(OUT/'controlled_turnover_association_predictions.csv',index=False)
    save_json(OUT/'controlled_turnover_association.json',result)
    return result


def save_json(path,d):
    def clean(v):
        if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
        if isinstance(v,(list,tuple)):return[clean(x)for x in v]
        if isinstance(v,(float,np.floating))and not np.isfinite(v):return None
        return v.item()if hasattr(v,'item')else v
    path.write_text(json.dumps(clean(d),indent=2,default=str,allow_nan=False)+'\n')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(ROOT/'work/core.sqlite3')as c:
        core=pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,team_id,kickoff_at,started,minutes FROM player_fixture_observations WHERE is_final=1',c)
        mapping={str(k):v for k,v in c.execute("SELECT external_id,player_uuid FROM player_id_mapping WHERE season='2025-26' AND id_namespace='fpl_element'")}
    names={(r['season'],int(r['team_id'])):r['club']for r in pd.read_csv(ROOT/'analysis/results/role-injury-mm-20261016/coverage.csv').to_dict('records')}
    a,audit24=load24(core,names);b,audit25=load25(core,mapping,names);players=pd.concat([a,b],ignore_index=True)
    games=team_games(players);work=individual_workload(players);summary=summarize(games)
    association=turnover_association(players,games)
    beforeafter=[]
    pl=games[games.competition.eq('Premier League')]
    for fields in [['season','club','previous_recorded_competition'],['season','club','next_recorded_competition'],['season','previous_recorded_competition','rest_band']]:
        for key,g in pl.groupby(fields):
            row=dict(zip(fields,key));row.update(comparison=' / '.join(fields),pl_matches=len(g),valid_turnover_pairs=int(g.xi_changes_from_previous_recorded.notna().sum()),mean_xi_changes=g.xi_changes_from_previous_recorded.mean(),mean_entries=g.substitute_entries.mean(),mean_observed_rest_days=g.observed_rest_before_days.mean());beforeafter.append(row)
    games.to_csv(OUT/'team_match_rotation.csv',index=False)
    work.to_csv(OUT/'individual_recorded_workload.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    summary.to_csv(OUT/'club_competition_summary.csv',index=False)
    matrix=[]
    for season in ['2024-25','2025-26']:
        for club in sorted({v for (s,_),v in names.items()if s==season} if season=='2025-26'else set(a.club)):
            for comp in sorted(set(COMP.values())):
                chosen=games[games.season.eq(season)&games.club.eq(club)&games.competition.eq(comp)]
                matrix.append(dict(season=season,club=club,competition=comp,observed_team_games=len(chosen),
                    complete_xi_games=int(chosen.complete_xi.sum()),
                    status='Recorded observations only; complete season participation not certified'if len(chosen)else'Not Available: no reliable observation; not evidence of zero participation'))
    pd.DataFrame(matrix).to_csv(OUT/'all_club_competition_coverage.csv',index=False)
    pd.DataFrame(beforeafter).to_csv(OUT/'pl_before_after_recorded_competitions.csv',index=False)
    gates=dict(A='Existing frozen MM reference reproduced; no new model',
        B='Not Available as complete all-competition MM: 2024 publication times are proxies; 2025 FA Cup absent, quarantined/missing cup games and player versions',
        C='Not Available: verified as-of future schedules, tie states, fixture phases, opponent ratings and importance calibration are incomplete',
        D_start='Not Available: same importance input blockers; no invented weights',
        D_duration='Not Available: same importance input blockers; no fabricated significance',
        recorded_workload='Retrospective lower bound, never silently called complete or substituted into forecast',
        causal_importance='Not established: observed competition/rest associations are not causal importance effects')
    reference=pd.read_csv(ROOT/'analysis/results/mm-all-clubs-20261016/club_metrics.csv')
    reference=reference[reference.phase.eq('evaluation_reused')&reference.model.eq('role_chance_return_duration')]
    reference['B_mae']=np.nan;reference['C_mae']=np.nan;reference['D_start_mae']=np.nan;reference['D_duration_mae']=np.nan
    reference['new_simulation_status']='Not Available: see source gates; A is frozen reference, not a new experiment'
    from individual_mm_evidence import load_frame
    from validate_mm_all_clubs import metrics
    frozen=load_frame(ROOT/'analysis/results/role-injury-mm-20261016/predictions.npz')
    af=frozen[frozen['mode'].eq('role_chance_return_duration') & (frozen.season.eq('2025-26')|frozen.gw.ge(22))]
    for row in reference.itertuples():
        checked=metrics(af[af.season.eq(row.season)&af.team_id.eq(row.team_id)])
        if abs(checked['minute_mae']-row.minute_mae)>1e-12:raise ValueError('Frozen A club replay differs')
    a_replay=metrics(af)
    reference.to_csv(OUT/'mm_ablation_availability_all40clubs.csv',index=False)
    report=dict(audit24=audit24,audit25=audit25,observations=len(players),team_games=len(games),
        complete_xis=int(games.complete_xi.sum()),event_interval_games=int(games.intervals_valid.sum()),
        coverage=summary.to_dict('records'),controlled_turnover_association=association,A_frozen_replay=a_replay,mm_gates=gates,locked_model_active=False,
        pm_ts_chips_points_not_run=True,source_ingestion_certified=False,
        important_limits=['Current complete XI does not prove chronological calendar completeness',
            'Recorded-next-fixture and rest-after are hindsight descriptions, NOT deadline-known features',
            'Nonstarter positive minutes counts observed entries; starter minutes<90 does not prove an exit substitution',
            'No arbitrary importance weight, missing workload zero-fill or current payload relabeling'])
    save_json(OUT/'rotation_report.json',report)
    inputs=[RAW24/'all_competition_player_observations.jsonl.gz',RAW24/'all_competition_match_actuals.jsonl.gz',
        RAW25/'SOURCE_MANIFEST.json',ROOT/'analysis/results/independent-europe-audit/workload_quarantine.csv',
        ROOT/'analysis/results/role-injury-mm-20261016/predictions.npz',
        ROOT/'analysis/results/mm-all-clubs-20261016/club_metrics.csv']+sorted(RAW25.glob('GW*/*.csv'))
    save_json(OUT/'rotation_manifest.json',dict(code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs},
        source_artifacts=[dict(run=38935549983,artifact=12061071746,sha256='fb331f934a747fe6c0eef7e3a9523c20e5b46f4f486a27b39de6e9184b1c71b6'),dict(run=38937294291,artifact=12060963430,sha256='abd90223836cb70a32562b09a050d493b7d11cbb7c931887d618d4961b145acd')]))
    outputs=['team_match_rotation.csv','individual_recorded_workload.csv.gz','club_competition_summary.csv',
        'pl_before_after_recorded_competitions.csv','all_club_competition_coverage.csv',
        'controlled_turnover_association_predictions.csv','controlled_turnover_association.json',
        'mm_ablation_availability_all40clubs.csv','rotation_report.json','rotation_manifest.json']
    contents={}
    for name in outputs:
        raw=(OUT/name).read_bytes();content=gzip.decompress(raw)if name.endswith('.gz')else raw
        contents[name]=dict(content_sha256=hashlib.sha256(content).hexdigest(),content_bytes=len(content))
    save_json(OUT/'rotation_content_manifest.json',contents)
    print('Observed MM rotation audit complete:',len(players),'player rows;',len(games),'team games;',int(games.complete_xi.sum()),'complete XI; event timing games',int(games.intervals_valid.sum()))


if __name__=='__main__':main()
