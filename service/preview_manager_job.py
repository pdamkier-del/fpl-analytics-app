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


def research_plan(forecast, raw, snapshot_at, baseline):
    """Chip-free PR66 candidate; only objective/beam weights change."""
    from dataclasses import replace, asdict
    from unittest.mock import patch
    from fpl_xpts import transfer_planner as planner
    from run_joint_fh_wc_stopping_replay import cfg
    from fpl_xpts import optimize
    config=cfg()
    if len(config.weights) != 6 or any(abs(w - .6 ** i) > 1e-12 for i, w in enumerate(config.weights)):
        raise ValueError('Unexpected frozen shortlist weights')
    if config.candidate_backend != 'fast_local' or config.discount_transfer_costs or config.hit_uncertainty_buffer != 1:
        raise ValueError('Unexpected frozen TS contract')
    meta,origin=project(forecast)
    gw=min(forecast['gws'])
    state=parse_state(raw,meta,gw,snapshot_at if snapshot_at is not None else forecast['data_asof'])
    prepare=planner._prepare_local_candidates
    generate=planner._fast_local_candidate_squads
    def suffix(gws):
        offset=gws[0]-gw
        if offset<0 or list(gws)!=list(range(gws[0],gws[0]+len(gws))):
            raise ValueError('Invalid shortlist horizon')
        result=config.weights[offset:offset+len(gws)]
        if len(result)!=len(gws): raise ValueError('Incomplete shortlist horizon')
        return result
    def prepare_fixed(meta,origin,gws,weights,top):
        return prepare(meta,origin,gws,suffix(gws),top)
    def generate_fixed(state,meta,origin,gws,weights,*settings):
        return generate(state,meta,origin,gws,suffix(gws),*settings)
    candidate=replace(config,weights=tuple(.9**i for i in range(len(config.weights))))
    with patch.object(planner,'_prepare_local_candidates',prepare_fixed),patch.object(planner,'_fast_local_candidate_squads',generate_fixed):
        plan=planner.plan_transfer_path(state,meta,origin,gw,candidate)
    if not plan.path or list(plan.horizon_gws)!=list(forecast['gws']):
        raise ValueError('Incomplete research plan')
    first = plan.first_action
    common = baseline['plan']['path'][0]
    if (first.gw, first.bank_before, first.free_transfers_before) != (common['gw'], common['bank_before'], common['free_transfers_before']):
        raise ValueError('TS start state disagreement')
    after=planner.clone_state(state)
    transfers=planner.execute_first_action(after,plan,meta)
    lineup=optimize.plan_squad(origin,list(after.squad),gw)
    return dict(schema='ts-v4.1-pr66-v1',status='complete',rho=.9,
        shortlist_rho=.6,chips_enabled=False,forecast_sha256=forecast['forecast_sha256'],
        manager_state_sha256=baseline['manager_state_sha256'],gw=gw,
        plan=asdict(plan),transfers=transfers,lineup=json.loads(lineup.rows.to_json(orient='records')))


def calculate(forecast,raw,*,snapshot_at=None):
    validate_forecast(forecast)
    from service.manager_job import calculate as original_calculate
    from b_snapshot_policy import manager_snapshot_context,POLICY
    context=manager_snapshot_context(forecast,raw,snapshot_at)if snapshot_at is not None else nullcontext()
    with context,preview_scoring(forecast) as scorer:
        result=original_calculate(forecast,raw)
        try:
            result['research_ts']=research_plan(forecast,raw,snapshot_at,result)
        except (ValueError, RuntimeError, KeyError, TypeError) as error:
            # Never substitute a second TS v3 result or discard a valid baseline.
            result['research_ts']={'schema':'ts-v4.1-pr66-v1','status':'unavailable','reason_code':type(error).__name__}
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
