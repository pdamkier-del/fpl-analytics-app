import importlib.util
from pathlib import Path
import pandas as pd
spec=importlib.util.spec_from_file_location('preflight',Path(__file__).resolve().parents[1]/'scripts/audit_frozen_live_component_preflight.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_absent_live_sources_are_explicit(tmp_path):
    sources={name:tmp_path/name for name in m.SOURCES}
    r=m.inspect(sources)
    assert not r['ready']
    assert len(r['blockers'])==len(m.SOURCES)
    assert all(v['status']=='ABSENT' for v in r['sources'].values())
def test_missing_conditional_minutes_and_assist_prior_are_flagged(tmp_path):
    sources={name:tmp_path/(name+'.csv') for name in m.SOURCES}
    for name,path in sources.items():
        pd.DataFrame([{field:1 for field in m.FIELDS[name] if field not in ['start_minutes_mean']}]).to_csv(path,index=False)
    r=m.inspect(sources)
    assert not r['ready']
    assert any('start_minutes_mean' in s for s in r['blockers'])
    assert any('assist_probability_per_goal' in s for s in r['blockers'])
