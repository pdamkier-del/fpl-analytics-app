import itertools
from collections import Counter
import pytest
from season_round_benchmark import best_xi

def test_hindsight_benchmark_is_exact_with_formation_club_and_captain_constraints():
    players=[dict(id=i,name=str(i),position=pos,team_id=i%6,points=(i*7)%13-2)for i,pos in enumerate([1,1,2,2,2,2,2,3,3,3,3,3,4,4,4],1)]
    expected=None
    for xi in itertools.combinations(players,11):
        counts=Counter(p['position']for p in xi)
        if counts[1]!=1 or not 3<=counts[2]<=5 or not 2<=counts[3]<=5 or not 1<=counts[4]<=3 or max(Counter(p['team_id']for p in xi).values())>3:continue
        value=sum(p['points']for p in xi)+max(p['points']for p in xi)
        expected=value if expected is None else max(expected,value)
    result=best_xi(players)
    assert result['points']==expected and result['optimal']is True
    assert 'NO budget'in result['scope']
    assert len(result['rows'])==11 and sum(p['role']=='C'for p in result['rows'])==1


def test_no_legal_formation_is_not_reported_as_an_optimum():
    assert best_xi([dict(id=i,position=3,team_id=i,points=2)for i in range(12)])is None
