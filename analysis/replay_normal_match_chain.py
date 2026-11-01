"""Exercise the real B MM→PM→TS pipeline on one exact archived source bundle.

This rehearsal never publishes, changes raw clocks or edits a manager's team.
The archive binding prevents mixing a retained older local live GK history.
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import gk_solo_role
import nonpenalty_goal_bridge
import run_joint_gk_preview as pipeline
from gk_joint_bridge import observations
from fpl_v1_1_model.forecast_snapshot import require_snapshot
from b_chain_contract import validate_forecast


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    root=Path(__file__).resolve().parents[1];inputs=a.artifact/'work/current-B-inputs'
    squads=pd.read_csv(a.artifact/'work/joint-gk-current/role-squad-evidence.csv.gz')
    for c in ['clock','kick']:squads[c]=pd.to_datetime(squads[c],utc=True,format='mixed')
    obs=observations(root);obs=obs[~obs.season.eq('2026-27')]
    live=pd.read_csv(a.artifact/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz',low_memory=False)
    live=live[live.fpl_position.isin(['GK','GKP','G'])].copy()
    live['known_at']=pd.to_datetime(live.available_at,utc=True)
    if 'season'not in live:live['season']='2026-27'
    obs=pd.concat([obs,live[obs.columns]],ignore_index=True).drop_duplicates(['season','fixture_uuid','player_uuid'])
    calculate=nonpenalty_goal_bridge.calculate
    def exact_calculate(root,frame,model,**kw):
        return calculate(root,frame,model,source_root=a.artifact)
    a.out.mkdir(parents=True,exist_ok=True)
    with patch.object(gk_solo_role,'load_policy',lambda _,history:gk_solo_role.SoloRolePolicy(history,squads)),\
         patch.object(pipeline,'observations',lambda _:obs),\
         patch.object(nonpenalty_goal_bridge,'calculate',exact_calculate):
        result=pipeline.current(inputs,a.out,paired=True,chain=True,physical_minutes=True,
            evidence_path=a.artifact/'work/gk-official-evidence/evidence.json',
            assignment_policy=root/'analysis/results/joint-role-candidate-20261022/policy.json',
            goal_head_policy=root/'analysis/results/nonpenalty-goal-head-20261023/policy.json')
        require_snapshot(result);validate_forecast(result)
        # Same physical process and seeds at one-match, one-GW and six-GW scopes.
        import validate_joint_gk_stages as stages
        with patch.object(stages,'observations',lambda _:obs):
            stages.main(a.out,inputs)
    audits=[r['physical_timeline']for r in result['gk_team_fixtures']]
    report=dict(scope='Exact archived 24 October source rehearsal, not fresh data',
        fixtures=result['fixtures'],players=len(result['players']),rows=result['player_fixture_rows'],
        gws=result['gws'],team_draws=sum(r['draws']for r in audits),
        max_substitutions=max(r['max_substitutions']for r in audits),
        max_live_windows=max(r['max_windows']for r in audits),
        all_physical_MM_PM_and_shared_TS_contracts_passed=True,
        synthetic_six_GW_TS_search_passed=json.loads((a.out/'ts-validation.json').read_text())['ts_ran'],
        physical_to_reported_clock_calibrated=False,red_card_removals_modeled=False,
        forecast_sha256=result['forecast_sha256'],production_changed=False)
    (a.out/'correctness-rehearsal.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
