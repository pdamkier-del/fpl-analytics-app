"""MM-only source/role integration. No production imports of this module.

Reuses the existing cap projection and frozen role forecasts. No new fitted
coefficients. Unknown is not healthy; training is not clearance. Role carry is
an explicitly tested alternative, never a manual star-player adjustment.
"""
import re
import numpy as np
import pandas as pd
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps

INJURIES=['hamstring','groin','ankle','knee','calf','thigh','hip','back','foot','heel','achilles','shoulder','rib','concussion','illness','knock','muscle','leg','wrist']
def medical_fields(row):
    text=str(row.get('raw_news')or'');low=text.lower();kind=next((s for s in INJURIES if (re.search(r'\bback (?:injury|problem|pain)\b',low)if s=='back'else re.search(r'\b'+s+r'\b',low))),None)
    # Keep only the exact source expression; do not invent an absent year/day.
    window=re.search(r'(?:Expected back|out for|sidelined for)[^.;]*',text,re.I)
    training='RETURNED_TO_TRAINING'if any(s in low for s in ['back in training','returned to training'])else None
    medical=bool(kind or 'injury'in low)
    return dict(injury_type=kind,medical_flag=bool(medical and row.get('raw_status')in ['i','d']),confirmed_medical_out=bool(medical and row.get('raw_status')=='i'),expected_absence_text=window.group(0)if window else None,return_earliest=None,return_latest=None,training_state=training)


def eligible_news(row,cutoff,club):
    if not row or not row.get('player_uuid')or row.get('identity_status')!='mapped'or not row.get('timing_verified')or not row.get('deadline_matches'):return False
    cut=pd.Timestamp(cutoff);effective=pd.Timestamp(row['effective_at'])
    if cut.tzinfo is None or effective.tzinfo is None:raise ValueError('Timezone required')
    if effective>=cut or int(row['team_id'])!=int(club):return False
    if row.get('news_added')and pd.Timestamp(row['news_added'])>effective:return False
    return int(row['gw'])in [row.get('payload_current_event'),row.get('payload_next_event')]


def bounded_news(frame,chance=False,project=False):
    """Cap marginal appearance; never multiply duplicated availability twice."""
    f=frame.copy();caps=np.ones(len(f));known=f.news_eligible.to_numpy(bool);state=f.news_state.astype(str).to_numpy();hard=known&np.isin(state,['OUT','SUSPENDED']);caps[hard]=0.
    if chance:
        v=pd.to_numeric(f.news_chance,errors='coerce').to_numpy(float);has=known&np.isfinite(v)
        if np.any((v[has]<0)|(v[has]>100)):raise ValueError('Invalid sourced chance')
        caps[has]=np.minimum(caps[has],v[has]/100)
    p=np.minimum(f.p.to_numpy(float),caps);q=f.q.to_numpy(float).copy();q=np.minimum(q,np.divide(np.maximum(caps-p,0),1-p,out=np.zeros(len(p)),where=p<1));q[hard]=0.
    f['projection_infeasible']=False
    if project:
        # Preserve existing hard endpoints unless fresh official AVAILABLE
        # supersedes them. No invented available replacement in an infeasible XI.
        preserved=f.p.eq(0)&f.q.eq(0)&~(f.news_eligible&f.news_state.isin(['AVAILABLE','RETURNED_AVAILABLE']))
        cc=np.where(preserved,0.,caps);out=p.copy()
        for _,idx in f.groupby(['fixture_uuid','team_id'],sort=True).indices.items():
            idx=np.asarray(idx);isgk=f.iloc[idx].pos.isin(['GK','GKP']).to_numpy()
            for mask,need in [(isgk,1),(~isgk,10)]:
                jj=idx[mask]
                try:out[jj]=project_exact_starters_with_caps(f.iloc[jj].reset_index(drop=True),p[jj],cc[jj],starters=need)
                except ValueError:f.iloc[jj,f.columns.get_loc('projection_infeasible')]=True
        p=out;q=np.minimum(q,np.divide(np.maximum(caps-p,0),1-p,out=np.zeros(len(p)),where=p<1))
    f['p']=p;f['q']=q;f['availability_cap']=caps;f['x']=p*f.s+(1-p)*q*f.c
    return f


def carry_normal_role(frame,duration_only=False):
    """First sourced return origin reuses last same-club fully-available role.

    Medical OUT does not update that latent state. UNKNOWN never establishes it.
    This alternative must be compared with the same role+hard-news control.
    """
    f=frame.copy();f['carried_normal_role']=False
    for _,idx in f.groupby(['season','player_uuid'],sort=False).groups.items():
        order=f.loc[idx].sort_values(['cutoff','fixture_uuid']);latent=None;medical=False;handled=None
        for cut,g in order.groupby('cutoff',sort=True):
            row=g.iloc[0];club=int(row.team_id)
            if latent is not None and latent['club']!=club:latent=None;medical=False
            if not row.news_eligible:continue
            if row.news_medical_out:medical=True;continue
            if row.news_state not in ['AVAILABLE','RETURNED_AVAILABLE']:continue
            if medical and latent is not None and pd.Timestamp(latent['cutoff'])<pd.Timestamp(cut):
                cols=['s']if duration_only else ['p','s','q','c']
                for col in cols:f.loc[g.index,col]=latent[col]
                f.loc[g.index,'carried_normal_role']=True;medical=False;handled=cut
            elif medical:
                # No verified pre-injury role: do not manufacture one, but let
                # subsequent available observations establish a new state.
                medical=False;latent=dict(club=club,cutoff=cut,**{k:float(row[k])for k in ['p','s','q','c']})
            elif not medical and handled!=cut:
                latent=dict(club=club,cutoff=cut,**{k:float(row[k])for k in ['p','s','q','c']})
    f['x']=f.p*f.s+(1-f.p)*f.q*f.c
    return bounded_news(f)
