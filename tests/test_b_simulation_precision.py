import copy,gzip,json
from pathlib import Path
import numpy as np
import pytest
from b_simulation_precision import fixture_offset,resolution,browser_summary
from pm_preview_distributions import simulate_with_distributions
from fpl_v1_1_model.forecast_snapshot import seal_forecast,require_snapshot
from b_chain_contract import validate_forecast
from test_b_event_conservation import fixture

def test_precision_budgets_and_identity_seed_ignore_batch_order():
    assert resolution()==2000
    assert resolution('validation')==resolution('close')==10000
    assert fixture_offset('fx','2026-27')==dict((f,fixture_offset(f,'2026-27'))for f in ['other','fx'])['fx']
    assert fixture_offset('fx','2026-27')!=fixture_offset('fx','2025-26')
    with pytest.raises(ValueError):resolution('close',61)

def test_preallocated_recorder_preserves_longer_N_prefix_without_rng_change():
    inp,_=fixture();short=simulate_with_distributions(inp,n=400,seed=337,include_samples=True);long=simulate_with_distributions(inp,n=2000,seed=337,include_samples=True)
    for pid in short:
        for name in ['points','minutes']:assert short[pid]['scenarios'][name]==long[pid]['scenarios'][name][:400]
        assert np.mean(long[pid]['scenarios']['points'])==long[pid]['xPts']
        assert long[pid]['distribution']['xp_mcse']==pytest.approx(np.std(long[pid]['scenarios']['points'],ddof=1)/np.sqrt(2000))

def test_browser_transport_keeps_sealed_backend_and_same_point_means():
    base=Path('analysis/results/systematic-precision-audit-20261101/prospective');f=json.loads(gzip.decompress(next(base.glob('forecast-*.json.gz')).read_bytes()));before=copy.deepcopy(f);short=browser_summary(f)
    assert before==f
    require_snapshot(f);validate_forecast(f)
    assert short['forecast_sha256']==f['forecast_sha256']
    assert short['transport']['canonical_forecast_sha256']==f['forecast_sha256']
    for a,b in zip(short['players'],f['players']):
        for x,y in zip(a['weeks'],b['weeks']):
            assert 'scenarios'not in x and y['scenarios']
            assert x['xpts']==y['xpts']
    assert len(json.dumps(short))<len(json.dumps(f))*.4
    with pytest.raises(ValueError):validate_forecast(short) # Summary never enters TS.
