"""Execute original Phase 5Y runner with recovered, checksum-verified inputs.

Unused analytic cold-start imports are omitted because phase5q reads already
frozen forecasts. No decision functions, transfer rules or chip rules are edited.
"""
import ast
import hashlib
import gzip
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'work/legacy-season-runtime'
OUT = ROOT / 'analysis/results/legacy-season-technical-replay-v1'

def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / 'original_runner.py').write_bytes((OUT / 'original_runner.py').read_bytes())
    for item in json.loads((OUT / 'runtime_input_manifest.json').read_text()):
        packed = []
        for part in item['parts']:
            data = (OUT / part['path']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == part['sha256']
            packed.append(data)
        data = gzip.decompress(b''.join(packed))
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        target = RUNTIME / item['runtime_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    legacy = ROOT / 'analysis/results/legacy-rolling-recovery-v1'
    forecast = next(x for x in json.loads((legacy / 'manifest.json').read_text())['outputs']
                    if x['name'] == 'player_gw_forecasts')
    data = gzip.decompress(b''.join((legacy / p['path']).read_bytes() for p in forecast['parts']))
    assert hashlib.sha256(data).hexdigest() == forecast['uncompressed_sha256']
    target = RUNTIME / 'outputs/v1_1/phase5t_rolling_reference/rolling_phase5q_forecasts.csv'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    unused = RUNTIME / 'outputs/backtest/rolling_predictions.csv'
    unused.parent.mkdir(parents=True, exist_ok=True)
    unused.write_text('backtest_season\n')
    settings = dict(FPL_REPLAY_RESUME='1', FPL_REPLAY_FORECAST='phase5q', FPL_TRANSFER_POLICY='simple_3gw',
                    FPL_CHIP_POLICY='joint_sequence', FPL_HIT_UNCERTAINTY_BUFFER='2.0',
                    FPL_MANUAL_TC_GWS='13,33',
                    FPL_MANUAL_EARLY_CHIPS='2:free_hit,3:wildcard,4:bench_boost',
                    FPL_REPLAY_OUT=str(OUT))
    os.environ.update(settings)
    source = OUT / 'original_runner.py'
    assert source.read_bytes() == (RUNTIME / 'original_runner.py').read_bytes()
    history = RUNTIME / 'data/cache/history/2025-26/gws/merged_gw.csv'
    assert hashlib.sha256(history.read_bytes()).hexdigest() == '0d09f1f1cb1b5520ec8e2f25238aa652efe2a263d8ca7cb2b6538b27bf86727d'
    tree = ast.parse(source.read_text())
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and node.module in ('fpl_xpts.backtest', 'fpl_xpts.data'))]
    context = dict(__file__=str(RUNTIME / 'original_runner.py'), __name__='isolated_original_runner')
    exec(compile(tree, str(source), 'exec'), context)
    context['main']()

if __name__ == '__main__':
    main()
