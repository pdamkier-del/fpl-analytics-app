"""Fitted B assist-allocation candidate; no MM or event-count changes.

This interface only replaces PlayerSimInput.assist_weight after MM/PhysicalKernel.
Activation requires an accepted, content-linked assist policy. No named players.
"""
from dataclasses import replace
import numpy as np

def assist_features(m,p):
    # Existing pregame role + expected exposure; the offset already includes minutes.
    return np.array([p.position=='DEF',p.position=='FWD',p.is_keeper,(p.position=='FWD')*float(m.get('baseline_xm',0))/90,m.get('tactical_role')in ['q_RW_slow','q_LW_slow','q_RAM_slow','q_LAM_slow','q_CAM_slow','q_SS_slow']],float)


def apply(inp,dist,meta,policy,arm):
    if arm=='baseline':return inp,dist
    if arm!='assist':raise ValueError('This branch owns assist calibration only; MM candidates are excluded')
    beta=np.array(policy['assist']['coef']);players=[]
    for p in inp.players:
        factor=float(np.exp(np.clip(assist_features(meta.get(p.player_id,{}),p)@beta,-np.log(2),np.log(2))))
        players.append(replace(p,assist_weight=p.assist_weight*factor))
    return replace(inp,players=tuple(players)),dist
