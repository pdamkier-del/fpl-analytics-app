"""Summarize a completed isolated conversion replay; never publish models."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', default='analysis/results/general-conversion-20261020')
    args = parser.parse_args()
    root = Path(args.root)
    rows, evidence = [], []
    for season, expected in (('2024-25', 171), ('2025-26', 330)):
        path = root / f'{season}_report.json'
        report = json.loads(path.read_text())
        if report['fixtures'] != expected or report['draws'] != 400 or not report['original_exact']:
            raise ValueError('Incomplete/non-reference replay')
        result = report['results']
        reference_path = Path('analysis/results/player-pm-v2-20261015') / f'{season}_locked_report.json'
        reference = json.loads(reference_path.read_text())['results']['points']['metrics']['original']
        original = result['metrics']['original']
        if original['rows'] != reference['rows'] or any(
            abs(original[k] - reference[k]) > 1e-12 for k in ('mae', 'rmse', 'bias')
        ):
            raise ValueError('Original historical evaluation metrics changed')
        for mode, values in result['metrics'].items():
            rows.append(dict(season=season, mode=mode, rows=values['rows'],
                             xp_mae=values['mae'], xp_rmse=values['rmse'], xp_bias=values['bias'],
                             played_xp_mae=values['played']['mae'],
                             goal_log_loss=values['goals']['binary_log_loss'],
                             assist_log_loss=values['fpl_assists']['binary_log_loss'],
                             goal_brier=values['goals']['brier'],
                             assist_brier=values['fpl_assists']['brier'],
                             goal_bias=values['goals']['bias'], assist_bias=values['fpl_assists']['bias'],
                             xp_mae_delta=result['paired']['point_abs_error'][mode]['delta'],
                             xp_mae_delta_ci=result['paired']['point_abs_error'][mode]['fixture_bootstrap_95_ci']))
        for name in (f'{season}_report.json', f'{season}_predictions.csv.gz', f'{season}_prepared.jsonl.gz'):
            p = root / name
            evidence.append(dict(file=name, sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    consistent = [mode for mode in ('individual', 'receivers', 'combined')
                  if all(r['xp_mae_delta'] < 0 for r in rows if r['mode'] == mode)]
    result = dict(classification='COMPLETED_GENERAL_CONVERSION_REPLAY_NOT_PROMOTED',
                  fixtures=501, arms=4, draws_per_fixture_arm=400, match_draws=801600,
                  historical_original_metrics_reproduced=True,
                  consistent_point_MAE_gain_candidates=consistent, metrics=rows, files=evidence,
                  decision='No automatic promotion. Inspect consistency, paired intervals, event calibration and subgroups; reused seasons are not independent validation.',
                  production_changed=False, promotion_allowed=False)
    (root / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
