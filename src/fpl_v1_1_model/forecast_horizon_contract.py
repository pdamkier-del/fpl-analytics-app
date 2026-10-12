"""Audit guard; never repairs missing future forecasts with hindsight or zeroes."""

def require_horizon(frame,origin,horizon=6,last_gw=38):
    required=set(range(origin,min(origin+horizon,last_gw+1)))
    targets=set(map(int,frame.loc[frame.decision_gw.eq(origin),'gw'].unique()))
    missing=sorted(required-targets)
    if missing:
        raise ValueError(f'Incomplete forecast horizon at origin GW{origin}: missing {missing}')
    return sorted(required)

def horizon_report(frame,horizon=6,last_gw=38):
    origins=sorted(map(int,frame.decision_gw.unique()));missing={}
    for origin in origins:
        required=set(range(origin,min(origin+horizon,last_gw+1)))
        targets=set(map(int,frame.loc[frame.decision_gw.eq(origin),'gw'].unique()))
        if required-targets:missing[str(origin)]=sorted(required-targets)
    return dict(origins=len(origins),actual_origin_target_pairs=len(frame[['decision_gw','gw']].drop_duplicates()),required_origin_target_pairs=sum(min(horizon,last_gw-o+1) for o in origins),missing=missing,complete=not missing)
