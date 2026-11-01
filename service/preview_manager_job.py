"""Isolated unified B worker; production manager_job.py is unchanged."""
import json
import sys
from pathlib import Path
import pandas as pd
from contextlib import nullcontext
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts'),str(ROOT/'src')]
from b_chain_contract import VERSION,validate_forecast
from b_preview_ts import preview_scoring
from run_live_locked_ts import run,project,parse_state


def calculate(forecast,raw,*,snapshot_at=None):
    validate_forecast(forecast)
    from service.manager_job import calculate as original_calculate
    from b_snapshot_policy import manager_snapshot_context,POLICY
    context=manager_snapshot_context(forecast,raw,snapshot_at)if snapshot_at is not None else nullcontext()
    with context,preview_scoring(forecast) as scorer:
        result=original_calculate(forecast,raw)
    result.update(computed_at=pd.Timestamp.now(tz='UTC').isoformat(),calculation_runtime='B_unified_python',
        forecast_variant=VERSION,chain_version=VERSION,
        forecast_sha256=forecast['forecast_sha256'],
        scoring_contract='PM shared draws: legal autosubs and conditional captain fallback',
        reason='Six-GW B MM→PM→TS: original transfer search, weights and hit costs; expected score includes legal automatic substitutions and captain fallback from the same PM draws.',
        validation_only=raw.get('validation_only')is True)
    if snapshot_at is not None:
        result.update(forecast_policy=POLICY,decision_at=str(snapshot_at),
            model_asof=forecast['data_asof'],prices_asof=forecast['data_asof'],
            snapshot_warning='Planen bruger seneste validerede prognose og dens priser. Nyere skader og prisændringer indgår først efter en modelopdatering.')
    return result


if __name__=='__main__':
    directory=Path(sys.argv[1]);body=json.loads((directory/'input.json').read_text())
    from b_snapshot_policy import POLICY
    result=calculate(body['forecast'],body['state'],snapshot_at=pd.Timestamp.now(tz='UTC').isoformat()if body.get('forecast_policy')==POLICY else None)
    (directory/'result.json').write_text(json.dumps(result,allow_nan=False))
