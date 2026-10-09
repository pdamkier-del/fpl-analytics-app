"""Standalone Bench Boost value estimate. No changes to locked TS, TC, FH or WC.

Estimates the *incremental* points of activating BB now compared with ordinary
automatic substitutions, using independent Bernoulli appearance assumptions.
This is NOT a player availability forecast; probabilities come from locked PM.
"""
from dataclasses import dataclass
from itertools import product
from collections import Counter
from math import prod
import pandas as pd

from .optimize import START_MIN, START_MAX

# LOCKED by user after 2025/26 and conditional 2024/25 replay, 2026-10-09.
LOCKED_LAMBDA_BB = 20.0

@dataclass(frozen=True)
class BenchBoostEstimate:
    bench_xp: float
    expected_autosub_xp: float
    incremental_xp: float
    bench_player_ids: tuple[int, ...]

def evaluate_bench_boost(plan_rows: pd.DataFrame) -> BenchBoostEstimate:
    """Evaluate an already selected, legal 15-player locked TS lineup.

    xpts_mean is treated as unconditional expected player points.
    p_play is the chance of a nonzero-minutes appearance.
    Starter/bench appearances are independent in this baseline approximation.
    Bench points that would enter through ordinary autosubs are *not* BB uplift.
    """
    required={'id','role','position','p_play','xpts_mean'}
    if not required.issubset(plan_rows.columns):
        raise ValueError(f'Missing columns: {sorted(required-set(plan_rows.columns))}')
    if len(plan_rows)!=15 or plan_rows.id.nunique()!=15:
        raise ValueError('BB requires 15 different players')
    df=plan_rows.set_index('id').copy()
    start=plan_rows[plan_rows.role.isin(('C','VC','XI'))]
    if len(start)!=11: raise ValueError('BB requires 11 starters')
    benches=[]
    for role in ('Bench 1','Bench 2','Bench 3','GK bench'):
        row=plan_rows[plan_rows.role.eq(role)]
        if len(row)!=1: raise ValueError('BB requires exactly one '+role)
        benches.append(int(row.iloc[0].id))
    out_bench=benches[:3]; bench_gk=benches[3]
    starters=[int(pid) for pid in start.id]
    starter_gk=[pid for pid in starters if df.at[pid,'position']=='GKP']
    if len(starter_gk)!=1: raise ValueError('Invalid goalkeeper count')
    field_starters=[pid for pid in starters if pid!=starter_gk[0]]
    p={int(pid):min(1.,max(0.,float(row.p_play))) for pid,row in plan_rows.set_index('id').iterrows()}
    xp={int(pid):max(0.,float(row.xpts_mean)) for pid,row in plan_rows.set_index('id').iterrows()}
    bench_xp=sum(xp[pid] for pid in benches)
    autosub=xp[bench_gk]*(1.-p[starter_gk[0]])

    # Enumerate availability outcomes only to calculate bench contribution,
    # not to predict a new transfer strategy or alter the forecast.
    for starter_bits in product((False,True),repeat=10):
        pw=prod(p[pid] if available else (1.-p[pid])
                for pid,available in zip(field_starters,starter_bits))
        if pw==0: continue
        missing=[pid for pid,available in zip(field_starters,starter_bits) if not available]
        if not missing: continue
        for bench_bits in product((False,True),repeat=3):
            weight=pw*prod(p[pid] if available else (1.-p[pid])
                           for pid,available in zip(out_bench,bench_bits))
            if weight==0: continue
            active=set(pid for pid,available in zip(out_bench,bench_bits) if available)
            scoring=starters.copy()
            reward=0.
            for absent in missing:
                for pid in out_bench:
                    if pid not in active or pid in scoring: continue
                    candidate=[x for x in scoring if x!=absent]+[pid]
                    counts=Counter(str(df.at[x,'position']) for x in candidate)
                    if all(START_MIN[k]<=counts[k]<=START_MAX[k] for k in START_MIN):
                        scoring=candidate
                        reward+=xp[pid]/p[pid]
                        break
            autosub+=weight*reward
    return BenchBoostEstimate(
        bench_xp=float(bench_xp),
        expected_autosub_xp=float(autosub),
        incremental_xp=max(0.,float(bench_xp-autosub)),
        bench_player_ids=tuple(benches),
    )

def bb_threshold(gw: int, lambda_bb: float) -> float:
    """One-parameter chip holding threshold, matching frozen FH/WC decay."""
    if gw<1 or gw>38 or lambda_bb<0:raise ValueError('Invalid BB GW/threshold')
    first,last=(1,19) if gw<=19 else (20,38)
    return float(lambda_bb)*(last-gw)/(last-first)

def post_wildcard_bb_opportunities(
    *,
    wc_gw: int,
    wc_squad_ids: list[int],
    asof_projection: pd.DataFrame,
    lookahead: int = 6,
) -> pd.DataFrame:
    """Show BB opportunities AFTER WC without modifying the locked WC choice.

    Input must be the snapshot available at the WC deadline, never a later
    forecast. The first BB opportunity is GW+1 because chips cannot stack.
    Each future lineup uses the existing locked lineup optimizer; actual BB
    selection must be recomputed at the corresponding GW deadline after TS.
    """
    from .optimize import plan_squad
    if not 1 <= wc_gw <= 38:
        raise ValueError('Invalid wildcard GW')
    if len(wc_squad_ids) != 15 or len(set(wc_squad_ids)) != 15:
        raise ValueError('A full 15-player WC squad is required')
    if lookahead < 1:
        raise ValueError('lookahead must be positive')
    period_end = 19 if wc_gw <= 19 else 38
    horizons = [g for g in range(wc_gw + 1, min(period_end, wc_gw + lookahead) + 1)]
    rows = []
    for gw in horizons:
        if asof_projection[asof_projection.gw.eq(gw)].id.nunique() < 15:
            continue
        plan = plan_squad(asof_projection, wc_squad_ids, gw)
        opportunity = evaluate_bench_boost(plan.rows)
        rows.append({
            'wc_gw': wc_gw,
            'bb_gw': gw,
            'bench_xp': opportunity.bench_xp,
            'normal_autosub_xp': opportunity.expected_autosub_xp,
            'bb_incremental_xp': opportunity.incremental_xp,
            'bench_ids': opportunity.bench_player_ids,
        })
    return pd.DataFrame(rows)


def choose_bb_vs_locked_chips(gw: int, mask: int, fh_gain: float, wc_gain: float,
                              bb_gain: float, bb_available: bool, lambda_bb: float) -> str:
    """Compare BB with FROZEN FH/WC adjusted opportunities; one chip per GW.

    Reserved TC GW must be excluded by the caller. FH/WC mechanics are unchanged.
    """
    from .simple_chip_thresholds import choose_locked_fh_wc
    existing=choose_locked_fh_wc(gw,mask,fh_gain,wc_gain)
    bb_surplus=float(bb_gain)-bb_threshold(gw,lambda_bb)
    if bb_available and bb_surplus>max(existing.q_normal,existing.q_fh,existing.q_wc):
        return 'bb'
    return existing.choice


def locked_bb_threshold(gw: int) -> float:
    """Freeze BB exercise threshold; no tuning while assembling pipeline."""
    return bb_threshold(gw, LOCKED_LAMBDA_BB)
