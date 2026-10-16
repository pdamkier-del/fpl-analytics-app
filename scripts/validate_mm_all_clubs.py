#!/usr/bin/env python3
"""All-club MM-only frozen walk-forward evaluation and isolated duration tests.

No production imports are edited. No PM, TS, chips or points are executed.
Return/short-stint labels describe evidence and outcomes, never medical causes.
"""
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from individual_mm_evidence import load_frame
from validate_mm_probability_robustness import paired_rows, losses

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'analysis/results/role-injury-mm-20261016'
OUT = ROOT/'analysis/results/mm-all-clubs-20261016'
KEY = ['season', 'fixture_uuid', 'player_uuid']
FIVE = ['original', 'role', 'role_news_projected', 'role_source_chance',
        'role_chance_return_duration']
EXTRA = ['role_return_carry', 'role_return_duration',
         'news_all_starter_duration', 'chance_all_starter_duration']
METRICS = ['minute_mae', 'minute_rmse', 'start_brier', 'start_log_loss',
           'appearance_brier', 'appearance_log_loss', 'minute_bias']


def write_json(path, obj):
    raw = (json.dumps(obj, indent=2, allow_nan=False, default=str)+'\n').encode()
    path.write_bytes(raw)
    path.with_suffix(path.suffix+'.gz').write_bytes(gzip.compress(raw, mtime=0))


def metrics(f):
    if not len(f):
        return dict(rows=0, status='Not Available: no matched observations')
    value = losses(f).mean(0)
    value[1] = np.sqrt(value[1])
    play = f.p+(1-f.p)*f.q
    started, sub = f.y.eq(1), f.y.eq(0) & f.minutes.gt(0)
    result = dict(zip(METRICS[:6], map(float, value)))
    result.update(rows=len(f), fixtures=int(f.fixture_uuid.nunique()),
        gameweeks=int(f.gw.nunique()), minute_bias=float((f.x-f.minutes).mean()),
        start_bias=float((f.p-f.y).mean()), appearance_bias=float((play-f.minutes.gt(0)).mean()),
        false_zero_minutes=int((f.x.eq(0) & f.minutes.gt(0)).sum()),
        false_zero_start=int((f.p.eq(0) & started).sum()),
        false_zero_appearance=int((play.eq(0) & f.minutes.gt(0)).sum()),
        starter_duration_mae=float(abs(f.loc[started, 's']-f.loc[started, 'minutes']).mean()) if started.any() else None,
        starter_duration_bias=float((f.loc[started, 's']-f.loc[started, 'minutes']).mean()) if started.any() else None,
        cameo_duration_mae=float(abs(f.loc[sub, 'c']-f.loc[sub, 'minutes']).mean()) if sub.any() else None,
        expected_starts=float(f.p.sum()), actual_starts=int(f.y.sum()),
        role_duration_change=float((f.s-f.reference_s).mean()) if 'reference_s' in f else 0.)
    return result


def temporal_ci(candidate, baseline, grid, draws=1000, length=4):
    if not len(candidate):
        return dict(status='Not Available: no paired cases', metrics={})
    a, b = paired_rows(candidate, baseline)
    weeks = list(grid)
    if len(weeks) < length or any(np.diff(weeks) != 1):
        raise ValueError('Expected complete consecutive calendar-GW grid')
    # Blank club gameweeks remain empty calendar blocks, never compressed out.
    z = pd.DataFrame(np.c_[losses(a), a.x-a.minutes, losses(b), b.x-b.minutes])
    z['gw'] = a.gw.to_numpy()
    sums = z.groupby('gw').sum().reindex(weeks, fill_value=0).to_numpy()
    counts = a.groupby('gw').size().reindex(weeks, fill_value=0).to_numpy()
    occupied = int((counts > 0).sum())
    if occupied < 8:
        ma, mb = metrics(a), metrics(b)
        return dict(status='Not Available: fewer than 8 populated GW blocks', populated_gws=occupied,
                    rows=len(a), metrics={k:dict(delta=float(ma[k]-mb[k]), interval95=None) for k in METRICS})
    rng = np.random.default_rng(20261016)
    starts = rng.integers(len(weeks), size=(draws, int(np.ceil(len(weeks)/length))))
    ix = ((starts[:, :, None]+np.arange(length)) % len(weeks)).reshape(draws, -1)[:, :len(weeks)]
    den = counts[ix].sum(1)
    good = den > 0
    if not good.any():
        raise ValueError('No populated bootstrap draws')
    sampled = sums[ix[good]].sum(1)/den[good, None]
    sampled[:, 1] = np.sqrt(sampled[:, 1])
    sampled[:, 8] = np.sqrt(sampled[:, 8])
    ma, mb = metrics(a), metrics(b)
    return dict(rows=len(a), populated_gws=occupied, calendar_gws=len(weeks),
                block_length=length, valid_draws=int(good.sum()),
                metrics={k:dict(delta=float(ma[k]-mb[k]),
                interval95=np.quantile(sampled[:, j]-sampled[:, j+7], [.025, .975]).tolist()) for j, k in enumerate(METRICS)},
                warning='Circular moving-GW-block bootstrap; few effective blocks; reused periods; no multiplicity or source-error correction')


