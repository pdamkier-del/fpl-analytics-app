"""Private worker adapter. Calls the unchanged original Python model."""
import json,sys,hashlib
from dataclasses import replace,asdict
from pathlib import Path
import pandas as pd
B_WC_HORIZON_SCHEMA='B-wildcard-followup-v1'
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from run_live_locked_ts import run,project,parse_state
from fpl_xpts.optimize import plan_squad
from fpl_xpts.transfer_planner import clone_state,execute_first_action,plan_transfer_path
from run_joint_fh_wc_stopping_replay import cfg

def calculate(forecast,raw,tc_bytes=None):
    tc=None
    if tc_bytes is not None:
        import io
        receipt=forecast['tc_scenarios']
        if receipt['cutoff']!=forecast['data_asof'] or receipt['ordinary_six_gw_checksums']!=forecast['checksums'] or hashlib.sha256(tc_bytes).hexdigest()!=receipt['samples_sha256']:raise ValueError('TC cutoff/checksum mismatch')
        tc=pd.read_csv(io.BytesIO(tc_bytes),compression='gzip')
    result=run(forecast,raw,include_chips=True,tc_samples=tc)
    meta,origin=project(forecast)
    state=parse_state(raw,meta,result['gw'],forecast['data_asof'])
    current=plan_squad(origin,list(state.squad),result['gw'])
    result['current_team']={'rows':json.loads(current.rows.to_json(orient='records')),'expected_score':current.expected_score}
    result['computed_at']=pd.Timestamp.now(tz='UTC').isoformat()
    result['calculation_runtime']='original_locked_python'
    wc=result.get('chip_assessment',{}).get('candidate_lineups',{}).get('wildcard')
    if wc:
        # Presentation totals from the existing original TS path, without a new rule.
        from fpl_xpts.transfer_planner import _apply_selected_squad
        from fpl_xpts.wildcard_planner_v2 import build_asof_wc_projection
        state_wc,_,_=_apply_selected_squad(state,set(wc['squad_ids']),meta)
        state_wc.free_transfers=state.free_transfers
        state_wc.chips_used['wildcard'].append(result['gw'])
        proxy=build_asof_wc_projection(origin,meta,origin,result['gw'],cfg())
        path=plan_transfer_path(state_wc,meta,proxy,result['gw']+1,replace(cfg(),weights=cfg().weights[1:]))
        result['wildcard_followup']={'six_gw_xp_after_hits':wc['expected_score']+sum(x.projected_manager_score-x.official_hit_points for x in path.path),'weighted_objective_before_chip_timing_threshold':wc['expected_score']+path.objective,'free_transfers_next_gw':state.free_transfers}
        if forecast.get('model')=='B-MM-PM-TS-v1':
            # Export the already-computed B WC path; no second search or new score.
            result['wildcard_followup'].update(schema=B_WC_HORIZON_SCHEMA,gw=result['gw'],squad_ids=sorted(wc['squad_ids']),path=asdict(path)['path'])
    return result
if __name__=='__main__':
    directory=Path(sys.argv[1]);body=json.loads((directory/'input.json').read_text())
    result=calculate(body['forecast'],body['state'],(directory/'tc.csv.gz').read_bytes() if (directory/'tc.csv.gz').exists() else None)
    (directory/'result.json').write_text(json.dumps(result,allow_nan=False))
