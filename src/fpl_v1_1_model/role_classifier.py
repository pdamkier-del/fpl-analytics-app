"""Deterministic, formation-first classifier v1 (historical roles, not forecasts).

Confirmed lineup order supplies a slot; full-match average positions only become
evidence after match completion. Prior q must come exclusively from earlier games.
Role templates retain the standing checkpoint's RAM/LAM half-space distinction.
"""
from math import isfinite

ROLES = ('GK','RB','RWB','RCB','CB','LCB','LB','LWB','RDM','DM','LDM',
         'RCM','CM','LCM','CAM','RAM','LAM','RW','LW','SS','ST')


def formation_layers(formation):
    try:
        values = [int(x) for x in str(formation).split('-')]
    except (ValueError, TypeError):
        return []
    return values if 2 <= len(values) <= 5 and sum(values) == 10 else []


def template(formation):
    """Standing-model structural patterns, with central AM named CAM."""
    layers = formation_layers(formation)
    patterns = []
    for i,n in enumerate(layers):
        if i == 0:
            roles = {2:['RCB','LCB'],3:['RCB','CB','LCB'],
                     4:['RB','RCB','LCB','LB'],5:['RWB','RCB','CB','LCB','LWB']}.get(n)
        elif i == len(layers)-1:
            roles = {1:['ST'],2:['ST','ST'],3:['RW','ST','LW'],
                     4:['RW','ST','ST','LW'],5:['RW','RAM','ST','LAM','LW']}.get(n)
        elif n == 1:
            roles = ['DM'] if i == 1 else ['CAM']
        elif n == 2:
            roles = (['RDM','LDM'] if i == 1 else ['RAM','LAM']) if len(layers)>3 else ['RCM','LCM']
        elif n == 3:
            roles = ['RAM','CAM','LAM'] if len(layers)>3 and i>1 else ['RCM','CM','LCM']
        elif n in (4,5):
            interior = ['RCM','LCM'] if n == 4 else ['RCM','CM','LCM']
            roles = (['RWB']+interior+['LWB']) if layers[0]==3 and i==1 else (['RW']+interior+['LW'])
        else:
            roles = None
        if roles is None:
            return []
        patterns.append(roles)
    return patterns


def canonical(role):
    return 'CAM' if role in ('AM','AMC') else role


def valid_coordinate(row):
    try:
        return all(isfinite(float(row[k])) and 0 <= float(row[k]) <= 100 for k in ('x','y'))
    except (TypeError, ValueError, KeyError):
        return False


def role_family(role):
    if role == 'GK': return 'GK'
    if role in ('RB','RWB','RCB','CB','LCB','LB','LWB'): return 'DEF'
    if role in ('RDM','DM','LDM','RCM','CM','LCM'): return 'MID'
    if role in ('CAM','RAM','LAM','RW','LW'): return 'AM'
    if role in ('SS','ST'): return 'FWD'
    return 'UNKNOWN'


def disagreement_type(a,b):
    """Unordered role-pair type, without diagnosing a side error as fact."""
    return ' ↔ '.join(sorted((canonical(a), canonical(b)))) if a and b else 'missing role'


def classify_lineup(formation, rows, geometry_roles, priors=None):
    """Return per-player structural, geometric and final roles with reasons.

    Structural capacities are preserved. A clear slot may only be permuted within
    its formation line when *every* changed member has a strong, pre-match prior
    supporting the alternative, coordinates are well separated, and x spread is
    modest. No cross-line override follows from average-x alone. Invalid structure
    uses prior q then geometry, with explicit low confidence; never random guesses.
    """
    priors = priors or {}
    patterns = template(formation)
    ordered = sorted(rows,key=lambda r:(int(r['slot']),str(r['player_uuid'])))
    flat = ['GK']+[r for line in patterns for r in line]
    coherent = bool(patterns) and len(ordered)==11 and sorted(int(r['slot']) for r in ordered)==list(range(1,12))
    coherent = coherent and str(ordered[0].get('position','')).upper()=='G'
    out = {}
    layer_for_slot = {1:-1}
    offset=2
    for layer,pattern in enumerate(patterns):
        for slot in range(offset,offset+len(pattern)): layer_for_slot[slot]=layer
        offset+=len(pattern)
    for row in ordered:
        pid=str(row['player_uuid']); slot=int(row['slot']); geom=canonical(geometry_roles.get(pid))
        prior=priors.get(pid,{}); q=prior.get('q',{})
        slot_role=flat[slot-1] if coherent else None
        chosen=slot_role; reason='formation_slot'; confidence='structural'
        if not coherent:
            if str(row.get('position','')).upper()=='G': chosen='GK'; reason='source_goalkeeper'
            elif q:
                chosen=max(sorted(q),key=lambda r:q[r]);reason='prior_q_fallback'
            else: chosen=geom;reason='geometry_fallback' if geom else 'unresolved'
            confidence='low'
        missing=not valid_coordinate(row)
        out[pid]={'slot_role':slot_role,'position_role':geom,'final_role':chosen,
                  'role_reason':reason,'role_confidence':confidence,
                  'average_position_missing':missing,
                  'average_position_uncertain':missing or (geom is not None and geom!=slot_role),
                  'disagreement':bool(slot_role and geom and slot_role!=geom),
                  'disagreement_type':disagreement_type(slot_role,geom) if slot_role!=geom else 'agreement',
                  'prior_q':q,'prior_evidence':float(prior.get('evidence',0)),
                  'formation_layer':layer_for_slot.get(slot),
                  'interpretation':'geometry_conflict_structure_preserved' if geom and geom!=slot_role else 'agreement'}
    if coherent:
        # Whole-line permutations only: retain role capacity and avoid assigning
        # two players to one slot merely because both have a similar mean position.
        for layer,pattern in enumerate(patterns):
            group=[r for r in ordered if layer_for_slot[int(r['slot'])]==layer]
            changed=[r for r in group if out[str(r['player_uuid'])]['disagreement']]
            geoms=[out[str(r['player_uuid'])]['position_role'] for r in group]
            if not changed or any(g is None for g in geoms) or sorted(geoms)!=sorted(pattern): continue
            if not all(valid_coordinate(r) for r in group): continue
            ys=sorted(float(r['y']) for r in group);xs=[float(r['x']) for r in group]
            if any(b-a<10 for a,b in zip(ys,ys[1:])) or max(xs)-min(xs)>20: continue
            supported=True
            for row in changed:
                z=out[str(row['player_uuid'])];q=z['prior_q']
                if z['prior_evidence']<3 or q.get(z['position_role'],0)<.65 or q.get(z['position_role'],0)-q.get(z['slot_role'],0)<.25:
                    supported=False;break
            if supported:
                for row in changed:
                    z=out[str(row['player_uuid'])]
                    z.update(final_role=z['position_role'],role_reason='within_line_geometry_prior_consensus',
                             role_confidence='supported_override',interpretation='prior_supported_slot_conflict')
    return out
