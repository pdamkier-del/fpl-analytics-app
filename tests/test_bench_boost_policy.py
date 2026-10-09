import pandas as pd
import pytest
from fpl_xpts.bench_boost_policy import evaluate_bench_boost,bb_threshold,post_wildcard_bb_opportunities

def lineup():
    # Valid 4-4-2; bench consists of DEF, MID, FWD and GKP.
    rows=[]
    roles=['XI']*15
    roles[0]='C'; roles[2]='VC'
    for i in range(11,15):
        roles[i]=['Bench 1','Bench 2','Bench 3','GK bench'][i-11]
    positions=['GKP']+['DEF']*4+['MID']*4+['FWD']*2+['DEF','MID','FWD','GKP']
    for i,(role,position) in enumerate(zip(roles,positions),1):
        rows.append(dict(id=i,role=role,position=position,p_play=1.,xpts_mean=float(1+i%4)))
    return pd.DataFrame(rows)

def test_all_starters_play_bb_gets_entire_bench():
    x=lineup()
    r=evaluate_bench_boost(x)
    assert r.incremental_xp==pytest.approx(r.bench_xp)
    assert r.expected_autosub_xp==pytest.approx(0.0)

def test_goalkeeper_autosub_is_not_extra_bb_points():
    x=lineup();x.loc[x.id.eq(1),'p_play']=0
    r=evaluate_bench_boost(x)
    assert r.incremental_xp==pytest.approx(r.bench_xp-float(x.loc[x.id.eq(15),'xpts_mean'].iloc[0]))

def test_outfield_autosub_reduces_bb_increment():
    x=lineup();x.loc[x.id.eq(2),'p_play']=0
    r=evaluate_bench_boost(x)
    assert r.expected_autosub_xp==pytest.approx(float(x.loc[x.id.eq(12),'xpts_mean'].iloc[0]))

def test_half_probability_autosub():
    x=lineup();x.loc[x.id.eq(2),'p_play']=.5
    r=evaluate_bench_boost(x)
    assert r.expected_autosub_xp==pytest.approx(float(x.loc[x.id.eq(12),'xpts_mean'].iloc[0])*.5)

def test_bb_caution_decreases_toward_each_half_end():
    assert bb_threshold(1,15)==15
    assert bb_threshold(19,15)==0
    assert bb_threshold(20,15)==15
    assert bb_threshold(38,15)==0

def test_invalid_bb_input():
    with pytest.raises(ValueError):evaluate_bench_boost(lineup().iloc[:-1])
    with pytest.raises(ValueError):bb_threshold(39,5)

def test_post_wc_options_start_next_week_and_end_at_half():
    x=lineup()
    horizons=pd.concat([x.assign(gw=g) for g in (17,18,19,20)],ignore_index=True)
    opportunity=post_wildcard_bb_opportunities(
        wc_gw=17,wc_squad_ids=list(range(1,16)),asof_projection=horizons,
        lookahead=5)
    assert opportunity.bb_gw.tolist()==[18,19]
    assert (opportunity.bb_incremental_xp>=0).all()
