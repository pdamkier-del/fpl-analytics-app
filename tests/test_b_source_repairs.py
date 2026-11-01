import numpy as np
import pandas as pd
import pytest
from b_physical_workload import features,current_ledger
from b_horizon_eligibility import annotate,constrain

def test_physical_load_includes_cup_cameos_but_not_future_reports_or_duplicates():
    target=pd.DataFrame([dict(season='2026-27',fixture_uuid='next',player_uuid='a',team_id=1,cutoff='2026-10-31T08:00:00Z')])
    ledger=pd.DataFrame([dict(season='2026-27',match_id=m,player_uuid='a',team_id=team,minutes=minutes,kickoff=k,known_at=n,competition=c)for m,team,minutes,k,n,c in [('pl',1,45,'2026-10-24T11:30Z','2026-10-24T15:30Z','prem'),('cup',1,90,'2026-10-28T19:30Z','2026-10-28T23:30Z','efl'),('late',1,30,'2026-10-29T19:30Z','2026-11-01T00:00Z','cl')]])
    f=features(target,ledger);assert f.minutes_7d.iloc[0]==135;assert f.rest_days.iloc[0]==pytest.approx(2.5208333333)
    # Physical load follows identity through a club transfer, team rest does not.
    moved=features(target.assign(team_id=2),ledger);assert moved.minutes_7d.iloc[0]==135;assert np.isnan(moved.team_rest_days.iloc[0])
    with pytest.raises(ValueError,match='Duplicate'):features(target,pd.concat([ledger,ledger.iloc[:1]]))

def test_persistent_departure_all_positions_and_later_recall():
    rows=[]
    for gw in [9,10,11]:
        for pid in range(1,16):rows.append(dict(season='2026-27',fixture_uuid=str(gw),player_uuid=str(pid),fpl_element=pid,team_id=1,gw=gw,cutoff='2026-10-31T08:00Z',pos='GK'if pid<3 else'MID',p=.5 if pid<3 else 10/13,q=.1,s=85.,c=15.,availability_cap=1.))
    f=pd.DataFrame(rows);boot={'elements':[dict(id=i,team=1,status='u'if i==3 else'a',news='Has joined Elsewhere permanently'if i==3 else'',news_added=None)for i in range(1,16)]}
    out=constrain(annotate(f,boot,'2026-10-31T07:00Z'));assert out[out.fpl_element.eq(3)][['p','q','x']].eq(0).all().all();assert np.allclose(out.groupby('fixture_uuid').p.sum(),11)
    boot['elements'][2].update(status='a',news='');returned=annotate(f,boot,'2026-10-31T07:00Z');assert returned.loc[returned.fpl_element.eq(3),'persistent_availability_cap'].eq(1).all()
    boot['elements'][2].update(status='i',news='Thigh injury');assert annotate(f,boot,'2026-10-31T07:00Z').persistent_availability_cap.eq(1).all()
    with pytest.raises(ValueError,match='precede'):annotate(f,boot,'2026-10-31T09:00Z')

def test_medical_dates_year_boundary_and_probabilistic_timeline():
    from b_medical_return import parse_date,probability
    assert parse_date('Thigh injury - Expected back 2 Jan','2026-12-20T12:00Z').year==2027
    assert parse_date('Unknown return date','2026-10-31T00:00Z')is None
    assert parse_date('Expected back 31 Feb','2026-10-31T00:00Z')is None
    with pytest.raises(ValueError):parse_date('Expected back 2 Jan','2026-12-20T00:00Z','2026-12-21T00:00Z')
    h=pd.DataFrame([dict(report_known_at='2025-01-01T00:00Z',outcome_known_at='2025-03-01T00:00Z',residual_days=d,event=True)for d in np.linspace(-10,30,40)])
    values=[probability(h,'2026-10-01T00:00Z','2026-10-21T00:00Z',t)[0]for t in ['2026-10-07T00:00Z','2026-10-21T00:00Z','2026-11-21T00:00Z']]
    assert 0<values[0]<values[1]<values[2]<1
    future=h.assign(outcome_known_at='2027-01-01T00:00Z');assert probability(future,'2026-10-01T00:00Z','2026-10-21T00:00Z','2026-11-21T00:00Z')[0]is None
