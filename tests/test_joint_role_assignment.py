import numpy as np
import pytest
from fpl_v1_1_model.experimental_joint_role_assignment import fractional_assignment,decompose_assignment,lineup_marginals,build_role_distribution,role_scores


def test_zero_strength_preserves_frozen_marginals():
 p=np.array([.8,.7,.6,.5,.4]);p=p*2/p.sum()
 x=fractional_assignment(p,np.zeros((5,2)),strength=0)
 np.testing.assert_allclose(x.sum(axis=1),p,atol=1e-8)


def test_whole_assignment_mixture_reproduces_start_means():
 p=np.array([.8,.7,.6,.5,.4])*2/3
 x=fractional_assignment(p,np.array([[2,0],[2,0],[0,2],[0,2],[1,1.]]),strength=.5)
 rows=decompose_assignment(x,list('abcde'),['left','right'],'toy')
 assert all(len(r.players)==2 and len(set(r.players))==2 for r in rows)
 np.testing.assert_allclose(lineup_marginals(rows,list('abcde')),x.sum(axis=1),atol=4e-7)


def test_availability_bounds_and_hard_endpoints():
 p=np.array([1.,.5,.25,.25,0]);caps=np.array([1,.5,.5,1,0])
 x=fractional_assignment(p,np.array([[0,0],[10,10],[0,0],[0,0],[100,100]]),caps=caps,strength=1)
 assert abs(x[0].sum()-1)<1e-10 and x[-1].sum()==0
 assert x[1].sum()<=.5+1e-9


def test_fully_known_lineup_decomposes_without_creating_reserve_starts():
 p=np.r_[np.ones(10),np.zeros(5)]
 x=fractional_assignment(p,np.random.default_rng(731).normal(size=(15,10)),strength=.5)
 rows=decompose_assignment(x,[str(i)for i in range(15)],['RB']*10,'test')
 np.testing.assert_allclose(lineup_marginals(rows,[str(i)for i in range(15)]),p,atol=4e-7)


def test_cap_sum_exactly_required_keeps_fractional_injury_mass():
 p=np.array([.7,.6,.4,.3]);x=fractional_assignment(p,np.zeros((4,2)),caps=p,strength=1)
 np.testing.assert_allclose(x.sum(axis=1),p,atol=1e-10)
 decompose_assignment(x,list('abcd'),['l','r'],'toy')


def test_role_alternatives_change_marginals_before_points():
 p=np.array([.8,.7,.5]);a=fractional_assignment(p,np.array([[4,0],[0,4],[0,0]]),strength=1)
 b=fractional_assignment(p,np.array([[4,4],[0,0],[0,4]]),strength=1)
 assert b[2].sum()>a[2].sum()


def test_common_score_offset_does_not_change_selection():
 p=np.array([.8,.7,.5]);s=np.array([[4,0],[0,4],[0,0.]])
 np.testing.assert_allclose(fractional_assignment(p,s,strength=.5),fractional_assignment(p,s+2,strength=.5),atol=1e-7)


def test_unknown_role_is_explicit_prior_not_invalid_zero():
 players=[dict(q={},H={})for _ in range(12)];s,slots=role_scores(players,'4-2-3-1',.5)
 assert s.shape==(12,10)and len(slots)==10 and np.isfinite(s).all()


def test_missing_role_evidence_does_not_equalize_starter_and_reserve_chances():
 p=np.r_[np.full(10,.98),.15,.05]
 players=[dict(player_uuid=str(i),base_p_start=float(v),q={},H={})for i,v in enumerate(p)]
 _,actual=build_role_distribution(players,{'4-2-3-1':1},.8,strength=.5)
 np.testing.assert_allclose(actual,p,atol=4e-7)


def test_infeasible_hard_caps_fail_without_inventing_starters():
 with pytest.raises(ValueError,match='available'):fractional_assignment([.2,.2,.2],np.zeros((3,2)),caps=[.3,.3,.3])


def test_real_formation_and_flexible_player_cannot_occupy_two_slots():
 roles=['RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST','RAM','CAM']
 players=[dict(player_uuid=str(i),base_p_start=10/12,q={r:1.},H={r:.5})for i,r in enumerate(roles)]
 rows,p=build_role_distribution(players,{'4-2-3-1':1},.7,strength=.25)
 assert abs(p.sum()-10)<1e-8
 assert all(len(r.players)==len(set(r.players))==10 for r in rows)
 assert all(len(r.roles)==10 for r in rows)