def combined_ci(candidate, baseline, draws=1000, length=4):
    """Resample within each season independently; combine row-weighted losses."""
    totals, denominators = None, None
    for i, season in enumerate(['2024-25', '2025-26']):
        a, b = paired_rows(candidate[candidate.season.eq(season)], baseline[baseline.season.eq(season)])
        grid = list(range(22 if season == '2024-25' else 6, 39))
        values = pd.DataFrame(np.c_[losses(a), a.x-a.minutes, losses(b), b.x-b.minutes])
        values['gw'] = a.gw.to_numpy()
        sums = values.groupby('gw').sum().reindex(grid, fill_value=0).to_numpy()
        counts = a.groupby('gw').size().reindex(grid, fill_value=0).to_numpy()
        rng = np.random.default_rng(20261016+i)
        starts = rng.integers(len(grid), size=(draws, int(np.ceil(len(grid)/length))))
        ix = ((starts[:, :, None]+np.arange(length)) % len(grid)).reshape(draws, -1)[:, :len(grid)]
        value, den = sums[ix].sum(1), counts[ix].sum(1)
        totals = value if totals is None else totals+value
        denominators = den if denominators is None else denominators+den
    sampled = totals/denominators[:, None]
    sampled[:, 1], sampled[:, 8] = np.sqrt(sampled[:, 1]), np.sqrt(sampled[:, 8])
    ma, mb = metrics(candidate), metrics(baseline)
    return dict(season_stratified=True, block_length=length, draws=draws,
        metrics={k:dict(delta=float(ma[k]-mb[k]), interval95=np.quantile(sampled[:, j]-sampled[:, j+7], [.025, .975]).tolist()) for j, k in enumerate(METRICS)},
        warning='Row-weighted combination; seasons resampled independently; historical periods reused, not independent validation')


def verify_inputs(f, core, source):
    b = f[f['mode'].eq('original')].copy()
    if b.duplicated(KEY).any() or core.duplicated(KEY).any():
        raise ValueError('Duplicate canonical observation')
    joined = b.merge(core, on=KEY, validate='one_to_one', suffixes=('', '_core'), indicator=True)
    if not joined['_merge'].eq('both').all():
        raise ValueError('Missing frozen/Core identity')
    for col, other in [('team_id', 'team_id_core'), ('gw', 'gw_core'), ('minutes', 'minutes_core'), ('y', 'started')]:
        if not np.array_equal(joined[col], joined[other]):
            raise ValueError('Frozen/Core disagreement: '+col)
    kick = pd.to_datetime(joined.kickoff_at, utc=True, format='mixed')
    cut = pd.to_datetime(joined.cutoff, utc=True, format='mixed')
    if not kick.gt(cut).all():
        raise ValueError('Target kickoff not after deadline')
    for (_, _), mode in f.groupby(['season', 'mode']):
        ref = b[b.season.eq(mode.season.iloc[0])]
        paired_rows(mode, ref)
    news = b[b.news_eligible]
    clock = pd.to_datetime(news.news_effective_at, utc=True, format='mixed')
    if not clock.lt(pd.to_datetime(news.cutoff, utc=True, format='mixed')).all():
        raise ValueError('News at/after cutoff')
    if source.duplicated(['season', 'gw', 'player_uuid']).any():
        raise ValueError('Ambiguous source identity')
    return dict(canonical_rows=len(b), frozen_model_arms=int(f['mode'].nunique()),
        all_core_minutes_starts_clubs_gws_match=True, all_target_kickoffs_after_cutoff=True,
        all_eligible_news_strictly_predeadline=True, historical_publication_clock='Inherited kickoff+3/4h proxy for actual outcomes; NOT fully certified',
        injuries_and_tactical_unknowns_not_imputed=True)


