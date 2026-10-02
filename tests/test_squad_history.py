from pathlib import Path
import json
import numpy as np
import pandas as pd
from fpl_v1_1_model.squad_history import SquadHistory,squad_label,unknown_state

ROOT=Path(__file__).resolve().parents[1]


def test_incomplete_squad_is_not_an_absence_label():
    assert squad_label(False,False,0,False) is None
    assert squad_label(False,False,0,True)==0
    assert squad_label(True,False,0,False)==1
    assert squad_label(False,False,12,False)==1
    assert squad_label(True,False,0,True,withdrawn=True) is None


def test_squad_history_is_cutoff_safe_and_registration_safe():
    h=SquadHistory();h.add_game(1,10,'a',{'p':{'squad':1,'started':False,'minutes':15},'u':{'squad':None,'started':False,'minutes':0}})
    assert h.state(1,10)==({},None)
    state,_=h.state(1,11)
    assert state['p']['squad_rate_fast']>0.5 and state['p']['bench_sub_rate_fast']>0.5
    assert state['u']==unknown_state()
    h.add_game(1,20,'b',{'p':{'squad':0,'started':False,'minutes':0},'new':{'squad':1,'started':True,'minutes':90}})
    assert h.state(1,11)[0]==state
    later,_=h.state(1,21)
    assert later['new']['squad_rate_fast']>0.5
    assert later['new']['squad_evidence_fast']==state['p']['squad_evidence_fast']


def test_saved_squad_factorization_and_development_choice():
    root=ROOT/'analysis/results/squad-minutes-v1'
    f=pd.read_csv(root/'reused_holdout_diagnostic_predictions.csv.gz',usecols=['cutoff','max_squad_history_known_at',
       'control_p_start','p_squad_given_not_start','p_sub_given_bench','p_sub_given_not_start_factorized',
       'p_squad_unconditional','factorized_sub_xmins','start_minutes_mean','cameo_minutes_mean'])
    assert len(f)==13987
    assert (pd.to_datetime(f.max_squad_history_known_at,utc=True)<pd.to_datetime(f.cutoff,utc=True)).all()
    assert np.allclose(f.p_sub_given_not_start_factorized,f.p_squad_given_not_start*f.p_sub_given_bench)
    assert (f.p_squad_unconditional>=f.control_p_start-1e-12).all()
    expected=f.control_p_start*f.start_minutes_mean+(1-f.control_p_start)*f.p_sub_given_not_start_factorized*f.cameo_minutes_mean
    assert np.allclose(expected,f.factorized_sub_xmins)
    metrics=json.loads((root/'development_metrics.json').read_text());protocol=json.loads((root/'protocol.json').read_text())
    chosen=min(['control','factorized_sub','factorized_full'],key=lambda n:metrics[n]['xmins_mae'])
    assert chosen==protocol['selected_on_development_mae']
    assert 'NOT fresh' in protocol['holdout_status']
