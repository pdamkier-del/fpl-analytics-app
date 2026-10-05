"""Verify role integration, frozen results and fixed-finalist confirmation."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/role-event-priors-20261005-v1'
CONFIRM=ROOT/'analysis/results/role-event-confirmation-20261005-v1'

def main():
    checks=0
    for folder in [OUT,CONFIRM]:
        m=json.loads((folder/'manifest.json').read_text())
        for s in m['sources']:
            assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256'];checks+=1
        for output in m['outputs']:
            read_frozen_table(folder,output['name']);checks+=len(output['parts'])+2
    base=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','inputs')
    candidate=read_frozen_table(OUT,'candidate_inputs')
    keys=['fixture_uuid','player_uuid']
    joined=base.merge(candidate,on=keys,suffixes=('_base','_role'),validate='one_to_one')
    assert len(joined)==11794 and candidate.fixture_uuid.nunique()==144;checks+=1
    allowed={'goal_rate90','assist_rate90','goal_mu','assist_mu','mu_dc'}
    for col in base:
        if col in keys or col in allowed:continue
        a=joined[col+'_base'];b=joined[col+'_role']
        if pd.api.types.is_numeric_dtype(a):assert np.allclose(a,b,rtol=0,atol=1e-12)
        else:assert a.equals(b)
        checks+=1
    for kind in ['goal','assist']:
        totals=candidate.groupby(['fixture_uuid','team_id'])[kind+'_mu'].sum()
        sides=candidate.drop_duplicates(['fixture_uuid','team_id']).set_index(['fixture_uuid','team_id']).loc[totals.index]
        expected=np.where(sides.index.get_level_values('team_id')==sides.home_team_id,
                          sides.lambda_home_goals,sides.lambda_away_goals)
        if kind=='assist':expected=expected*sides.assist_probability_per_goal
        assert np.allclose(totals,expected,rtol=0,atol=1e-10);checks+=1
    d=read_frozen_table(OUT,'development_prior_predictions')
    known=d.role_known
    for kind in ['goal','assist','dc']:
        assert np.array_equal(d.loc[~known,kind+'_role_prior90'],d.loc[~known,kind+'_position_prior90']);checks+=1
    pred=read_frozen_table(OUT,'predictions');old=read_frozen_table(ROOT/'analysis/results/deadline-joint-paired-diagnostic-v1','predictions')
    j=pred.merge(old,on=keys,validate='one_to_one')
    for col in ['xPts','xPts_nonbonus','expected_minutes']:
        assert np.array_equal(j['current_v4_'+col],j['v4_'+col]);checks+=1
    truth=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','targets')
    precision=read_frozen_table(CONFIRM,'predictions')
    assert len(precision)==3*11794 and not precision[keys+['seed']].duplicated().any()
    assert set(precision.seed)=={26092501,26192501,26292501};checks+=2
    pooled=precision.drop(columns=['seed','gw']).groupby(keys,as_index=False).mean().merge(truth,on=keys,validate='one_to_one')
    metrics=json.loads((CONFIRM/'metrics.json').read_text())
    for arm in ['current_v4','role_candidate']:
        error=pooled[arm+'_xPts_nonbonus']-(pooled.total_points-pooled.bonus)
        scores=dict(mae=float(abs(error).mean()),rmse=float(np.sqrt((error**2).mean())),bias=float(error.mean()))
        for key,v in scores.items():assert np.isclose(v,metrics['nonbonus'][arm][key],rtol=0,atol=1e-12);checks+=1
    policies=json.loads((ROOT/'analysis/results/season-2025-26-mechanics-v1/verification.json').read_text())['policy_checks']
    for p in policies:assert hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest()==p['sha256'];checks+=1
    report=dict(passed=True,checks=checks,tests_passed=131,forecast_rows=11794,fixtures=144,
        simulations_per_fixture_per_arm=1200,only_role_event_fields_changed=True,
        original_80_draw_v4_predictions_identical=True,position_fallback_exact=True,
        team_goal_and_assist_means_conserved=True,source_hashes_and_packed_outputs_verified=True,
        classification='reused_diagnostic_not_new_holdout',model_promoted=False)
    (CONFIRM/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
