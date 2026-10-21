#!/usr/bin/env python3
"""Exact seeded locked-default parity against the retained original PM source."""
from dataclasses import asdict
import subprocess,sys,types,inspect
import numpy as np
from fpl_v1_1_model import joint_simulator as current
REFERENCE='49b5a82976a264da51624bac98990d371116a488'
def check():
    source=subprocess.check_output(['git','show',REFERENCE+':src/fpl_v1_1_model/joint_simulator.py'],text=True)
    tail='    # Shared penalty process.'
    current_source=inspect.getsource(current).replace('    if trace is not None: trace["intervals"]=dict(intervals)\n','')
    # Only this explicitly gated B taker-selection branch is new. Collapse
    # its disabled path before retaining the exact legacy scoring-tail check.
    branch='''        candidates=active
        if inp.experimental_penalty_hierarchy:
            ranked=[p for p in active if p.penalty_order is not None and p.penalty_order>0]
            if ranked:
                first=min(p.penalty_order for p in ranked)
                candidates=[p for p in ranked if p.penalty_order==first]
        taker=_weighted_choice(rng,candidates,[p.penalty_weight for p in candidates])
        if taker is None:
            taker=_weighted_choice(rng,candidates,[p.goal_weight for p in candidates])'''
    legacy='''        taker=_weighted_choice(rng,active,[p.penalty_weight for p in active])
        if taker is None:
            taker=_weighted_choice(rng,active,[p.goal_weight for p in active])'''
    assert current_source.count(branch)==1, 'Unexpected penalty hierarchy branch'
    current_source=current_source.replace(branch,legacy)
    assert source[source.index(tail):].rstrip()==current_source[current_source.index(tail):].rstrip(), 'Locked event/scoring/aggregate logic changed'
    changed=subprocess.check_output(['git','diff','--name-status',REFERENCE,'--','src'],text=True).splitlines()
    assert all(line.split('\t')[-1]=='src/fpl_v1_1_model/joint_simulator.py' or
        (line.startswith('A\t')and line.split('\t')[-1].startswith('src/fpl_v1_1_model/experimental_'))for line in changed),changed
    legacy=types.ModuleType('fpl_v1_1_model._gk_legacy_validation');legacy.__package__='fpl_v1_1_model';sys.modules[legacy.__name__]=legacy;exec(source,legacy.__dict__)
    def fixture(m):
        return m.MatchSimInput('H','A',1.7,1.2,tuple(m.PlayerSimInput(pid,team,pos,.8,.2,80.,20.,goal_weight=1.,assist_weight=1.,is_keeper=pos=='GK',lambda_saves=3.)for team in ['H','A']for pid,pos in[(team+'k','GK'),(team+'f','FWD')]))
    for seed in range(100):
        a=current.simulate_match(fixture(current),np.random.default_rng(seed));b=legacy.simulate_match(fixture(legacy),np.random.default_rng(seed))
        assert {k:asdict(v)for k,v in a.items()}=={k:asdict(v)for k,v in b.items()},seed
    assert current.simulate_many(fixture(current),n=100,seed=27)==legacy.simulate_many(fixture(legacy),n=100,seed=27)
    print('Original locked PM: exact seeded parity, all fields,100 fixtures and100-draw aggregate.')
if __name__=='__main__':check()
