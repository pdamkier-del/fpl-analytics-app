#!/usr/bin/env python3
"""Final per-GW audit: forecast vs actual vs reachable oracle.

Inputs:
- vFinal full-horizon proxy replay (GW22-38)
- reachable hindsight oracle benchmark for the exact pre-deadline model state

Outputs one table per GW with:
predicted manager points, actual points, reachable oracle points,
forecast error, oracle gap, model vs oracle transfers, hits, and bank/FT context.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'analysis/results/final_audit_inputs/model'
ORACLE=ROOT/'analysis/results/final_audit_inputs/oracle'
OUT=ROOT/'analysis/results/vfinal-final-gw-audit-20261006-v1'


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    glog=pd.read_csv(MODEL/'gameweek_log.csv')
    plans=pd.read_csv(MODEL/'plans.csv')
    oracle=pd.read_csv(ORACLE/'oracle_gap_by_gw.csv')

    executed=plans[plans.is_executed.astype(str).str.lower().isin(['true','1'])].copy()
    executed=executed.sort_values(['origin_gw','step']).drop_duplicates('origin_gw',keep='first')
    executed=executed.rename(columns={
        'origin_gw':'gw',
        'projected_manager_score':'predicted_points',
        'outgoing':'model_outgoing',
        'incoming':'model_incoming',
        'transfers':'model_plan_transfers',
        'official_hit_points':'model_plan_hits',
        'bank_before':'model_bank_before',
        'bank_after':'model_bank_after',
        'free_transfers_before':'model_ft_before',
        'free_transfers_after':'model_ft_after',
    })

    cols=[
        'gw','predicted_points','model_outgoing','model_incoming',
        'model_plan_transfers','model_plan_hits','model_bank_before',
        'model_bank_after','model_ft_before','model_ft_after'
    ]
    out=glog[['gw','score','transfers','hit_points','bank','free_transfers']].rename(columns={
        'score':'actual_points',
        'transfers':'model_transfers',
        'hit_points':'model_hits',
        'bank':'model_bank_after_logged',
        'free_transfers':'model_ft_after_logged',
    }).merge(executed[cols],on='gw',how='left')

    out=out.merge(
        oracle[[
            'gw','reachable_oracle_score','reachable_gap',
            'unconstrained_oracle_score','unconstrained_gap',
            'oracle_transfers','oracle_hits','oracle_incoming','oracle_outgoing',
            'pre_ft','pre_bank'
        ]],
        on='gw',how='left'
    )
    out['forecast_error_actual_minus_pred']=out.actual_points-out.predicted_points
    out['abs_forecast_error']=out.forecast_error_actual_minus_pred.abs()
    out['reachable_strategy_gap']=out.reachable_oracle_score-out.actual_points
    out['predicted_to_oracle_gap']=out.reachable_oracle_score-out.predicted_points
    out['actual_as_share_of_reachable_oracle']=out.actual_points/out.reachable_oracle_score
    out['same_transfer_count']=out.model_transfers.eq(out.oracle_transfers)
    out['same_incoming']=out.model_incoming.fillna('').astype(str).eq(out.oracle_incoming.fillna('').astype(str))
    out['same_outgoing']=out.model_outgoing.fillna('').astype(str).eq(out.oracle_outgoing.fillna('').astype(str))
    out['same_transfer_action']=out.same_incoming & out.same_outgoing

    out.to_csv(OUT/'gw_forecast_actual_oracle.csv',index=False)

    summary={
        'gameweeks':int(len(out)),
        'model_actual_points':int(out.actual_points.sum()),
        'reachable_oracle_points':int(out.reachable_oracle_score.sum()),
        'reachable_oracle_gap':int(out.reachable_strategy_gap.sum()),
        'mean_predicted_points':float(out.predicted_points.mean()),
        'mean_actual_points':float(out.actual_points.mean()),
        'mean_forecast_error_actual_minus_pred':float(out.forecast_error_actual_minus_pred.mean()),
        'mae_manager_points':float(out.abs_forecast_error.mean()),
        'mean_reachable_strategy_gap':float(out.reachable_strategy_gap.mean()),
        'median_reachable_strategy_gap':float(out.reachable_strategy_gap.median()),
        'same_transfer_action_gws':int(out.same_transfer_action.sum()),
        'different_transfer_action_gws':int((~out.same_transfer_action).sum()),
        'largest_forecast_misses':out.nlargest(6,'abs_forecast_error')[[
            'gw','predicted_points','actual_points','forecast_error_actual_minus_pred','abs_forecast_error'
        ]].to_dict(orient='records'),
        'largest_strategy_gaps':out.nlargest(6,'reachable_strategy_gap')[[
            'gw','predicted_points','actual_points','reachable_oracle_score','reachable_strategy_gap'
        ]].to_dict(orient='records'),
        'interpretation':{
            'forecast_error':'actual - predicted; measures manager-score calibration/noise for selected team',
            'reachable_strategy_gap':'reachable hindsight oracle - actual; upper bound on missed same-deadline strategy value from exact model state',
            'warning':'oracle knows actual outcomes and is not a deployable strategy; use as diagnostic ceiling only'
        }
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')

    # Compact markdown for checkpoint/review.
    show=out[[
        'gw','predicted_points','actual_points','reachable_oracle_score',
        'forecast_error_actual_minus_pred','reachable_strategy_gap',
        'model_outgoing','model_incoming','oracle_outgoing','oracle_incoming'
    ]].copy()
    show['predicted_points']=show.predicted_points.round(1)
    show['forecast_error_actual_minus_pred']=show.forecast_error_actual_minus_pred.round(1)
    md=['# vFinal GW forecast / actual / oracle audit','',
        '| GW | Pred | Actual | Reachable oracle | Forecast err | Strategy gap |',
        '|---:|---:|---:|---:|---:|---:|']
    for r in show.itertuples():
        md.append(f'| {int(r.gw)} | {r.predicted_points:.1f} | {int(r.actual_points)} | {int(r.reachable_oracle_score)} | {r.forecast_error_actual_minus_pred:+.1f} | {int(r.reachable_strategy_gap)} |')
    md += ['', '## Summary','',
           f"- Actual points: **{summary['model_actual_points']}**",
           f"- Reachable oracle: **{summary['reachable_oracle_points']}**",
           f"- Total reachable gap: **{summary['reachable_oracle_gap']}**",
           f"- Manager-score MAE: **{summary['mae_manager_points']:.2f}**",
           f"- Mean strategy gap/GW: **{summary['mean_reachable_strategy_gap']:.2f}**",
           '',
           'Oracle is hindsight-only and is used as a diagnostic ceiling, not as a deployable benchmark.']
    (OUT/'report.md').write_text('\n'.join(md)+'\n')

    print(json.dumps(summary,indent=2))
    print(show.to_string(index=False))


if __name__=='__main__':
    main()
