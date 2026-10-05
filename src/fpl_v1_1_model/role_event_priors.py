"""Soft predeadline role distributions for event priors, with position fallback.

Role exposure is fractional: a 70% RB / 30% RW player contributes that share
of historical minutes/events to each role pool within their FPL position.
Only q states known before the corresponding fixture may enter these pools.
"""
import numpy as np
import pandas as pd
from .role_classifier import ROLES

KEYS=['fixture_uuid','player_uuid','team_id']
QCOLS=['q_'+r+'_slow' for r in ROLES]
EVENTS={'goal':'xg','assist':'xa','dc':'defcon_count'}

def validate_roles(roles):
    if roles[KEYS].duplicated().any():raise ValueError('Duplicate role keys')
    q=roles[QCOLS].to_numpy(float)
    if not np.isfinite(q).all() or (q<0).any() or (q>1).any():
        raise ValueError('Invalid role probabilities')
    total=q.sum(axis=1)
    if not np.all(np.isclose(total,0,atol=1e-10)|np.isclose(total,1,atol=1e-10)):
        raise ValueError('Role mass must sum to one or zero for unknown')
    cut=pd.to_datetime(roles.cutoff,utc=True,errors='raise')
    known=pd.to_datetime(roles.max_history_known_at,utc=True,errors='raise')
    if cut.isna().any() or ((total>0)&known.isna()).any() or (known>=cut).any():
        raise ValueError('Role state violates predeadline availability')

def role_priors_at_deadline(history, historical_roles, roster, target_roles, cutoff, role_tau_minutes):
    """Return broad-position and role-mixed priors using past outcomes only.

History requires available_at/kickoff_at, minutes, fpl_position and events.
Target roles are forecast q distributions, never observed target positions.
The smoothing strength is a fixed positive exposure in minutes per role.
"""
    if not np.isfinite(role_tau_minutes) or role_tau_minutes<=0:
        raise ValueError('Positive role prior exposure required')
    cutoff=pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:raise ValueError('Timezone-aware cutoff required')
    validate_roles(historical_roles);validate_roles(target_roles)
    if roster.empty or roster[KEYS].duplicated().any():raise ValueError('Unique nonempty roster required')
    if (pd.to_datetime(target_roles.cutoff,utc=True)>cutoff).any():
        raise ValueError('Future target role state')
    h=history.copy()
    h['available_at']=pd.to_datetime(h.available_at,utc=True,errors='raise')
    h['kickoff_at']=pd.to_datetime(h.kickoff_at,utc=True,errors='raise')
    if h.available_at.isna().any() or h.kickoff_at.isna().any() or (h.available_at<h.kickoff_at).any():
        raise ValueError('Invalid historical availability')
    h=h[h.available_at<cutoff].copy()
    if h[KEYS].duplicated().any():raise ValueError('Duplicate historical rows')
    if set(h.fixture_uuid)&set(roster.fixture_uuid):raise ValueError('Target outcomes in history')
    h['pos']=h.fpl_position.replace({'GKP':'GK'})
    fields=['minutes',*EVENTS.values()]
    if not np.isfinite(h[fields].to_numpy(float)).all() or (h[fields].to_numpy(float)<0).any():
        raise ValueError('Missing or invalid historical event values')
    h=h.merge(historical_roles[KEYS+QCOLS+['cutoff']].rename(columns={'cutoff':'role_cutoff'}),
              on=KEYS,how='left',validate='one_to_one')
    observed_q=h[QCOLS].fillna(0).to_numpy(float)
    role_cut=pd.to_datetime(h.role_cutoff,utc=True,errors='raise')
    if ((observed_q.sum(axis=1)>0)&(role_cut>h.kickoff_at)).any():
        raise ValueError('Historical role state later than its fixture')
    targets=roster[KEYS+['pos']].merge(target_roles[KEYS+QCOLS],on=KEYS,how='left',validate='one_to_one')
    targets['pos']=targets.pos.replace({'GKP':'GK'})
    rows=[]
    for pos,group in targets.groupby('pos',sort=False):
        past=h[h.pos==pos];exposure=float(past.minutes.sum())
        if exposure<=0:raise ValueError('No historical position exposure for '+str(pos))
        q=past[QCOLS].fillna(0).to_numpy(float)
        role_minutes=q.T@past.minutes.to_numpy(float)
        qt=group[QCOLS].fillna(0).to_numpy(float)
        known=qt.sum(axis=1)>0
        values=group[KEYS].copy();values['role_known']=known
        values['pooled_role_minutes']=qt@role_minutes
        for kind,event in EVENTS.items():
            broad=90*float(past[event].sum())/exposure
            byrole=90*(q.T@past[event].to_numpy(float)+role_tau_minutes*broad/90)/(role_minutes+role_tau_minutes)
            mixed=np.where(known,qt@byrole,broad)
            if kind=='dc' and pos=='GK':mixed[:]=0.;broad=0.
            values[kind+'_position_prior90']=broad
            values[kind+'_role_prior90']=mixed
        rows.append(values)
    return pd.concat(rows,ignore_index=True)
