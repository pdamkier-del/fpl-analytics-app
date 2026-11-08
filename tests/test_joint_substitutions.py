"""Synthetic structural fixtures; these tests are not accuracy evidence."""
import numpy as np
import pytest
from test_physical_timeline import fixture
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel,validate_timeline
from fpl_v1_1_model.experimental_joint_substitutions import JointSubstitutionKernel

def model():
 return {'heads':{'incoming':[-1.,1.,0.,0.],'outgoing':[0.,1.,0.,0.]},'count':[0.,0.,0.,.2,.3,.5],'time':{event:{'pool':values,'by_position':{p:values for p in ['DEF','MID','FWD']}}for event,values in [('exit',[60,70,80]),('cameo',[10,20,30])]}}
def caps(inp):return {p.player_id:(0. if 'unavailable'in p.player_id else .65 if p.player_id=='H01'else 1.)for p in inp.players if not p.is_keeper}

def test_preserves_XI_keeper_and_clinical_caps():
 inp=fixture();b=PhysicalKernel(inp);k=JointSubstitutionKernel(inp,{},caps(inp),'synthetic',model())
 for data in k.teams.values():
  assert sum(k.moments[p.player_id]['x']for p in data['field'])==pytest.approx(900)
  assert sum(k.moments[p.player_id]['p']for p in data['field'])==pytest.approx(10)
  for p in data['field']:
   assert k.moments[p.player_id]['p']==pytest.approx(b.moments[p.player_id]['p'])
   assert k.moments[p.player_id]['p_play']<=caps(inp)[p.player_id]+1e-10
 for draw in range(100):
  a=b.sample(np.random.default_rng(draw));c=k.sample(np.random.default_rng(draw));assert validate_timeline(inp,c)
  for p in inp.players:
   assert (a[p.player_id][0]>0 and a[p.player_id][1]==0)==(c[p.player_id][0]>0 and c[p.player_id][1]==0)
   if p.is_keeper:assert a[p.player_id]==c[p.player_id]
  assert c['Hunavailable'][0]==c['Aunavailable'][0]==0

def test_analytic_minutes_match_sampler():
 inp=fixture();k=JointSubstitutionKernel(inp,{},caps(inp),'synthetic-moments',model());ids=sorted(k.moments);rng=np.random.default_rng(107)
 draws=np.array([[t[pid][0]for pid in ids]for t in [k.sample(rng)for _ in range(1000)]])
 for i,pid in enumerate(ids):
  actual=draws[:,i];assert abs(actual.mean()-k.moments[pid]['x'])<=6*actual.std(ddof=1)/np.sqrt(len(actual))+1e-8

def test_invalid_state_count_or_medical_cap_fails_closed():
 inp=fixture()
 with pytest.raises(ValueError,match='Power-of-two'):JointSubstitutionKernel(inp,{},caps(inp),'synthetic',model(),conditional_states=3)
 medical=caps(inp);medical['H01']=.1
 with pytest.raises(ValueError,match="availability cap"):JointSubstitutionKernel(inp,{},medical,'synthetic',model())
