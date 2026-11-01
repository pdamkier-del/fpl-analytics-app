"""Guard against future squad leakage and roster-size-induced pool inflation."""
import numpy as np
import pandas as pd
from evaluate_gk_hierarchy import probabilities,role_groups


def test_unknown_roster_size_does_not_inflate_other_group_mass():
    beta=np.log([20.,8.,2.,1.])
    def group(roles,caps):return dict(roles=np.array(roles),caps=np.array(caps),counts=np.bincount(roles,weights=np.array(caps)>0,minlength=4))
    single=probabilities(group([2,3],[1.,1.]),beta)
    many=probabilities(group([2,3,3,3,3],[1.]*5),beta)
    assert np.isclose(single[0],many[0])
    assert np.isclose(single[1],many[1:].sum())
    unavailable=probabilities(group([0,2,3],[0.,1.,1.]),beta)
    assert unavailable[0]==0
    assert np.isclose(unavailable.sum(),1)


def test_future_lineup_does_not_change_historical_hierarchy():
    rows=pd.DataFrame([dict(season='2024-25',fixture_uuid='next',team_id=1,player_uuid=p,pos='GK',cutoff='2024-09-02T00:00:00Z',availability_cap=1.,y=y)for p,y in [('a',1),('b',0)]])
    obs=pd.DataFrame([dict(season='2024-25',fixture_uuid='prior',team_id=1,player_uuid=p,pos='GK',known_at='2024-09-01T18:00:00Z',kickoff_at='2024-09-01T14:00:00Z',started=y,minutes=90*y,confirmed_squad=True)for p,y in [('a',1),('b',0)]])
    expected=role_groups(rows,obs)[0]['roles']
    future=obs.copy();future['known_at']='2024-09-03T18:00:00Z';future['kickoff_at']='2024-09-03T14:00:00Z';future['started']=1-future.started
    actual=role_groups(rows,pd.concat([obs,future]))[0]['roles']
    assert expected.tolist()==actual.tolist()==[0,2,3]
