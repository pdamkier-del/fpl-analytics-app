"""B-only source-known persistent eligibility; no production imports."""
import re
import numpy as np
import pandas as pd
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
VERSION='B-horizon-eligibility-v2'

def departure_kind(player):
    if player.get('status')!='u':return None
    text=str(player.get('news')or'')
    if re.search(r'\b(?:joined|signed|transferred|left|moved)\b.*\bpermanently\b',text,re.I):return 'permanent_exit'
    if re.search(r'\bloan\b.*\b(?:rest|remainder|end).{0,20}\bseason\b|\bseason.long\s+loan\b',text,re.I):return 'season_loan'
    return 'ambiguous_unavailable'

def annotate(frame,bootstrap,observed_at):
    cut=pd.Timestamp(frame.cutoff.iloc[0]);seen=pd.Timestamp(observed_at)
    if cut.tzinfo is None or seen.tzinfo is None or seen>=cut:raise ValueError('Eligibility evidence must precede cutoff')
    if frame.cutoff.nunique()!=1:raise ValueError('One eligibility origin required')
    official={p['id']:p for p in bootstrap['elements']};out=frame.copy();kinds=[];clocks=[]
    for r in out.itertuples():
        p=official[int(r.fpl_element)]
        if int(p['team'])!=int(r.team_id):raise ValueError('Eligibility source club mismatch')
        added=p.get('news_added')
        if added and pd.Timestamp(added)>seen:raise ValueError('News postdates source receipt')
        kind=departure_kind(p);kinds.append(kind);clocks.append(seen.isoformat())
    out['persistent_absence_kind']=kinds;out['eligibility_known_at']=clocks
    # Ambiguous status=u is not silently declared available. Retain identity and
    # an explicit Not Available reason; fail if a legal XI cannot be constructed.
    out['persistent_availability_cap']=np.where(out.persistent_absence_kind.notna(),0.,1.)
    return out

def constrain(predicted):
    if 'persistent_availability_cap'not in predicted:return predicted
    out=predicted.copy();cap=out.persistent_availability_cap.to_numpy(float)
    if 'medical_return_cap'in out:cap=np.minimum(cap,out.medical_return_cap.to_numpy(float))
    if not np.isfinite(cap).all()or ((cap<0)|(cap>1)).any():raise ValueError('Invalid horizon availability cap')
    if 'availability_cap'in out:cap=np.minimum(cap,out.availability_cap.to_numpy(float))
    original=out.p.to_numpy(float).copy();prior=original.copy()
    # The return probability is applied once to the latent role probability.
    if 'medical_return_cap'in out:prior*=out.medical_return_cap.to_numpy(float)
    prior=np.minimum(prior,cap)
    for _,indices in out.groupby(['fixture_uuid','team_id'],sort=True).indices.items():
        indices=np.asarray(indices)
        for keeper,need in [(True,1),(False,10)]:
            mask=out.iloc[indices].pos.isin(['GK','GKP']).to_numpy()==keeper;jj=indices[mask]
            if not len(jj):raise ValueError('Missing position group for horizon XI')
            prior[jj]=project_exact_starters_with_caps(out.iloc[jj].reset_index(drop=True),prior[jj],cap[jj],starters=need)
    out['p']=prior;out['q']=np.minimum(out.q,np.divide(np.maximum(cap-prior,0),1-prior,out=np.zeros(len(out)),where=prior<1))
    out['availability_cap']=cap;out['x']=out.p*out.s+(1-out.p)*out.q*out.c
    out['role_horizon_absence']=out.persistent_availability_cap.eq(0)
    if not out.loc[cap==0,['p','q','x']].eq(0).all().all():raise AssertionError('Persistent absence consumes minutes')
    return out
