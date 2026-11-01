"""Opt-in repair of B's keeper-stint penalty-save reserve.

The sealed B simulator and approved NP policy remain unchanged. This adapter
reuses its event/scoring body and replaces only the regular-save mean. It is
not activated by production or previews.
"""
import ast
import inspect
from contextlib import contextmanager
import numpy as np
from . import b_event_simulator as B
from .b_event_simulator import takers

def regular_save_mean(inp, player, intervals, attempts, conversion):
    """Inclusive FPL save mean minus penalty saves during THIS keeper's stint.

    If the penalty-save expectation exceeds the inclusive target, zero regular
    saves is the feasible floor. Save-bucket tilts subsequently alter the mean.
    """
    start,end=intervals[player.player_id]
    fraction=(end-start)/90
    opponent=inp.away_team if player.team==inp.home_team else inp.home_team
    if fraction<=0:return 0.
    save_on_miss=float(np.clip(inp.p_penalty_save_given_miss,0,1))
    if attempts[opponent]<=0 or save_on_miss<=0:
        return max(0.,player.lambda_saves)*fraction
    if start==0 and end==90:
        # Preserve the established full-match calculation and random stream.
        reserve=attempts[opponent]*(1-conversion[opponent])*save_on_miss
        return max(0.,player.lambda_saves-reserve)*fraction
    opponents=[p for p in inp.players if p.team==opponent]
    edges=sorted({start,end,*[x for p in opponents for x in intervals[p.player_id] if start<x<end]})
    miss_mass=0.
    for a,b in zip(edges,edges[1:]):
        active=[p for p in opponents if intervals[p.player_id][0]<=a and intervals[p.player_id][1]>=b]
        candidates,weights=takers(inp,active)
        weight=np.maximum(0.,np.asarray(weights,float))
        if weight.sum()<=0:raise ValueError('Positive penalty intensity without an eligible taker')
        conv=np.clip([p.penalty_conversion for p in candidates],0,1)
        miss_mass+=(b-a)/90*float(weight@(1-conv)/weight.sum())
    reserve=attempts[opponent]*save_on_miss*miss_mass
    return max(0.,max(0.,player.lambda_saves)*fraction-reserve)


def _compile():
    tree=ast.parse(inspect.getsource(B.simulate_match))
    replaced=0
    class Reserve(ast.NodeTransformer):
        def visit_If(self,node):
            nonlocal replaced
            if ast.unparse(node.test)=='p.is_keeper':
                # Fail closed if upstream no longer has the audited expression.
                original=ast.unparse(ast.Module(body=node.body,type_ignores=[]))
                expected="save_reserve = attempts[opp] * (1 - conversion[opp]) * np.clip(inp.p_penalty_save_given_miss, 0, 1)"
                if not original.startswith(expected):
                    raise RuntimeError('B keeper reserve source changed; re-audit adapter')
                node.body=ast.parse('regular = regular_save_mean(inp,p,intervals,attempts,conversion)\nr.saves += legacy._sample_calibrated_saves(rng,regular,p.save_bucket_tilts)').body
                replaced+=1
                return node
            return self.generic_visit(node)
    tree=Reserve().visit(tree)
    if replaced!=1:raise RuntimeError('Expected exactly one B keeper reserve')
    ast.fix_missing_locations(tree)
    ns=dict(B.simulate_match.__globals__,regular_save_mean=regular_save_mean)
    exec(compile(tree,'<B-keeper-stint-save-reserve>','exec'),ns)
    return ns['simulate_match']


simulate_match=_compile()


@contextmanager
def keeper_save_reserve():
    """Explicit B research opt-in; restore the prior simulator on every exit."""
    previous=B.simulate_match
    B.simulate_match=simulate_match
    try:yield
    finally:B.simulate_match=previous
