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


def test_card_only_goalkeeper_is_a_played_candidate_under_official_fpl_rules(tmp_path):
    import json,hashlib
    from season_round_benchmark import build
    base=tmp_path/'history';base.mkdir()
    positions=[1,1,2,2,2,3,3,3,3,4,4,4]
    players=[dict(id=i,web_name=str(i),position=pos)for i,pos in enumerate(positions,1)]
    rows=[]
    for p in players:
        card=p['id']==2
        rows.append(dict(player_id=p['id'],gw=1,gw_complete=True,stats=dict(minutes=0 if card else 90,starts=0 if card else 1,red_cards=1 if card else 0,yellow_cards=0,total_points=-3 if card else -8 if p['id']==1 else 1)))
    docs={'current-players.json':{'players':players},'match-results.json':{'completed_gws':[1],'gw_rows':rows,'match_rows':[dict(player_id=p['id'],gw=1,team_id=p['id'])for p in players]}}
    files={}
    for name,data in docs.items():
        raw=json.dumps(data).encode();(base/name).write_bytes(raw);files[name]=hashlib.sha256(raw).hexdigest()
    (base/'index.json').write_text(json.dumps({'files':files}))
    result=build(tmp_path)['1']
    assert 2 in [p['id']for p in result['rows']]
    assert result['points']==8
