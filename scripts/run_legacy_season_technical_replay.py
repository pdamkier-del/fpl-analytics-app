"""Execute original Phase 5Y runner with recovered, checksum-verified inputs.

Unused analytic cold-start imports are omitted because phase5q reads already
frozen forecasts. No decision functions, transfer rules or chip rules are edited.
"""
import ast
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'work/legacy-season-runtime'
OUT = ROOT / 'analysis/results/legacy-season-technical-replay-v1'

def main():
    settings = dict(FPL_REPLAY_FORECAST='phase5q', FPL_TRANSFER_POLICY='simple_3gw',
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
