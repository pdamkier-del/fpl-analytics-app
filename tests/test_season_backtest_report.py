import pytest
from season_backtest_report import score_forecast,metrics

def fixture():
    row=dict(gw=6,fixture_uuid='live-2026-27-fpl-51',player_uuid='uuid',player_id=1,fpl_code=99,team_id=10,position=1,kickoff='2026-10-10T12:00:00Z',p_start=.8,expected_minutes=72,pm_expected_minutes=72,p_play=.9,p60=.7,p90=.6,xp=4)
    doc=dict(schema='B-current-season-backtest-v1',scope='retrospective_fixed_B_policy_not_original_forecast_not_independent_holdout',gw=6,cutoff='2026-10-10T09:00:00Z',origin_deadline='2026-10-10T10:00:00Z',generated_at='2026-10-27T00:00:00Z',players=[row])
    st=dict(minutes=90,starts=1,total_points=6)
    history=dict(match_rows=[dict(player_id=1,fixture_id=51,team_id=10,provisional=False,stats=st)],gw_rows=[dict(player_id=1,gw=6,gw_complete=True,stats=st)])
    catalogue=dict(players=[dict(id=1,code=99)])
    fixtures=dict(fixtures=[dict(id=51,gw=6,home=10,away=20,kickoff='2026-10-10T12:00:00Z',finished=True)])
    return doc,history,catalogue,fixtures

def test_retrospective_accuracy_separate_mm_pm_law_and_all_minute_briers():
    w,rows=score_forecast(*fixture());assert w['scored_rows']==1 and w['minute_mae']==18 and w['xp_mae']==2 and w['xp_bias']==-2
    assert w['start_brier']==pytest.approx(.04) and w['p60_brier']==pytest.approx(.09)
    assert w['p0_brier']==pytest.approx(.01) and w['p90_brier']==pytest.approx(.16)

def test_missing_outcomes_not_zero_or_perfect_score():
    d,h,c,f=fixture();h['match_rows']=[]
    w,rows=score_forecast(d,h,c,f);assert w['pending_rows']==1 and w['xp_mae']is None and not rows

def test_source_verified_zero_can_be_scored():
    d,h,c,f=fixture();h['match_rows']=[];h['gw_rows'][0]['stats']=dict(minutes=0,starts=0,total_points=0)
    w,rows=score_forecast(d,h,c,f);assert w['xp_mae']==4 and rows[0]['label_basis']=='official_final_GW_all_zero'

def test_wrong_stable_code_excluded():
    d,h,c,f=fixture();c['players'][0]['code']=100
    w,rows=score_forecast(d,h,c,f);assert w['excluded_rows']==1 and not rows

@pytest.mark.parametrize('change',['scope','clock','fixture','duplicate','MM_PM','probability'])
def test_corrupt_or_mislabelled_backtest_rejected(change):
    d,h,c,f=fixture()
    if change=='scope':d['scope']='prospective_forecast'
    elif change=='clock':d['cutoff']=d['origin_deadline']
    elif change=='fixture':d['players'][0]['team_id']=99
    elif change=='duplicate':d['players']*=2
    elif change=='MM_PM':d['players'][0]['pm_expected_minutes']=70
    else:d['players'][0]['p90']=1.1
    with pytest.raises(ValueError):score_forecast(d,h,c,f)

def test_empty_period_not_claimed_as_validated():
    m=metrics([]);assert m['scored_rows']==0 and m['start_brier']is None and m['minute_mae']is None