def test_importance_interacts_with_role_hierarchy():
 players=[dict(q={'RAM':1.},H={'RAM':.9}),dict(q={'RAM':1.},H={'RAM':.1})]
 a,_=role_scores(players,'4-2-3-1',0);b,_=role_scores(players,'4-2-3-1',1)
 assert (b[0]-b[1]).max()>(a[0]-a[1]).max()


def sampler_fixture():
 from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup
 from fpl_v1_1_model.joint_simulator import PlayerSimInput,MatchSimInput
 players=[];choices={}
 for team in ('H','A'):
  # Nine fixed players and two competing flexible alternatives. Every draw
  # must choose exactly one alternative, while marginal means stay at .7/.3.
  ids=[team+str(i)for i in range(11)]
  roles=('RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST')
  choices[team]=(RoleLineup(.7,'4-2-3-1',tuple(ids[:10]),roles),
                 RoleLineup(.3,'4-2-3-1',tuple(ids[:9]+[ids[10]]),roles))
  for i,uid in enumerate(ids):
   players.append(PlayerSimInput(uid,team,'MID',1. if i<9 else .7 if i==9 else .3,0.,90.,1.))
  players.append(PlayerSimInput(team+'GK',team,'GK',1.,0.,90.,1.,is_keeper=True))
 inp=MatchSimInput('H','A',0.,0.,tuple(players),experimental_joint_goalkeepers=True,
                    verified_goalkeeper_roster_teams=('H','A'),experimental_mean_preserving_minutes=True,
                    experimental_joint_starters=True)
 return inp,choices


def test_pm_draws_whole_roles_with_same_marginals_and_preserves_gk_coverage():
 from fpl_v1_1_model import joint_simulator as sim
 from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
 inp,choices=sampler_fixture();original=sim.simulate_match;rng=np.random.default_rng(8421);starts=0
 with role_lineup_sampler(choices):
  for _ in range(1000):
   trace={};out=sim.simulate_match(inp,rng,trace=trace)
   for team in ('H','A'):
    assert sum(v.started for uid,v in out.items()if uid.startswith(team)and uid!=team+'GK')==10
    assert out[team+'9'].started+out[team+'10'].started==1
    assert out[team+'GK'].minutes==90
    assert trace['intervals'][team+'GK']==(0,90)
   starts+=out['H9'].started
 assert .65<starts/1000<.75
 assert sim.simulate_match is original


def test_pm_rejects_inconsistent_mm_marginals_and_restores_hook():
 from dataclasses import replace
 from fpl_v1_1_model import joint_simulator as sim
 from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
 inp,choices=sampler_fixture();original=sim.simulate_match
 inp=replace(inp,players=tuple(replace(p,p_start=.4)if p.player_id=='H9'else p for p in inp.players))
 with pytest.raises(ValueError,match='MM start marginals'):
  with role_lineup_sampler(choices):sim.simulate_match(inp,np.random.default_rng(3))
 assert sim.simulate_match is original


def test_role_evidence_excludes_target_and_future_games():
 import pandas as pd
 from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
 roles=['GK','RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST']
 rows=[]
 for fx,kick,known in [('past','2026-10-01T12:00Z','2026-10-01T16:00Z'),('future','2026-10-20T12:00Z','2026-10-20T16:00Z')]:
  for i,role in enumerate(roles):rows.append(dict(season='s',fixture_uuid=fx,team_id=1,
   player_uuid=fx+str(i),kickoff=kick,known_at=known,formation='4-2-3-1',final_role=role,minutes=90.))
 hist=AssignmentHistory(pd.DataFrame(rows));e=hist.evidence('s',1,'2026-10-20T16:00Z')
 assert e['games']==1 and all(uid.startswith('past')for uid in e['states'])
 assert hist.evidence('s',1,'2026-10-01T16:00Z')is None


@pytest.mark.parametrize('seed',range(10))
def test_transport_decomposition_stress_with_injuries(seed):
 rng=np.random.default_rng(seed);p=rng.uniform(.05,.95,25);p*=10/p.sum()
 caps=np.maximum(p,rng.uniform(.4,1.,25));scores=rng.normal(0,3,(25,10))
 x=fractional_assignment(p,scores,caps=caps,strength=.5)
 rows=decompose_assignment(x,[str(i)for i in range(25)],['RB']*10,'test')
 np.testing.assert_allclose(lineup_marginals(rows,[str(i)for i in range(25)]),x.sum(axis=1),atol=4e-7)