def descriptive_history(b, core):
    """Prior-only groups, not fitted prediction features or injury diagnoses."""
    eligible = b[b.news_eligible & b.news_state.isin(['AVAILABLE', 'RETURNED_AVAILABLE'])][KEY]
    verified = core.merge(eligible, on=KEY, validate='one_to_one')
    verified = verified[verified.started.eq(1)].copy()
    verified['known_at'] = pd.to_datetime(verified.kickoff_at, utc=True, format='mixed') + pd.to_timedelta(np.where(verified.season.eq('2025-26'), 3, 4), unit='h')
    histories = {(s, p, int(t)): g.sort_values('known_at') for (s, p, t), g in verified.groupby(['season', 'player_uuid', 'team_id'])}
    rows = []
    for r in b.to_dict('records'):
        h = histories.get((r['season'], r['player_uuid'], int(r['team_id'])))
        past = h[h.known_at.lt(pd.Timestamp(r['cutoff']))] if h is not None else pd.DataFrame()
        mins = past.minutes.tolist() if len(past) else []
        rows.append(dict(**{k:r[k] for k in KEY},
            prior_three_full_starts=len(mins) >= 3 and all(m == 90 for m in mins[-3:]),
            single_short_after_three_full=len(mins) >= 4 and all(m == 90 for m in mins[-4:-1]) and mins[-1] < 60,
            verified_available_prior_starts=len(mins),
            latest_prior_known_at=str(past.known_at.max()) if len(past) else None))
    return pd.DataFrame(rows)


def return_trajectories(b):
    """Scheduled and actually-played matches after source selection return.

    This is an evaluation cohort. Actual appearances never enter forecasts.
    A new sourced medical OUT or club move resets the episode.
    """
    rows = []
    for _, g in b.groupby(['season', 'player_uuid'], sort=False):
        active, scheduled, played, last_event, club = None, 0, 0, None, None
        for r in g.sort_values(['cutoff', 'kickoff_at', 'fixture_uuid']).to_dict('records'):
            current = int(r['team_id'])
            if club != current or r['news_medical_out']:
                active, scheduled, played = None, 0, 0
            club = current
            event = (r['cutoff'], current)
            if r['news_medical_return'] and event != last_event:
                active, scheduled, played, last_event = str(event), 0, 0, event
            if active:
                scheduled += 1
                if r['minutes'] > 0:
                    played += 1
            rows.append(dict(**{k:r[k] for k in KEY}, return_episode=active,
                scheduled_return_match=scheduled if active and scheduled <= 3 else 0,
                played_return_match=played if active and r['minutes'] > 0 and played <= 3 else 0))
    return pd.DataFrame(rows)


def component_problem(g):
    y, m, p, s, q, c = [g[x].to_numpy(float) for x in ['y', 'minutes', 'p', 's', 'q', 'c']]
    components = np.c_[(p-y)*(s-q*c), y*(s-m), (1-y)*(q-(m > 0))*c, (1-y)*(m > 0)*(c-m)]
    if not np.allclose(components.sum(1), g.x-g.minutes, atol=1e-9):
        raise ValueError('Minute component reconciliation failed')
    labels = ['start_selection', 'starter_duration', 'cameo_selection', 'cameo_duration']
    mean = np.abs(components).mean(0)
    return dict(largest_component=labels[int(mean.argmax())],
                component_absolute_magnitudes=dict(zip(labels, map(float, mean))),
                warning='Algebraic component magnitudes overlap/cancel; not additive MAE or causal explanations')


