"""Isolated unified B worker; production manager_job.py is unchanged."""
import json
import sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from b_chain_contract import VERSION,validate_forecast
from b_preview_ts import preview_scoring
from run_live_locked_ts import run,project,parse_state


def calculate(forecast,raw):
    validate_forecast(forecast)
    from service.manager_job import calculate as original_calculate
    with preview_scoring(forecast) as scorer:
        result=original_calculate(forecast,raw)
    result.update(computed_at=pd.Timestamp.now(tz='UTC').isoformat(),calculation_runtime='B_unified_python',
        forecast_variant=VERSION,chain_version=VERSION,
        scoring_contract='PM shared draws: legal autosubs and conditional captain fallback',
        reason='Six-GW B MM→PM→TS: original transfer search, weights and hit costs; expected score includes legal automatic substitutions and captain fallback from the same PM draws.',
        validation_only=raw.get('validation_only')is True)
    return result


if __name__=='__main__':
    directory=Path(sys.argv[1]);body=json.loads((directory/'input.json').read_text())
    result=calculate(body['forecast'],body['state'])
    (directory/'result.json').write_text(json.dumps(result,allow_nan=False))
