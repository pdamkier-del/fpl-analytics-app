from __future__ import annotations
"""Experimental *joint* FH/WC stopping layer (not locked or calibrated).

Incremental chip values are scored on the same six-GW TS objective at the
CURRENT deadline. Stochastic continuation is a small-state approximation:
healthy/mild/severe squad disruption, and two binary chip rights. The player
forecast, locked TS transfer planner and permanent WC optimiser are unchanged.

Future possibilities are observed one GW at a time inside backwards induction.
Crucially, this is not a clairvoyant max of future gap values.
"""
from dataclasses import dataclass
import numpy as np

FH=1
WC=2
BOTH=3

@dataclass(frozen=True)
class ScenarioParameters:
    """Uncalibrated availability-shock sensitivity assumptions.

    Numbers are explicit research assumptions, NOT empirical injury probabilities.
    'Severe' represents correlated 2-4 starting-player absences, not necessarily
    injuries. BGW/DGW are separate one-week structural disruptions.
    """
    new_mild: float=.16
    new_severe: float=.055
    severe_persistence: float=.38
    mild_persistence: float=.48
    replacement_xp: float=3.2
    baseline_fh_gain: float=4.0
    baseline_wc_gain: float=4.0
    scenario_noise: float=1.5
    bgw_p: float=.025
    dgw_p: float=.035

@dataclass
class DecisionResult:
    choice: str
    q_normal: float
    q_fh: float
    q_wc: float
    v_save_fh: float
    v_save_wc: float
    g_fh_now: float
    g_wc_now: float
    current_disruption: int
    future_gws: int
    future_state_values: dict
    assumptions: dict

def _transition(h:int,p:ScenarioParameters):
    if h==0:
        s=min(.85,p.new_severe)
        m=min(1.-s,p.new_mild)
        return np.array([1.-s-m,m,s])
    if h==1:
        s=min(.85,p.new_severe*1.7)
        m=p.mild_persistence
        return np.array([1.-s-m,m,s])
    s=p.severe_persistence
    m=min(.90-s,.35)
    return np.array([1.-s-m,m,s])

def _event_gains(health:np.ndarray,p:ScenarioParameters,
                 bgw:np.ndarray,dgw:np.ndarray,noise:np.ndarray,ft:int):
    """Explicit correlated squad shocks with TS mitigation.

    Health severity is the damage to a *specific already-owned squad*, not
    a per-player injury label. Free transfers mitigate WC's persistent reset
    gain; autosubs moderate one-week FH loss. BGW/DGW improve FH more than WC.
    """
    affected=np.where(health==0,0,np.where(health==1,1,3))
    # TS can replace up to its banked FT; the remaining absence cost is
    # relative to an available substitute. A severe shock has a tail.
    unresolved=np.maximum(0,affected-min(max(0,ft),2))
    short_loss=affected*p.replacement_xp*.72
    persistent_loss=(unresolved*p.replacement_xp*1.55+
                     (health==2)*p.replacement_xp*1.5)
    # BGW is a one-week roster concentration risk; the WC rebuild should
    # not be rewarded as much for a one-week blank.
    fh=np.maximum(0.,p.baseline_fh_gain+short_loss+
                  bgw*p.replacement_xp*2.6+
                  dgw*p.replacement_xp*1.4+noise)
    wc=np.maximum(0.,p.baseline_wc_gain+persistent_loss+
                  bgw*p.replacement_xp*.25+
                  dgw*p.replacement_xp*.65+noise*.8)
    return fh,wc

def future_option_table(*,gw:int,ft:int=1,params:ScenarioParameters=ScenarioParameters(),
                        draws:int=2500,seed:int=20261009,
                        bgw_by_gw:dict[int,float]|None=None,
                        dgw_by_gw:dict[int,float]|None=None):
    """Return V_{t+1}(mask,health) at the CURRENT deadline.

    At each simulated FUTURE deadline the current week's shock is revealed,
    THEN choose to exercise, but later random shocks are not revealed.
    """
    end=19 if gw<=19 else 38
    if not 1<=gw<=38:raise ValueError('GW must be 1..38')
    if draws<100:raise ValueError('draws must be >=100')
    v=np.zeros((4,3),float)
    rng=np.random.default_rng(seed+gw)
    for target in range(end,gw,-1):
        after=np.zeros((4,3))
        for previous_h in range(3):
            health=rng.choice(3,size=draws,p=_transition(previous_h,params))
            pbg=float((bgw_by_gw or {}).get(target,params.bgw_p))
            pdg=float((dgw_by_gw or {}).get(target,params.dgw_p))
            pbg=np.clip(pbg,0,1);pdg=np.clip(pdg,0,1-pbg)
            kind=rng.choice(3,size=draws,p=[1-pbg-pdg,pbg,pdg])
            bgw=kind==1;dgw=kind==2
            noise=rng.normal(0,params.scenario_noise,size=draws)
            fh,wc=_event_gains(health,params,bgw,dgw,noise,ft)
            for mask in range(4):
                # Current week's disruption becomes next week's carried health
                choices=[v[mask,health]]
                if mask&FH:choices.append(fh+v[mask&~FH,health])
                if mask&WC:choices.append(wc+v[mask&~WC,0])
                after[mask,previous_h]=float(np.mean(np.maximum.reduce(choices)))
        v=after
    return v

def choose_joint_chip(*,gw:int,available_mask:int,g_fh_now:float,
                      g_wc_now:float,current_disruption:int=0,ft:int=1,
                      params:ScenarioParameters=ScenarioParameters(),
                      draws:int=2500,seed:int=20261009,
                      bgw_by_gw:dict[int,float]|None=None,
                      dgw_by_gw:dict[int,float]|None=None)->DecisionResult:
    if available_mask not in range(4):raise ValueError('invalid chip mask')
    if current_disruption not in (0,1,2):raise ValueError('invalid health class')
    future=future_option_table(gw=gw,ft=ft,params=params,draws=draws,seed=seed,
                               bgw_by_gw=bgw_by_gw,dgw_by_gw=dgw_by_gw)
    h=current_disruption;m=available_mask
    qnormal=float(future[m,h])
    qfh=float(g_fh_now+future[m&~FH,h]) if m&FH else -float('inf')
    qwc=float(g_wc_now+future[m&~WC,0]) if m&WC else -float('inf')
    vals={'normal':qnormal,'fh':qfh,'wc':qwc}
    # Tie breaks preserve chips.
    choice=max(('normal','fh','wc'),key=lambda x:(vals[x],x=='normal'))
    return DecisionResult(choice,qnormal,qfh,qwc,
                          float(future[FH,h]),float(future[WC,h]),
                          float(g_fh_now),float(g_wc_now),h,
                          (19 if gw<=19 else 38)-gw,
                          {str(mask):[float(x) for x in future[mask]] for mask in range(4)},
                          dict(vars(params)))