def test_scoped_role_kernel_keeps_unknown_team_on_existing_rounding():
 from fpl_v1_1_model import joint_simulator as sim
 from fpl_v1_1_model.experimental_joint_role_assignment import role_lineup_sampler
 inp,choices=sampler_fixture();rng=np.random.default_rng(72)
 with role_lineup_sampler({'H':choices['H']}):
  for _ in range(30):
   out=sim.simulate_match(inp,rng)
   assert sum(v.started for uid,v in out.items()if uid.startswith('A')and uid!='AGK')==10


def test_actual_b_run_connects_assignment_mm_and_pm_without_changing_keepers(monkeypatch):
 import pandas as pd
 from dataclasses import replace
 import run_joint_gk_preview as runner
 from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
 inp,_=sampler_fixture()
 inp=replace(inp,home_team='1',away_team='2',players=tuple(replace(p,
  player_id=p.player_id.replace('H','1').replace('A','2'),team='1'if p.team=='H'else'2')for p in inp.players))
 forecast=[];past=[]
 roles=['RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST']
 for p in inp.players:
  forecast.append(dict(season='s',fixture_uuid='target',player_uuid=p.player_id,team_id=int(p.team),
   gw=8,cutoff='2026-10-20T00:00Z',pos=p.position,p=p.p_start,q=p.p_cameo_given_bench,
   s=p.start_minutes_mean,c=p.cameo_minutes_mean,x=p.p_start*p.start_minutes_mean,
   availability_cap=1.,news_eligible=False,news_state='UNKNOWN',news_chance=np.nan))
  if p.player_id==p.team+'10':continue
  role='GK'if p.is_keeper else roles[int(p.player_id[1:])]
  past.append(dict(season='s',fixture_uuid='past',player_uuid=p.player_id,team_id=int(p.team),
   kickoff='2026-10-01T12:00Z',formation='4-2-3-1',final_role=role,minutes=90.))
 f=pd.DataFrame(forecast);h=AssignmentHistory(pd.DataFrame(past))
 obs=pd.DataFrame([dict(player_uuid='prior',team_id=1,started=1,minutes=90,known_at='2026-09-01T00:00Z')for _ in range(120)])
 monkeypatch.setattr(runner,'make_vfinal_input',lambda g:(inp,False))
 result,means,audit,_=runner.run(f,f,obs,season='2026-27',draws=25,chain=True,
                                  distributions=True,assignment_history=h,assignment_strength=.5)
 assert len(result)==len(f) and all(a['outfield_role_assignment']['applied']for a in audit)
 for team in ('1','2'):
  assert sum(means['target',p.player_id]['p']for p in inp.players if p.team==team and not p.is_keeper)==pytest.approx(10.)
  assert means['target',team+'GK']['x']==pytest.approx(90.)
 for key,d in means.items():
  assert d['x']==pytest.approx(d['p']*d['s']+(1-d['p'])*d['q']*d['c'])


def test_policy_does_not_accept_receipts_without_implementation_fingerprints(tmp_path):
 import json
 from joint_role_bridge import load_assignment_policy
 p=tmp_path/'policy.json';p.write_text(json.dumps(dict(version='joint-role-assignment-v1',strength=.5,evidence_sha256={})))
 with pytest.raises(ValueError,match='fingerprints'):load_assignment_policy(tmp_path,p)


@pytest.mark.parametrize('code,name',[('cl','champions-league'),('el','europa-league'),('efl','efl-cup'),('fa','fa-cup'),('conf','conference-league'),('conf_qual','conference-league')])
def test_provider_competition_codes_keep_existing_importance_values(code,name):
 from fpl_v1_1_model.experimental_role_importance import competition_name,importance
 assert competition_name(code)==name
 active=['prem','fa-cup','efl-cup',name]
 assert importance(code,'League phase',10,active)==importance(name,'League phase',10,active)


def test_champions_league_is_not_given_league_cup_priority():
 from fpl_v1_1_model.experimental_role_importance import importance,stage_strength
 active=['prem','fa-cup','efl-cup','cl']
 assert importance('cl','League phase',10,active)>importance('efl','Third round',10,active)
 assert stage_strength('fa','Semi-final',4)==.88
 assert stage_strength('fa','Quarter-final',3)==.76
 assert stage_strength('fa','Final',5)==1.


def test_unknown_competition_fails_instead_of_silently_using_zero_value():
 from fpl_v1_1_model.experimental_role_importance import competition_name
 with pytest.raises(ValueError,match='Unknown role competition'):competition_name('unmapped-cup')
