"""Assist candidates must not own or alter any MM/physical interface."""
from dataclasses import asdict
import numpy as np
import pytest
from b_precision_calibration import apply,assist_features
from test_b_event_conservation import fixture

def test_assist_candidate_changes_only_weights_and_keeps_role_mixture_object():
    inp,_=fixture();dist={};policy={'assist':{'coef':[-.2,.3,.1,.2,.1]}};meta={p.player_id:{'baseline_xm':80,'tactical_role':'q_RW_slow'}for p in inp.players};out,roles=apply(inp,dist,meta,policy,'assist')
    assert roles is dist
    for a,b in zip(inp.players,out.players):
        x=asdict(a);y=asdict(b);old=x.pop('assist_weight');new=y.pop('assist_weight');assert x==y
        assert .5<=new/old<=2.
    x=asdict(inp);y=asdict(out);x.pop('players');y.pop('players');assert x==y

def test_MM_arms_rejected_and_zero_assist_support_stays_zero():
    from dataclasses import replace
    inp,_=fixture();inp=replace(inp,players=tuple(replace(p,assist_weight=0.)for p in inp.players))
    policy={'assist':{'coef':[1.]*5}};out,_=apply(inp,{}, {},policy,'assist');assert all(p.assist_weight==0 for p in out.players)
    for arm in ['return','p90','combined']:
        with pytest.raises(ValueError,match='MM candidates are excluded'):apply(inp,{}, {},policy,arm)

def test_event_weight_hook_preserves_current_kernel_and_paired_goals():
    import pandas as pd
    from dataclasses import replace
    from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel
    from fpl_v1_1_model.b_event_simulator import simulate_match
    from b_precision_calibration import attach_to_kernel
    from fpl_v1_1_model.role_event_priors import QCOLS
    inp,_=fixture();inp=replace(inp,experimental_joint_goalkeepers=True,experimental_mean_preserving_minutes=True,verified_goalkeeper_roster_teams=('h','a'))
    kernel=PhysicalKernel(inp);moments={p.player_id:dict(x=90.)for p in inp.players};moments.update(kernel.moments);frame=pd.DataFrame([dict(player_uuid=p.player_id,**{q:float(q=='q_ST_slow')for q in QCOLS})for p in inp.players]);out,new=attach_to_kernel(inp,kernel,moments,frame,{'assist':{'coef':[-.2,.3,.1,.2,.1]}})
    assert new is not kernel and kernel.input==inp and new.input==out
    assert new.moments==kernel.moments
    for seed in range(8):
        a=np.random.default_rng(seed);b=np.random.default_rng(seed);ta=kernel.sample(a);tb=new.sample(b);assert ta==tb
        ra=simulate_match(inp,a,timeline=ta);rb=simulate_match(out,b,timeline=tb)
        assert all(ra[p].minutes==rb[p].minutes and ra[p].goals==rb[p].goals for p in ra)
        for team in ['h','a']:assert sum(ra[p.player_id].assists for p in inp.players if p.team==team)==sum(rb[p.player_id].assists for p in out.players if p.team==team)

def test_unaccepted_or_changed_assist_evidence_fails_closed(tmp_path):
    import json
    from b_precision_calibration import load_accepted
    p=tmp_path/'policy.json';p.write_text(json.dumps({'version':'B-assist-calibration-v1','approved':False}))
    with pytest.raises(ValueError,match='not approved'):load_accepted(tmp_path,p)
    p.write_text(json.dumps({'version':'B-assist-calibration-v1','approved':True,'sha256':{'weights.json':'0'*64}}));(tmp_path/'weights.json').write_text('{}')
    with pytest.raises(ValueError,match='evidence/source changed'):load_accepted(tmp_path,p)
