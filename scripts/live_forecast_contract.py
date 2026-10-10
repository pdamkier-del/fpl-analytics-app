"""Validate full current-player, six-GW final forecasts without altering models."""
import math


def validate_forecast_rows(rows, official_players, next_gw, horizon=6):
    expected={int(p['id']) for p in official_players}
    if not isinstance(rows,list) or len(rows)!=len(expected):
        raise RuntimeError('Incomplete current player forecast coverage')
    ids=[r.get('id') for r in rows]
    if len(set(ids))!=len(ids) or set(ids)!=expected:
        raise RuntimeError('Duplicate or missing current player identity')
    required=set(range(next_gw,min(38,next_gw+horizon-1)+1))
    for row in rows:
        weeks=row.get('weeks')
        if not isinstance(weeks,list) or len(weeks)!=len(required):
            raise RuntimeError('Missing six-GW forecast per player')
        if {w.get('gw') for w in weeks}!=required:
            raise RuntimeError('Duplicate, stale or missing forecast GW')
        for w in weeks:
            for key in ('xpts','xmins'):
                value=w.get(key)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                    raise RuntimeError('Nonfinite or missing '+key)
            if w['xmins']<0:raise RuntimeError('Negative minutes')
            # Do not impose single-match upper bounds on DGW aggregate forecasts.
            # Negative points are also possible under the original event model.
            for aliases in [('p_start','pstart'),('q_sub','p_sub_given_not_start')]:
                value=next((w[k] for k in aliases if k in w),None)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
                    raise RuntimeError('Invalid probability '+aliases[0])
    return {'players':len(ids),'gws':sorted(required)}