def make_arms(f):
    arms = {name: f[f['mode'].eq(name)].copy() for name in FIVE+EXTRA[:2]}
    for season in ['2024-25', '2025-26']:
        frozen = load_frame(ROOT/f'work/mm-source/{season}_candidates.npz')
        duration = frozen[frozen['mode'].eq('role_start_duration')][KEY+['s']].rename(columns={'s':'existing_role_s'})
        for name, reference in [('news_all_starter_duration', 'role_news_projected'),
                                ('chance_all_starter_duration', 'role_source_chance')]:
            base = arms[reference][arms[reference].season.eq(season)]
            new = base.merge(duration, on=KEY, validate='one_to_one')
            if len(new) != len(base):
                raise ValueError('Missing frozen duration ablation')
            new['reference_s'] = new.s
            new['s'] = new.existing_role_s
            new['x'] = new.p*new.s+(1-new.p)*new.q*new.c
            new['mode'] = name
            arms[name] = pd.concat([arms.get(name, pd.DataFrame()), new], ignore_index=True)
    return arms


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = load_frame(BASE/'predictions.npz')
    source = pd.read_csv(BASE/'source_backed_news.csv.gz', low_memory=False)
    with sqlite3.connect(ROOT/'work/core.sqlite3') as c:
        core = pd.read_sql_query('SELECT season,gw,fixture_uuid,player_uuid,team_id,kickoff_at,started,minutes FROM player_fixture_observations WHERE is_final=1', c)
        names = dict(c.execute('SELECT player_uuid,canonical_name FROM players'))
    audit = verify_inputs(frozen, core, source)
    b = frozen[frozen['mode'].eq('original')].merge(core[KEY+['kickoff_at']], on=KEY, validate='one_to_one')
    history = descriptive_history(b, core)
    trajectory = return_trajectories(b)
    metadata = history.merge(trajectory, on=KEY, validate='one_to_one').merge(core[KEY+['kickoff_at']], on=KEY, validate='one_to_one')
    sourcecols = ['season', 'gw', 'player_uuid', 'raw_status', 'raw_news', 'source_url', 'news_added']
    arms = {name: a.merge(metadata, on=KEY, validate='one_to_one').merge(source[sourcecols], on=['season', 'gw', 'player_uuid'], how='left', validate='many_to_one') for name, a in make_arms(frozen).items()}
    clubnames = {(r['season'], int(r['team_id'])):r['club'] for r in pd.read_csv(BASE/'coverage.csv').to_dict('records')}
    reports, clubrows, grouprows, worstrows, overallrows, ablationrows = {}, [], [], [], [], []
    for season in ['2024-25', '2025-26']:
        scopes = [('development_reused', 6, 21), ('evaluation_reused', 22, 38)] if season == '2024-25' else [('evaluation_reused', 6, 38)]
        for phase, low, high in scopes:
            e = {name: a[a.season.eq(season) & a.gw.between(low, high)].copy() for name, a in arms.items()}
            grid = range(low, high+1)
            key = season+':'+phase
            for name, a in e.items():
                overallrows.append(dict(season=season, phase=phase, model=name, **metrics(a)))
            clubs = []
            for team, original in e['original'].groupby('team_id'):
                club = clubnames[(season, int(team))]
                group_arms = {name: a[a.team_id.eq(team)] for name, a in e.items()}
                table = {}
                for name, a in group_arms.items():
                    mm = metrics(a)
                    interval = temporal_ci(a, original, grid)
                    row = dict(season=season, phase=phase, club=club, team_id=int(team), model=name, **mm)
                    for metric, v in interval['metrics'].items():
                        row[metric+'_delta_vs_original'] = v['delta']
                        row[metric+'_delta_ci95_low'] = v['interval95'][0] if v['interval95'] else None
                        row[metric+'_delta_ci95_high'] = v['interval95'][1] if v['interval95'] else None
                    clubrows.append(row)
                    table[name] = dict(metrics=mm, vs_original=interval)
                    groups = {label: a[a.player_type.eq(label)] for label in ['regular', 'rotation_or_short_history', 'reserve']}
                    groups.update(prior_three_full_starts=a[a.prior_three_full_starts], single_short_after_three_full=a[a.single_short_after_three_full], source_medical_return=a[a.news_medical_return], source_medical_out=a[a.news_medical_out], source_unknown=a[~a.news_eligible], actually_played_evaluation_only=a[a.minutes.gt(0)], actually_started_evaluation_only=a[a.y.eq(1)])
                    for n in [1, 2, 3]:
                        groups['scheduled_return_'+str(n)] = a[a.scheduled_return_match.eq(n)]
                        groups['played_return_'+str(n)] = a[a.played_return_match.eq(n)]
                    table[name]['groups'] = {}
                    for label, cases in groups.items():
                        ids = cases[KEY]
                        baseline = original.merge(ids, on=KEY, validate='one_to_one')
                        score = metrics(cases)
                        ci = temporal_ci(cases, baseline, grid)
                        table[name]['groups'][label] = dict(metrics=score, vs_original=ci)
                        grouprows.append(dict(season=season, phase=phase, club=club, team_id=int(team), model=name, group=label, **score,
                            minute_mae_delta_vs_original=ci['metrics'].get('minute_mae', {}).get('delta'),
                            minute_mae_ci95=json.dumps(ci['metrics'].get('minute_mae', {}).get('interval95')),
                            ci_status=ci.get('status', 'Available; few effective time blocks')))
                    top = a.assign(abs_error=abs(a.x-a.minutes)).nlargest(10, 'abs_error')
                    for r in top.to_dict('records'):
                        verified = []
                        if r['news_eligible'] and r['news_state'] in ['OUT', 'SUSPENDED'] and r['minutes'] > 0:
                            verified.append('Source-status/outcome conflict; archived source existed before cutoff')
                        if r['news_medical_return']:
                            verified.append('First source AVAILABLE after documented FPL medical flag; not clinical clearance')
                        if r['scheduled_return_match']:
                            verified.append('Scheduled match '+str(r['scheduled_return_match'])+' after source selection return')
                        cause = 'start_selection' if (r['y'] == 1 and r['p'] < .5) or (r['y'] == 0 and r['p'] >= .5) else 'duration_or_appearance_error'
                        worstrows.append(dict(season=season, phase=phase, club=club, model=name, player=names.get(r['player_uuid'], 'Not Available'),
                            **{k:r[k] for k in KEY if k != 'season'}, gw=int(r['gw']), cutoff=r['cutoff'], kickoff_at=r['kickoff_at'],
                            actual_minutes=r['minutes'], expected_minutes=r['x'], abs_error=r['abs_error'], p_start=r['p'],
                            actual_started=r['y'], prior_three_full_starts=r['prior_three_full_starts'],
                            single_short_after_three_full=r['single_short_after_three_full'],
                            verified_available_prior_starts=r['verified_available_prior_starts'], latest_prior_known_at=r['latest_prior_known_at'],
                            p_appearance=r['p']+(1-r['p'])*r['q'], starter_minutes=r['s'], news_state=r['news_state'],
                            raw_news=r['raw_news'], source_url=r['source_url'], news_effective_at=r['news_effective_at'],
                            verified_observations='; '.join(verified) if verified else 'No verified medical/tactical explanation',
                            error_component=cause, hypothesis='Rotation, substitution cause, coach/tactical change NOT established'))
                problem = component_problem(group_arms['role_chance_return_duration'])
                clubreport = dict(club=club, team_id=int(team), models=table, problem=problem,
                    source_unknown_rows=int((~original.news_eligible).sum()),
                    training_return_verified_rows=0,
                    tactical_change_causal_evidence='Not Available: no verified coach-change/causal event timeline used')
                clubs.append(clubreport)
            if len(clubs) != 20:
                raise ValueError('Not all 20 season clubs evaluated')
            clubs.sort(key=lambda c:c['models']['role_chance_return_duration']['metrics']['minute_mae'], reverse=True)
            # Exactly one component changed in each isolated comparison.
            pairs = [('role_source_chance', 'role_news_projected'),
                ('role_return_duration', 'role_news_projected'),
                ('role_return_carry', 'role_news_projected'),
                ('role_chance_return_duration', 'role_source_chance'),
                ('news_all_starter_duration', 'role_news_projected'),
                ('chance_all_starter_duration', 'role_source_chance')]
            ablations = {}
            for name, base in pairs:
                value = temporal_ci(e[name], e[base], grid)
                ablations[name+' vs '+base] = value
                ablationrows.append(dict(season=season, phase=phase, candidate=name, reference=base,
                    **{k+'_delta':v['delta'] for k, v in value['metrics'].items()},
                    minute_mae_ci95=json.dumps(value['metrics']['minute_mae']['interval95'])))
            reports[key] = dict(clubs_ranked=clubs, isolated_ablations=ablations)
            print('Completed', key, '20 clubs', len(e), 'MM arms', flush=True)
    combined, combined_intervals = {}, {}
    baseline_eval = arms['original'][arms['original'].season.eq('2025-26') | (arms['original'].season.eq('2024-25') & arms['original'].gw.ge(22))]
    for name, a in arms.items():
        eval_rows = a[a.season.eq('2025-26') | (a.season.eq('2024-25') & a.gw.ge(22))]
        combined[name] = metrics(eval_rows)
        combined_intervals[name] = combined_ci(eval_rows, baseline_eval)
    audit['input_sha256'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'predictions.npz', BASE/'source_backed_news.csv.gz', ROOT/'work/mm-source/2024-25_candidates.npz', ROOT/'work/mm-source/2025-26_candidates.npz']}
    audit['coverage_rows'] = pd.read_csv(BASE/'coverage.csv').to_dict('records')
    audit['protocol'] = dict(primary_five=FIVE, isolated_extra_arms=EXTRA, parameters_fitted=0,
        new_duration_arm='Only s replaced from frozen role_start_duration; p,q,c unchanged',
        return_label='Source-confirmed selection availability, NOT medical/training clearance',
        played_return_cohort='Retrospective evaluation only; never a forecast feature',
        descriptive_stint_groups='Three previous source-AVAILABLE 90-minute starts; short-reaction group adds a fourth most recent start under60min. Diagnostic thresholds, not forecast parameters.',
        prospective_validation='Not Available; all periods previously used in research',
        known_missing='GW1-5 forecasts, exact historical outcome publication times, medical clearance/training return dates, verified fixture-specific suspension expiry',
        pm_ts_chips_points_not_run=True, locked_model_active=False, promotion_allowed=False)
    pd.DataFrame(clubrows).to_csv(OUT/'club_metrics.csv', index=False)
    for name, rows in [('group_metrics', grouprows), ('top_errors', worstrows)]:
        pd.DataFrame(rows).to_csv(OUT/(name+'.csv.gz'), index=False, compression={'method':'gzip', 'mtime':0})
    pd.DataFrame(overallrows).to_csv(OUT/'overall_metrics.csv', index=False)
    pd.DataFrame(ablationrows).to_csv(OUT/'isolated_ablations.csv', index=False)
    write_json(OUT/'report.json', dict(audit=audit, combined_evaluation=combined, combined_intervals=combined_intervals, reports=reports))
    write_json(OUT/'summary.json', dict(audit=audit, combined_evaluation=combined, combined_intervals=combined_intervals,
        club_seasons_evaluated=40, development_club_slices=20, required_model_rows=200,
        total_club_model_phase_rows=len(clubrows), total_error_cases=len(worstrows)))
    manifest = dict(code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=audit['input_sha256'], pm_ts_chips_points_not_run=True,
        comparison='Exact decompressed content SHA256 for gzip files, exact bytes otherwise', files={})
    for name in ['club_metrics.csv', 'group_metrics.csv.gz', 'top_errors.csv.gz', 'overall_metrics.csv',
                 'isolated_ablations.csv', 'report.json.gz', 'summary.json']:
        raw = (OUT/name).read_bytes()
        content = gzip.decompress(raw) if name.endswith('.gz') else raw
        manifest['files'][name] = dict(content_sha256=hashlib.sha256(content).hexdigest(), content_bytes=len(content))
    write_json(OUT/'content_manifest.json', manifest)
    print('MM ONLY: no production change, no points/PM/TS/chips', flush=True)


if __name__ == '__main__':
    main()
