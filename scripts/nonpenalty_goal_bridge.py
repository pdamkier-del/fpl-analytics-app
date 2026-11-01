"""Verified current source bridge for the explicitly selected B NP goal head."""
import hashlib,json
from pathlib import Path
import pandas as pd
import numpy as np
from fpl_v1_1_model.experimental_penalty_neutral import PenaltyNeutralState,occurrence_probability
from fpl_v1_1_model.experimental_nonpenalty_allocation import allocate
from fpl_v1_1_model.role_event_priors import QCOLS


def calculate(root,frame,model,*,source_root=None):
    root=Path(root);source=Path(source_root or root);base=source/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    names=['player_fixture_observations','verified_penalty_attempts','verified_penalty_team_sides','reconstructed_training_features','classified_starters']
    data={n:pd.read_csv(base/(n+'.csv.gz'),low_memory=False)for n in names}
    h,events,sides,roles,classified=[data[n]for n in names]
    if sides.duplicated(['fixture_uuid','team_code']).any()or not sides.groupby('fixture_uuid').size().eq(2).all():raise ValueError('Incomplete penalty source sides')
    if set(h.fixture_uuid)!=set(sides.fixture_uuid):raise ValueError('Penalty and xG match coverage differs')
    events=events.merge(sides[['match_id','team_code','fixture_uuid']],on=['match_id','team_code'],validate='many_to_one',how='left')
    if events.fixture_uuid.isna().any():raise ValueError('Unmapped penalty event')
    count=events.groupby(['fixture_uuid','player_uuid'],as_index=False).attempts.sum();count['season']='2026-27'
    actual=events.groupby(['fixture_uuid','team_code']).attempts.sum().reindex(pd.MultiIndex.from_frame(sides[['fixture_uuid','team_code']]),fill_value=0)
    if not np.array_equal(actual.to_numpy(),sides.attempts.to_numpy()):raise ValueError('Penalty event counts do not reconcile')
    if 'max_history_known_at'not in roles:
        by={int(t):pd.to_datetime(g.available_at,utc=True).drop_duplicates().sort_values()for t,g in classified.groupby('team_id')}
        roles['max_history_known_at']=[by[int(r.team_id)][by[int(r.team_id)]<pd.Timestamp(r.cutoff)].max()for r in roles.itertuples()]
    if frame.cutoff.nunique()!=1:raise ValueError('Mixed goal-head cutoff')
    cut=frame.cutoff.iloc[0];target=frame[['fixture_uuid','player_uuid','team_id','pos','max_history_known_at']+QCOLS]
    state=PenaltyNeutralState(h,count,roles[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS],model['attack'])
    audit=allocate(state,target,cut,'2026-27',model['allocation']);weights={(r.fixture_uuid,r.player_uuid):float(r.ordinary_goal_weight)for r in audit.itertuples()}
    report=dict(version=model['version'],historical_fixtures=int(h.fixture_uuid.nunique()),verified_penalty_attempts=int(count.attempts.sum()),source_sha256={n:hashlib.sha256((base/(n+'.csv.gz')).read_bytes()).hexdigest()for n in names},ordinary_head='FPL-scale NP history, NP role priors and NP-only refitted coefficients',penalty_fallback='frozen separately before replacing ordinary weights',form_window='previous three known PL observations; no missing cup events assumed zero')
    report['team_penalty_fixtures']=[dict(fixture_id=r.fixture_uuid,team_id=int(r.team_id),expected_attempts=float(r.lambda_pen),p_at_least_one=occurrence_probability(float(r.lambda_pen)))for r in frame[['fixture_uuid','team_id','lambda_pen']].drop_duplicates().itertuples()]
    return weights,audit,report


def load(root,path):
    root=Path(root);policy=json.loads(Path(path).read_text())
    if policy.get('approved')is not True or policy.get('version')!='nonpenalty-goal-head-v1':raise ValueError('NP goal head not approved')
    for name,expected in policy['sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise ValueError('NP policy source mismatch '+name)
    decision=json.loads((root/policy['decision']).read_text())
    if decision.get('passed')is not True or decision.get('fixtures')!=341 or decision.get('baseline_max_xp_error')!=0:raise ValueError('NP historical gate not passed')
    model=json.loads((root/policy['model']).read_text())
    if model.get('version')!='nonpenalty-goal-head-v1'or set(model['allocation']['columns'])!={'np_last_xg','np_recent3_xg'}:raise ValueError('Blended goal model is forbidden')
    if model.get('training_max_gw')!=21 or model.get('training_min_gw')!=16:raise ValueError('Wrong NP training window')
    return model,policy
