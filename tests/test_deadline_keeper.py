import json
from pathlib import Path

import pandas as pd
import pytest

from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline

FIT=json.loads((Path(__file__).resolve().parents[1]/'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json').read_text())
CUTOFF='2026-01-17T11:00:00Z'


def history():
    rows=[]
    for i in range(5):
        for team,opponent,for_sot,against in [(1,2,12.,3.),(2,1,3.,12.)]:
            rows.append(dict(season='2025-26',fixture_uuid=str(i),team_id=team,opponent_team_id=opponent,
                kickoff_at=f'2026-01-{i+1:02d}T15:00:00Z',available_at=f'2026-01-{i+1:02d}T18:00:00Z',
                shots_on_target=for_sot,shots_on_target_conceded=against))
    return pd.DataFrame(rows)


def sides():
    return pd.DataFrame([dict(fixture_uuid='target',team_id=1,opponent_team_id=2,was_home=True),
        dict(fixture_uuid='target',team_id=2,opponent_team_id=1,was_home=False)])


def run(h):
    return keeper_saves_at_deadline(h,sides(),CUTOFF,FIT).set_index('team_id')


def test_attacking_opportunity_is_assigned_to_opposing_keeper():
    h=history();before=run(h)
    h.loc[h.team_id==1,'shots_on_target']=24
    h.loc[h.team_id==2,'shots_on_target_conceded']=24
    after=run(h)
    assert after.loc[2,'lambda_saves']>before.loc[2,'lambda_saves']
    assert after.loc[1,'lambda_saves']==pytest.approx(before.loc[1,'lambda_saves'])


def test_future_target_sot_cannot_change_either_keeper():
    future=history();future.fixture_uuid=future.fixture_uuid+'future'
    future.kickoff_at='2026-01-17T15:00:00Z';future.available_at='2026-01-17T18:00:00Z'
    future[['shots_on_target','shots_on_target_conceded']]=1e8
    pd.testing.assert_frame_equal(run(history()),run(pd.concat([history(),future],ignore_index=True)))


def test_missing_source_sot_is_rejected():
    h=history();h.loc[0,'shots_on_target']=None
    with pytest.raises(ValueError,match='source SOT'):run(h)
