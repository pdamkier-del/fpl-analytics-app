import pandas as pd
import pytest
from analyze_mm_competition_rotation import integer,bool_value,lineup_changes,valid_intervals,team_games,individual_workload


def squad():
    rows=[]
    for i in range(12):
        starter=i<11
        minutes=60 if i==0 else 30 if i==11 else 90
        rows.append(dict(season='2024-25',club='Club',match_id='m',competition='FA Cup',stage='3',
            kickoff='2025-01-01T15:00:00Z',player_id=str(i),player_uuid=str(i),
            started=starter,minutes=minutes,start_min=0 if starter else 60,finish_min=60 if i==0 else 90))
    return pd.DataFrame(rows)


def test_xi_turnover_is_not_inmatch_substitution_count():
    assert lineup_changes(set(range(11)),set(range(1,12)))==1
    assert lineup_changes(set(range(10)),set(range(11)))is None
    g=team_games(squad())
    assert g.iloc[0].substitute_entries==1
    assert pd.isna(g.iloc[0].substitution_exits)
    assert g.iloc[0].mean_concordant_entry_minute==60


def test_fractional_or_all_zero_endpoints_are_not_minute_events():
    f=squad();assert valid_intervals(f)
    f['start_min']=0;f['finish_min']=1
    assert not valid_intervals(f)
    f['finish_min']=0;assert not valid_intervals(f)


def test_short_starter_alone_does_not_prove_a_substitution_exit():
    f=squad().iloc[:11].copy();f.loc[0,'minutes']=20;f.loc[0,'finish_min']=20
    g=team_games(f)
    assert pd.isna(g.iloc[0].substitution_exits)
    assert pd.isna(g.iloc[0].mean_concordant_entry_minute)


def test_stable_player_id_requires_numeric_id_not_a_name_guess():
    assert integer('42.0')=='42'
    assert integer(float('nan'))is None
    assert integer('J. Smith')is None
    assert bool_value('missing')is None


def test_workload_uses_past_only_and_unknown_is_not_zero_participation():
    f=squad().iloc[:1].copy();f.loc[:,'minutes']=90
    g=f.assign(match_id='next',kickoff='2025-01-05T15:00:00Z',minutes=20)
    rows=pd.concat([f,g],ignore_index=True)
    result=individual_workload(rows)
    assert result.iloc[0].recorded_minutes_7d==0
    assert result.iloc[1].recorded_minutes_7d==90
    assert result.iloc[1].observed_player_rest_before_days==4
    changed=rows.copy();changed.loc[1,'minutes']=120
    assert individual_workload(changed).iloc[0].recorded_minutes_7d==0
    rows.loc[0,'minutes']=float('nan')
    unknown=individual_workload(rows)
    assert unknown.iloc[1].missing_minutes_7d==1
    assert pd.isna(unknown.iloc[1].observed_player_rest_before_days)


def test_duplicate_player_records_fail_closed():
    f=squad();f=pd.concat([f,f.iloc[:1]],ignore_index=True)
    with pytest.raises(ValueError):team_games(f)
