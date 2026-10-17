"""Preview-only bridge to the unchanged vFinal simulator and six-GW TS.

The PM adapter derives on-pitch propensities from its frozen control exposure.
Keep that exposure and every non-minute input intact; replace only the four
candidate minute fields. Changing control exposure alone would silently change
goal/assist/DefCon rates. No rescaling of simulated xP is used here.
"""
import hashlib
import json
from dataclasses import asdict
import numpy as np
import pandas as pd
from mm_candidate import validate_frame

KEY = ['fixture_uuid', 'player_uuid']
MINUTE_FIELDS = dict(p='v4_workload_start_p_start',
                     q='v4_p_cameo_given_bench', s='v4_start_minutes_mean',
                     c='v4_cameo_minutes_mean', x='v4_workload_start_xmins')


def locked_sampler_expectation(p,q,s,c):
    """Exact mean of the unchanged rounded/clipped Gaussian duration sampler.

    Diagnostic only: do not invert/reparameterize B or silently fix the PM.
    For clipped integer K in [1,U], E[K]=1+sum(k=2..U) P(Z>=k-.5).
    Continuous Gaussian draws have zero probability of rounding ties.
    """
    from scipy.special import ndtr
    p,q,s,c=np.broadcast_arrays(p,q,s,c)
    start=1+ndtr((s[...,None]-(np.arange(2,91)-.5))/10.).sum(axis=-1)
    cameo=1+ndtr((c[...,None]-(np.arange(2,46)-.5))/7.).sum(axis=-1)
    return p*start+(1-p)*q*cameo


def attach_mm(pm, mm):
    """Exact identity/cutoff join; never fill missing players from another MM."""
    mm = validate_frame(mm)
    if pm.empty or pm.duplicated(KEY).any() or mm.duplicated(KEY).any():
        raise ValueError('Missing/duplicate PM or MM identity')
    required = set(KEY + ['team_id', 'pos', 'gw', 'cutoff', *MINUTE_FIELDS.values()])
    if required - set(pm):
        raise ValueError('Incomplete PM input')
    joined = pm[KEY + ['team_id', 'pos', 'gw', 'cutoff']].merge(
        mm[KEY + ['team_id', 'pos', 'gw', 'cutoff', 'p', 'q', 's', 'c', 'x']],
        on=KEY, how='outer', validate='one_to_one', suffixes=('_pm', ''), indicator=True)
    if not joined._merge.eq('both').all():
        raise ValueError('MM/PM roster coverage mismatch')
    for c in ['team_id', 'gw']:
        if not joined[c].eq(joined[c+'_pm']).all():
            raise ValueError('MM/PM identity mismatch: '+c)
    if not joined.pos.replace('GKP', 'GK').eq(joined.pos_pm.replace('GKP', 'GK')).all():
        raise ValueError('MM/PM position mismatch')
    if not pd.to_datetime(joined.cutoff, utc=True).eq(pd.to_datetime(joined.cutoff_pm, utc=True)).all():
        raise ValueError('MM/PM cutoff mismatch')
    # Historical seasons are independently checked when available on PM input.
    if 'season' in pm:
        s=pm[KEY+['season']].merge(mm[KEY+['season']],on=KEY,validate='one_to_one')
        if not s.season_x.eq(s.season_y).all():raise ValueError('MM/PM season mismatch')
    values=joined.set_index(KEY).reindex(pd.MultiIndex.from_frame(pm[KEY]))
    out=pm.copy()
    for c,dest in MINUTE_FIELDS.items():out[dest]=values[c].to_numpy()
    pd.testing.assert_frame_equal(pm.drop(columns=list(MINUTE_FIELDS.values())),
                                  out.drop(columns=list(MINUTE_FIELDS.values())),check_exact=True)
    return out


