#!/usr/bin/env python3
"""Pinned source plus exact seeded default replay against original PM.

The reviewed point-accounting/input extractions changed source text, not model
behavior. Verify those exact implementations and execute the original oracle;
never accept an arbitrary scoring-tail edit merely because B gates pass.
"""
from dataclasses import asdict,fields
from pathlib import Path
import hashlib,subprocess,sys,types
import numpy as np
from fpl_v1_1_model import joint_simulator as current

REFERENCE='49b5a82976a264da51624bac98990d371116a488'
ROOT=Path(__file__).resolve().parents[1]
REVIEWED={
    'src/fpl_v1_1_model/joint_simulator.py':'557857c7bc3bf56db75e0505a50606b4704c3534fdcced502783a3da34e0c953',
    'src/fpl_v1_1_model/point_accounting.py':'3256eb0d422064b24340e985863f84ed2b3c203c1db1ac03d5534a331b72b26d',
    'src/fpl_v1_1_model/fixture_input.py':'2a738326f18355c9515d410fd5ca907725531c22475175ec40560738be673037',
}

B_ONLY_ADDITIONS={
    'src/fpl_v1_1_model/b_event_simulator.py':'261ab1cabafcd6146125c1c499313d275e6019f5a296780ec92f7ee7df37a68b',
}


def require_reviewed_default_sources(root=ROOT):
    for name,digest in REVIEWED.items():
        assert hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()==digest, 'Unreviewed default source change: '+name


def check():
    require_reviewed_default_sources()
    source=subprocess.check_output(['git','show',REFERENCE+':src/fpl_v1_1_model/joint_simulator.py'],text=True)
    changed=subprocess.check_output(['git','diff','--name-status',REFERENCE,'--','src'],text=True).splitlines()
    assert all(line.split('\t')[-1]in REVIEWED or
        (line.startswith('A\t')and(line.split('\t')[-1].startswith('src/fpl_v1_1_model/experimental_')or line.split('\t')[-1]in B_ONLY_ADDITIONS))for line in changed),changed
    for name,digest in B_ONLY_ADDITIONS.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, 'Unreviewed B event implementation: '+name
    legacy=types.ModuleType('fpl_v1_1_model._gk_legacy_validation');legacy.__package__='fpl_v1_1_model'
    sys.modules[legacy.__name__]=legacy;exec(source,legacy.__dict__)
    def fixture(m):
        return m.MatchSimInput('H','A',1.7,1.2,tuple(m.PlayerSimInput(pid,team,pos,.8,.2,80.,20.,goal_weight=1.,assist_weight=1.,is_keeper=pos=='GK',lambda_saves=3.)for team in ['H','A']for pid,pos in[(team+'k','GK'),(team+'f','FWD')]))
    for seed in range(100):
        a=current.simulate_match(fixture(current),np.random.default_rng(seed));b=legacy.simulate_match(fixture(legacy),np.random.default_rng(seed))
        assert {k:asdict(v)for k,v in a.items()}=={k:asdict(v)for k,v in b.items()},seed
    assert current.simulate_many(fixture(current),n=100,seed=27)==legacy.simulate_many(fixture(legacy),n=100,seed=27)
    # Exercise actual frozen full rosters and all component inputs as well as
    # the original small fixture. New B flags must remain disabled here.
    from run_vfinal_integrated import build_final_frame,make_vfinal_input
    frame=build_final_frame();cases=list(frame.groupby('fixture_uuid',sort=True))[:100]
    assert len(cases)==100,'Incomplete original-default full-roster replay'
    player_fields={f.name for f in fields(legacy.PlayerSimInput)}
    match_fields={f.name for f in fields(legacy.MatchSimInput)}-{'players'}
    for i,(fx,g)in enumerate(cases):
        inp,_=make_vfinal_input(g)
        assert not any(getattr(inp,f.name)for f in fields(inp)if f.name.startswith('experimental_')),'Default B switch enabled'
        assert all(p.goalkeeper_start_pmf is None and p.penalty_order is None and p.penalty_fallback_weight is None for p in inp.players)
        old=legacy.MatchSimInput(**{k:getattr(inp,k)for k in match_fields},players=tuple(
            legacy.PlayerSimInput(**{k:getattr(p,k)for k in player_fields})for p in inp.players))
        a=np.random.default_rng(20261025+i);b=np.random.default_rng(20261025+i)
        for _ in range(20):
            x=current.simulate_match(inp,a);y=legacy.simulate_match(old,b)
            assert {k:asdict(v)for k,v in x.items()}=={k:asdict(v)for k,v in y.items()},fx
            assert a.bit_generator.state==b.bit_generator.state,fx
        assert current.simulate_many(inp,n=20,seed=i)==legacy.simulate_many(old,n=20,seed=i),fx
    print('Original locked PM: pinned reviewed source, exact seeded events/RNG/aggregate parity on 100 full-roster fixtures plus 100 original fixtures.')


if __name__=='__main__':check()
