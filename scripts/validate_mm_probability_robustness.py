#!/usr/bin/env python3
"""Read-only probability/serial-dependence audit of frozen MM predictions.

No fitting, forecast edits, medical imputation or PM/points/TS execution.
All slices are diagnostic reuse of the previous research evaluation periods.
"""
import hashlib
import gzip
import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from individual_mm_evidence import load_frame

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'analysis/results/role-injury-mm-20261016'
OUT = ROOT / 'analysis/results/mm-probability-robustness-20261016'
KEY = ['season', 'fixture_uuid', 'player_uuid']
ARMS = ['original', 'role', 'role_news_projected', 'role_source_chance',
        'role_return_carry', 'role_return_duration', 'role_chance_return_duration']
METRICS = ['minute_mae', 'minute_rmse', 'start_brier', 'start_log_loss',
           'appearance_brier', 'appearance_log_loss']


def probability_scores(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    if not len(p) or p.shape != y.shape or not np.isfinite(np.c_[p, y]).all():
        raise ValueError('Missing, mismatched or nonfinite probabilities/outcomes')
    if np.any((p < 0) | (p > 1)) or not np.isin(y, [0, 1]).all():
        raise ValueError('Illegal probability or nonbinary truth')
    # A declared endpoint with contrary outcome has infinite theoretical loss.
    # Finite reporting uses the same explicit numerical clip as the prior audit.
    pp = np.clip(p, 1e-12, 1 - 1e-12)
    bins = np.minimum((p * 10).astype(int), 9)
    rows = []
    for k in range(10):
        take = bins == k
        if take.any():
            rows.append(dict(bin=k, lower=k / 10, upper=(k + 1) / 10,
                             rows=int(take.sum()), forecast=float(p[take].mean()),
                             observed=float(y[take].mean())))
    return dict(rows=len(p), brier=float(np.mean((p-y)**2)),
                log_loss=float(-np.mean(y*np.log(pp)+(1-y)*np.log1p(-pp))),
                bias=float(np.mean(p-y)),
                ece_10_bins=float(sum(r['rows']*abs(r['forecast']-r['observed']) for r in rows)/len(p)),
                endpoint_contradictions=int(((p == 0) & (y == 1) | (p == 1) & (y == 0)).sum()),
                reliability=rows)


def losses(f):
    p = f.p.to_numpy(float)
    play = p + (1-p)*f.q.to_numpy(float)
    y = f.y.to_numpy(float)
    actual_play = f.minutes.gt(0).to_numpy(float)
    # Validation is shared with the scalar reliability report.
    probability_scores(p, y)
    probability_scores(play, actual_play)
    error = f.x.to_numpy(float)-f.minutes.to_numpy(float)
    p, play = np.clip(p, 1e-12, 1-1e-12), np.clip(play, 1e-12, 1-1e-12)
    return np.c_[abs(error), error**2, (p-y)**2,
                 -(y*np.log(p)+(1-y)*np.log1p(-p)), (play-actual_play)**2,
                 -(actual_play*np.log(play)+(1-actual_play)*np.log1p(-play))]


def paired_rows(candidate, baseline):
    if candidate.duplicated(KEY).any() or baseline.duplicated(KEY).any():
        raise ValueError('Duplicate canonical player-fixture')
    if len(candidate) != len(baseline):
        raise ValueError('Different candidate/baseline cohorts')
    a = candidate.sort_values(KEY).reset_index(drop=True)
    b = baseline.sort_values(KEY).reset_index(drop=True)
    for field in KEY + ['gw', 'cutoff', 'y', 'minutes', 'team_id']:
        if not np.array_equal(a[field].to_numpy(), b[field].to_numpy()):
            raise ValueError('Different paired identity, deadline or truth: '+field)
    if a.season.nunique() != 1:
        raise ValueError('Bootstrap each season separately')
    return a, b


def block_delta(candidate, baseline, block_length=4, draws=2000):
    a, b = paired_rows(candidate, baseline)
    la, lb = losses(a), losses(b)
    by = a.groupby('gw', sort=True).indices
    weeks = np.asarray(list(by))
    if len(weeks) < 2 or np.any(np.diff(weeks) != 1):
        raise ValueError('Need contiguous historical gameweeks')
    if block_length < 1 or block_length > len(weeks):
        raise ValueError('Illegal temporal block length')
    blocks = np.asarray([[len(ix)] + la[ix].sum(0).tolist() + lb[ix].sum(0).tolist()
                         for ix in by.values()])
    rng = np.random.default_rng(20261016)
    starts = rng.integers(len(weeks), size=(draws, int(np.ceil(len(weeks)/block_length))))
    # Circular moving blocks avoid underweighting the first/last gameweeks.
    # Wrapping is a resampling convention, never information used in a forecast.
    indexes = ((starts[:, :, None]+np.arange(block_length)) % len(weeks)).reshape(draws, -1)[:, :len(weeks)]
    sampled = blocks[indexes].sum(1)
    boot_a, boot_b = sampled[:, 1:7]/sampled[:, :1], sampled[:, 7:13]/sampled[:, :1]
    point_a, point_b = la.mean(0), lb.mean(0)
    boot_a[:, 1], boot_b[:, 1] = np.sqrt(boot_a[:, 1]), np.sqrt(boot_b[:, 1])
    point_a[1], point_b[1] = np.sqrt(point_a[1]), np.sqrt(point_b[1])
    return dict(rows=len(a), gameweeks=len(weeks), block_length=block_length,
                draws=draws, metrics={key: dict(delta=float(point_a[j]-point_b[j]),
                interval95=np.quantile(boot_a[:, j]-boot_b[:, j], [.025, .975]).tolist())
                for j, key in enumerate(METRICS)},
                warning='Diagnostic circular moving-GW-block bootstrap; few effective blocks, reused periods, no multiplicity correction or independent validation')


def evaluate(f):
    if not len(f):
        return dict(rows=0, status='Not Available: no observations')
    return dict(rows=len(f), minute_mae=float(abs(f.x-f.minutes).mean()),
                minute_rmse=float(np.sqrt(((f.x-f.minutes)**2).mean())),
                minute_bias=float((f.x-f.minutes).mean()),
                start=probability_scores(f.p, f.y),
                appearance=probability_scores(f.p+(1-f.p)*f.q, f.minutes.gt(0)))


def endpoint_cases(f):
    """Retrospective source/outcome conflicts; never a forecast feature."""
    zero = f[f['mode'].eq('role_news_projected') & f.minutes.gt(0) &
             f.p.eq(0) & f.q.eq(0)].copy()
    zero = zero[zero.season.eq('2025-26') | zero.gw.ge(22)]
    source = pd.read_csv(RESULT/'source_backed_news.csv.gz', low_memory=False)
    with sqlite3.connect(ROOT/'work/core.sqlite3') as c:
        times = pd.read_sql_query('SELECT season,fixture_uuid,player_uuid,kickoff_at '
                                  'FROM player_fixture_observations WHERE is_final=1', c)
    wanted = ['season', 'gw', 'player_uuid', 'player_name', 'raw_status', 'raw_news',
              'news_added', 'source_url', 'source_commit']
    zero = zero.merge(source[wanted], on=['season', 'gw', 'player_uuid'], validate='many_to_one')
    zero = zero.merge(times, on=KEY, validate='one_to_one')
    kick = pd.to_datetime(zero.kickoff_at, utc=True, format='mixed')
    cut = pd.to_datetime(zero.cutoff, utc=True, format='mixed')
    captured = pd.to_datetime(zero.news_effective_at, utc=True, format='mixed')
    zero['deadline_to_kickoff_hours'] = (kick-cut).dt.total_seconds()/3600
    zero['source_age_at_deadline_hours'] = (cut-captured).dt.total_seconds()/3600
    months = {name: i+1 for i, name in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}
    same = []
    for text, kickoff in zip(zero.raw_news, kick):
        match = re.search(r'Suspended until (\d{1,2}) ([A-Z][a-z]{2})\b', str(text))
        same.append(bool(match and months.get(match[2]) == kickoff.month and int(match[1]) == kickoff.day))
    zero['literal_suspension_day_month_matches_fixture'] = same
    zero['diagnosis'] = np.where(same,
        'GW-wide suspension cap applied to a fixture on the source day/month; no full expiry timestamp inferred',
        'Source flag and outcome disagree; cause not verified, no retrospective label repair')
    zero['evaluation_only'] = True
    fields = KEY + ['gw', 'player_name', 'team_id', 'cutoff', 'kickoff_at', 'minutes',
        'news_state', 'raw_status', 'raw_news', 'news_added', 'news_effective_at',
        'deadline_to_kickoff_hours', 'source_age_at_deadline_hours',
        'literal_suspension_day_month_matches_fixture', 'source_url', 'source_commit',
        'diagnosis', 'evaluation_only']
    return zero[fields].sort_values(KEY).reset_index(drop=True)


def main():
    path = RESULT/'predictions.npz'
    f = load_frame(path)
    output = dict(protocol=dict(read_only=True, fitted_parameters=0,
                  reused_periods_not_new_holdouts=True,
                  baseline_reference='PR #4 6d875a6; existing frozen walk-forward forecasts',
                  probability_clip=1e-12, bootstrap_seed=20261016,
                  source_chance_warning='An official FPL chance is not a guaranteed selection probability; no fit or medical posterior inferred',
                  pm_ts_chips_points_not_run=True), seasons={})
    calibration = []
    for season, g in f.groupby('season', sort=True):
        e = g[g.gw.ge(22)] if season == '2024-25' else g
        arms = {name: e[e['mode'].eq(name)].copy() for name in ARMS}
        for a in arms.values():
            paired_rows(a, arms['original'])
        overall = {name: evaluate(a) for name, a in arms.items()}
        for name, value in overall.items():
            for target in ['start', 'appearance']:
                calibration += [dict(season=season, model=name, target=target, **r)
                                for r in value[target]['reliability']]
        comparisons = {}
        for name, base in [('role_source_chance', 'role_news_projected'),
                           ('role_return_carry', 'role_news_projected'),
                           ('role_return_duration', 'role_news_projected'),
                           ('role_chance_return_duration', 'role_source_chance'),
                           ('role_source_chance', 'original')]:
            comparisons[name+' vs '+base] = {str(length): block_delta(arms[name], arms[base], length)
                                            for length in [1, 2, 4]}
        n = arms['role_news_projected']
        source_chance = []
        for chance, rows in n[n.news_eligible].groupby('news_chance', dropna=False):
            source_chance.append(dict(source_chance=None if pd.isna(chance) else float(chance),
                rows=len(rows), observed_start=float(rows.y.mean()),
                observed_appearance=float(rows.minutes.gt(0).mean()),
                zero_minutes=int(rows.minutes.eq(0).sum()),
                interpretation='Retrospective source stratum, not an availability ground truth label'))
        midpoint = (int(n.gw.min())+int(n.gw.max()))//2
        slices = {label: {name: evaluate(a[mask(a)]) for name, a in arms.items()}
                  for label, mask in [('earlier_evaluation_slice', lambda a: a.gw.le(midpoint)),
                                       ('later_evaluation_slice', lambda a: a.gw.gt(midpoint)),
                                       ('source_medical_selection_returns', lambda a: a.news_medical_return),
                                       ('source_out_but_actual_appearance', lambda a: a.news_medical_out & a.minutes.gt(0)),
                                       ('source_unknown', lambda a: ~a.news_eligible)]}
        output['seasons'][season] = dict(overall=overall, block_comparisons=comparisons,
            source_chance_strata=source_chance, diagnostic_slices=slices,
            slices_warning='Slices specified for follow-up diagnosis after observing research results, not independent holdouts',
            unverified_medical_clearance_or_training_dates_used=0)
    conflicts = endpoint_cases(f)
    output['endpoint_conflicts'] = dict(rows=len(conflicts),
        suspension_day_month_matches=int(conflicts.literal_suspension_day_month_matches_fixture.sum()),
        hard_endpoint_warning='Contradictory outcomes have infinite theoretical log-loss; displayed loss uses numerical clip, not a validated certainty claim',
        used_to_change_any_forecast=False)
    output['input_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    output['locked_model_active'] = False
    output['promotion_allowed'] = False
    OUT.mkdir(parents=True, exist_ok=True)
    conflicts.to_csv(OUT/'endpoint_conflicts.csv', index=False)
    encoded = (json.dumps(output, indent=2, allow_nan=False)+'\n').encode()
    (OUT/'report.json').write_bytes(encoded)
    (OUT/'report.json.gz').write_bytes(gzip.compress(encoded, mtime=0))
    pd.DataFrame(calibration).to_csv(OUT/'reliability.csv', index=False)
    print('Read-only MM probability and gameweek-block audit complete; no forecasts fitted or modified')


if __name__ == '__main__':
    main()
