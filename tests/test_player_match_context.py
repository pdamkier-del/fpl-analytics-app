import copy
import pytest
from collect_player_match_context import build

B={'elements':[{'id':1,'code':101,'element_type':3}], 'teams':[{'id':1,'name':'Manchester City'},{'id':2,'name':'Ipswich Town'}]}
SOURCE={'url':'https://www.fotmob.com/api/data/matchDetails?matchId=10','observed_at':'2026-10-22T11:00:00Z'}
F=[{'id':7,'team_h':1,'team_a':2,'kickoff_time':'2026-10-17T14:00:00Z'}]
def detail(group='subs',performance=None,minutes=None,comp='prem'):
 p={'id':1001,'name':'Fixture','performance':performance or {}}
 stats=[] if minutes is None else [{'stats':{'Minutes':{'key':'minutes_played','stat':{'value':minutes}},'Goals':{'key':'goals','stat':{'value':1}}}}]
 return {'general':{'matchId':10,'homeTeam':{'id':8456,'name':'Manchester City'},'awayTeam':{'id':9902,'name':'Ipswich Town'},'matchTimeUTCDate':'2026-10-17T14:00:00Z'},'header':{'teams':[{'score':3},{'score':2}]},'content':{'lineup':{'homeTeam':{'starters':[p]if group=='starters'else[{'id':999}],group:[p]},'awayTeam':{'starters':[{'id':888}]}},'playerStats':{'1001':{'id':1001,'optaId':'101','stats':stats}}}}
def run(j,e=None,comp='prem',fixtures=F):return build(B,fixtures,[(comp,j,SOURCE)],e or {'records':[]},SOURCE['observed_at'],[])['rows']

def test_unused_bench_is_not_played_due_to_season_totals():
 r=run(detail(performance={'seasonGoals':6,'seasonRating':8.0}))[0]
 assert r['minutes']==0 and r['reason_code']=='unused_substitute'
 assert r['cause_confirmed']is False and 'rested'not in r['reason_code']
 assert r['goals']is None and r['fpl_fixture_id']==7

def test_appearance_with_missing_minutes_stays_unknown():
 r=run(detail(performance={'substitutionEvents':[{'type':'subIn','time':70,'reason':'tactical'}]}))[0]
 assert r['minutes']is None and r['reason_code']=='minutes_unknown'

def test_cl_goal_is_context_and_never_fpl_points():
 r=run(detail('starters',minutes=90),comp='cl')[0]
 assert r['minutes']==90 and r['goals']==1
 assert 'fpl_fixture_id'not in r and 'total_points'not in r

def test_false_rest_claim_rejected():
 evidence={'records':[{'fpl_code':101,'provider_match_id':'10','reason_code':'rested','cause_confirmed':False,'label':'Sparet','source_url':'https://club.example/report'}]}
 with pytest.raises(ValueError,match='Unconfirmed'):run(detail(),evidence)
 evidence['records'][0]['cause_confirmed']=True
 assert run(detail(),evidence)[0]['reason_code']=='rested'

def test_exact_pl_fixture_identity_required():
 with pytest.raises(ValueError,match='identity mismatch'):run(detail(),fixtures=[])

def test_unavailable_suspension_keeps_provider_attribution():
 j=detail(group='unavailable');j['content']['lineup']['homeTeam']['unavailable'][0]['unavailability']={'type':'suspension'}
 r=run(j)[0];assert r['reason_code']=='suspension'and r['minutes']==0
 assert r['cause_confirmed']is False and r['reason_source']==SOURCE['url']
