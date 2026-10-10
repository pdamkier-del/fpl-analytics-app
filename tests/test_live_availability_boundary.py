"""Regression tests of the proposed boundary only, NOT locked live chain certification."""
import numpy as np
import pandas as pd
import pytest

from fpl_v1_1_model.live_availability_boundary import (
    BOUNDARY_VERSION,prepare_live_mm_release_candidate,
)
from fpl_v1_1_model.mm_release import validate_mm_release
from run_mm_unified_official_roles import compose


def example(gw=6,news_state="OUT",cap=0.):
    rows=[]
    for i in range(12):
        hard=(i==11)
        rows.append({
            "season":"2026-27","gw":gw,"fixture_uuid":"fixture-6","team_id":1,
            "player_uuid":f"player-{i}","player":f"Player {i}","team":"Team",
            "pos":"MID","cutoff":"2026-10-10T10:00:00+00:00",
            "p_start":0. if hard else 1.,"xmins":4. if hard else 80.,
            "expected_role":"CM","xi_assigned_role":"CM","xi_formation":"4-3-3",
            "start_minutes_mean":80.,"team_news_state":news_state if hard else "AVAILABLE",
            "team_news_availability_cap":cap if hard else 1.,
        })
    f=pd.DataFrame(rows)
    p=f.p_start.to_numpy(float)
    q=np.full(len(f),.20)
    sub=np.full(len(f),20.)
    assert np.allclose(compose(f,p,q,sub),f.xmins)
    return f,p,q,sub


@pytest.mark.parametrize("state",["OUT","SUSPENDED"])
def test_hard_unavailable_zero_cameo_preserves_frozen_compose(state):
    source,p,q,sub=example(news_state=state)
    original=source.copy(deep=True)
    x=prepare_live_mm_release_candidate(
        source,p_start=p,q_sub=q,sub_minutes=sub,
        origin_gw=6,news_scoped_gw=6)
    assert (x.loc[:10,"xmins"]==80).all()
    assert x.loc[11,"xmins"]==0
    assert x.loc[11,"mm_raw_xmins"]==4
    assert x.loc[11,"mm_raw_q_sub"]==.2
    assert x.loc[11,"live_effective_q_sub"]==0
    assert x.loc[11,"live_eligibility_minutes_removed"]==4
    assert set(x.live_eligibility_rule)=={BOUNDARY_VERSION}
    assert source.equals(original)  # frozen predictions untouched
    assert validate_mm_release(x)["exact11_max_abs_error"]<1e-9


def test_normal_players_do_not_change():
    source,p,q,sub=example(news_state="AVAILABLE",cap=1.)
    # Even when the cameo signal says four minutes for a nonstarter, retain it.
    x=prepare_live_mm_release_candidate(
        source,p_start=p,q_sub=q,sub_minutes=sub,
        origin_gw=6,news_scoped_gw=6)
    assert np.array_equal(x.xmins.to_numpy(),source.xmins.to_numpy())
    assert not x.live_eligibility_applied.any()


def test_no_current_news_reuse_across_future_gws():
    source,p,q,sub=example()
    with pytest.raises(ValueError,match="not scoped"):
        prepare_live_mm_release_candidate(source,p_start=p,q_sub=q,
            sub_minutes=sub,origin_gw=6,news_scoped_gw=7)
    source["gw"]=7
    with pytest.raises(ValueError,match="cannot be reused"):
        prepare_live_mm_release_candidate(source,p_start=p,q_sub=q,
            sub_minutes=sub,origin_gw=6,news_scoped_gw=6)


def test_hard_out_requires_zero_start_and_cap():
    source,p,q,sub=example()
    source.loc[11,"p_start"]=.1
    p[11]=.1
    # Cannot silently re-normalize a locked XI projection.
    with pytest.raises(ValueError):
        prepare_live_mm_release_candidate(source,p_start=p,q_sub=q,
            sub_minutes=sub,origin_gw=6,news_scoped_gw=6)
    source,p,q,sub=example(cap=.5)
    with pytest.raises(ValueError,match="hard-out"):
        prepare_live_mm_release_candidate(source,p_start=p,q_sub=q,
            sub_minutes=sub,origin_gw=6,news_scoped_gw=6)


def test_rejects_wrong_unfrozen_raw_minutes():
    source,p,q,sub=example()
    source.loc[11,"xmins"]=0  # illicit edited model output
    with pytest.raises(ValueError,match="do not match"):
        prepare_live_mm_release_candidate(source,p_start=p,q_sub=q,
            sub_minutes=sub,origin_gw=6,news_scoped_gw=6)