def simulate_pair(pm, mm, *, season, seed=93000000, draws=400):
    """Paired seed/budget, not event-aligned Monte Carlo; no PM modifications."""
    from run_vfinal_integrated import make_vfinal_input
    from fpl_v1_1_model.joint_simulator import simulate_many
    from run_live_vfinal_joint_simulation import POINT_COMPONENTS
    from dataclasses import replace
    if draws != 400:raise ValueError('Locked simulation budget is 400')
    if season not in ('2025-26','2026-27'):raise ValueError('Unknown scoring season')
    candidate=attach_mm(pm, mm)
    result=[]
    for i,(fixture,base) in enumerate(pm.groupby('fixture_uuid',sort=True)):
        changed=candidate[candidate.fixture_uuid.eq(fixture)]
        frozen_nonminute=None
        for arm,frame in [('production_minutes',base),('B_minutes',changed)]:
            inp,_=make_vfinal_input(frame)
            inp=replace(inp,bps_rules=season)
            nonminute=asdict(inp)
            for player in nonminute['players']:
                for field in ['p_start','p_cameo_given_bench','start_minutes_mean','cameo_minutes_mean']:
                    del player[field]
            if frozen_nonminute is None:frozen_nonminute=nonminute
            elif nonminute!=frozen_nonminute:raise ValueError('Bridge changed PM rates or non-minute simulator inputs')
            expected=frame.set_index('player_uuid')
            # Inspect the final simulator object, not just renamed table fields.
            for p in inp.players:
                r=expected.loc[p.player_id]
                for attr,col in [('p_start','v4_workload_start_p_start'),
                    ('p_cameo_given_bench','v4_p_cameo_given_bench'),
                    ('start_minutes_mean','v4_start_minutes_mean'),
                    ('cameo_minutes_mean','v4_cameo_minutes_mean')]:
                    if abs(getattr(p,attr)-r[col])>1e-12:raise ValueError('PM lost MM field '+attr)
            sim=simulate_many(inp,n=draws,seed=seed+i)
            if set(sim)!=set(expected.index):raise ValueError('PM missed player')
            for pid,s in sorted(sim.items()):
                if abs(sum(s[c] for c in POINT_COMPONENTS)-s['xPts'])>1e-8:
                    raise ValueError('Point components do not reconcile')
                r=expected.loc[pid]
                if r.v4_workload_start_p_start==0 and r.v4_p_cameo_given_bench==0:
                    if s['expected_minutes']!=0 or s['xPts']!=0:raise ValueError('Unavailable PM output')
                result.append(dict(fixture_uuid=fixture,player_uuid=pid,gw=int(r.gw),
                    arm=arm,xpts=float(s['xPts']),simulated_minutes=float(s['expected_minutes']),
                    xmins=float(r.v4_workload_start_xmins),p_start=float(r.v4_workload_start_p_start),
                    sampler_expected_minutes=float(locked_sampler_expectation(r.v4_workload_start_p_start,r.v4_p_cameo_given_bench,r.v4_start_minutes_mean,r.v4_cameo_minutes_mean)),
                    **{c:float(s[c]) for c in POINT_COMPONENTS}))
    return pd.DataFrame(result)


def run_current_ts(payload, manager, *, now=None, include_chips=True):
    """Use the existing private TS entry point; historical outputs are rejected."""
    from run_live_locked_ts import run
    from fpl_v1_1_model.forecast_snapshot import require_snapshot
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if payload.get('scope')!='prospective_preview':raise ValueError('Current TS requires prospective B forecast')
    require_snapshot(payload)
    if not payload.get('origin_deadline') or pd.Timestamp(payload['origin_deadline'])<=now:
        raise ValueError('Current TS deadline expired')
    if not payload.get('freshness_limit_hours'):raise ValueError('Missing forecast freshness policy')
    if len(payload.get('gws',[]))!=min(6,39-min(payload.get('gws',[39]))):
        raise ValueError('Incomplete six-GW forecast')
    return run(payload,manager,include_chips=include_chips)


def code_identity(root):
    paths=['src/fpl_v1_1_model/joint_simulator.py','src/fpl_v1_1_model/phase4b.py',
           'src/fpl_v1_1_model/paired_joint.py','scripts/run_vfinal_integrated.py',
           'src/fpl_xpts/transfer_planner.py','scripts/run_live_locked_ts.py',
           'scripts/run_joint_fh_wc_stopping_replay.py']
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}


def sample_candidate_minutes(rng, *, p, q, s, c):
    """RESEARCH ONLY: draw PR13/B exact-mean conditional minutes.

    Preserves separate start/cameo events, the original (minutes, entrance,
    departure) tuple contract, and the B expectation. Unlike the locked PM
    Gaussian clip, cameo minutes may exceed 45. This is NOT a production
    sampler, has NOT passed calibration/prospective gates, and must never
    silently replace joint_simulator._sample_minutes.
    """
    from mm_candidate import minute_masses
    for name, v, upper in [('p', p, 1), ('q', q, 1),
                            ('s', s, 90), ('c', c, 90)]:
        if not np.isfinite(v) or v < 0 or v > upper:
            raise ValueError('Invalid B minute input: ' + name)
    if q > 0 and c < 1:
        raise ValueError('Positive cameo probability requires positive minutes')
    if p > 0 and s < 0:
        raise ValueError('Invalid starter duration')
    if rng.random() < p:
        arm, mu = 'start', s
    elif rng.random() < q:
        arm, mu = 'cameo', c
    else:
        return 0, 90, 90
    # Each conditional distribution is generated with PR13's fixed sigma
    # and the original endpoint repair, not a second/fitted probability model.
    f = pd.DataFrame([dict(p=1. if arm == 'start' else 0.,
                           q=1. if arm == 'cameo' else 0.,
                           s=mu if arm == 'start' else 0.,
                           c=mu if arm == 'cameo' else 1.,
                           x=mu)])
    probs = minute_masses(f)[0]
    m = int(rng.choice(np.arange(91), p=probs))
    return (m, 0, m) if arm == 'start' else (m, 90-m, 90)
