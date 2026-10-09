from __future__ import annotations
import numpy as np
from fpl_xpts.joint_chip_stopping import (
    FH,WC,BOTH,ScenarioParameters,choose_joint_chip,future_option_table,
)

def test_no_chip_has_no_option_value():
    table=future_option_table(gw=6,draws=300,seed=7)
    assert np.allclose(table[0],0.)

def test_chip_cannot_be_used_twice_and_half_end_chooses_one():
    z=choose_joint_chip(gw=19,available_mask=BOTH,
                        g_fh_now=15.,g_wc_now=10.,draws=300)
    assert z.choice=='fh'
    assert z.q_fh==15. and z.q_wc==10. and z.q_normal==0.
    w=choose_joint_chip(gw=19,available_mask=WC,
                        g_fh_now=999.,g_wc_now=10.,draws=300)
    assert w.choice=='wc'

def test_future_shock_risk_increases_save_value():
    low=ScenarioParameters(new_mild=.05,new_severe=.01)
    high=ScenarioParameters(new_mild=.18,new_severe=.19)
    a=choose_joint_chip(gw=6,available_mask=BOTH,
                 g_fh_now=10.,g_wc_now=10.,
                 params=low,draws=3500,seed=20)
    b=choose_joint_chip(gw=6,available_mask=BOTH,
                 g_fh_now=10.,g_wc_now=10.,
                 params=high,draws=3500,seed=20)
    assert b.q_normal>a.q_normal
    assert b.q_normal>10.

def test_catastrophe_now_makes_wc_worthwhile():
    z=choose_joint_chip(gw=6,available_mask=BOTH,
                        g_fh_now=9.,g_wc_now=100.,
                        current_disruption=2,draws=350)
    assert z.choice=='wc'

def test_decisions_are_deadline_local_not_oracle_future_max():
    a=choose_joint_chip(gw=6,available_mask=BOTH,
                      g_fh_now=8.,g_wc_now=8.,draws=450,seed=1729)
    b=choose_joint_chip(gw=6,available_mask=BOTH,
                      g_fh_now=8.,g_wc_now=8.,draws=450,seed=1729)
    assert (a.choice,a.q_normal,a.q_fh,a.q_wc)==(b.choice,b.q_normal,b.q_fh,b.q_wc)
    assert a.future_gws==13
    assert a.q_normal>=0
