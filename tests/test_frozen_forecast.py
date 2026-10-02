from pathlib import Path
import json
import numpy as np
import pandas as pd
from fpl_v1_1_model.frozen_forecast import predict_frozen,VARIANTS

ROOT=Path(__file__).resolve().parents[1]


def inputs():
    f=pd.read_csv(ROOT/'analysis/results/workload-v1/all_features.csv.gz')
    f=f[f.gw.between(22,23)].copy()
    models=json.load(open(ROOT/'analysis/results/workload-minutes-v1/frozen_models.json'))
    protocol=json.load(open(ROOT/'analysis/results/workload-minutes-v1/protocol.json'))
    return f,models,protocol['final_fit']['training_cutoff']


def test_frozen_predictor_matches_saved_predictions_without_outcomes():
    f,models,cutoff=inputs()
    saved=pd.read_csv(ROOT/'analysis/results/workload-minutes-v1/reused_holdout_diagnostic_predictions.csv.gz')
    actual_columns=[c for c in f if c.startswith('actual_') or c.endswith('_posthoc') or c in ['y','minutes','outcome_known_at']]
    clean=f.drop(columns=actual_columns)
    for variant in VARIANTS:
        result=predict_frozen(clean,models,cutoff,variant)
        pair=result.merge(saved[['fixture_uuid','player_uuid',variant+'_p_start',variant+'_xmins']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
        assert np.allclose(pair.p_start,pair[variant+'_p_start'],atol=1e-10)
        assert np.allclose(pair.expected_minutes,pair[variant+'_xmins'],atol=1e-9)
        assert not any(c in result for c in actual_columns)


def test_frozen_predictor_rejects_future_history_and_pretraining_cutoff():
    f,models,cutoff=inputs()
    for field,value in [('work_max_history_known_at',f.cutoff.iloc[0]),('cutoff','2025-01-01T00:00:00Z')]:
        bad=f.copy();bad.loc[bad.index[0],field]=value
        try:predict_frozen(bad,models,cutoff)
        except ValueError:pass
        else:raise AssertionError('Future/pre-training input accepted')


def test_frozen_predictor_rejects_partial_and_duplicate_rosters():
    f,models,cutoff=inputs();group=f[(f.fixture_uuid==f.fixture_uuid.iloc[0])&(f.team_id==f.team_id.iloc[0])]
    for bad in (group.iloc[:11],pd.concat([group,group.iloc[:1]],ignore_index=True)):
        try:predict_frozen(bad,models,cutoff)
        except ValueError:pass
        else:raise AssertionError('Invalid roster accepted')
