"""B-only BB timing on the existing WC/transfer path; no MM/PM or TS refit."""
from copy import deepcopy
import math
import json
from fpl_xpts.transfer_planner import clone_state,_apply_selected_squad
from fpl_xpts.bench_boost_policy import locked_bb_threshold

SCHEMA='B-wildcard-BB-followup-v1'

def add_bench_boost(followup,state_wc,meta,projection,weights,*,reserved_chip_gws=()):
    # Import at call time: the existing B preview context provides joint PM
    # scoring and its autosub-correct BB estimator, not independent p(play).
    from fpl_xpts.optimize import plan_squad
    from fpl_xpts.bench_boost_policy import evaluate_bench_boost
    result=deepcopy(followup);state=clone_state(state_wc);candidates=[]
    if len(result['path'])!=len(weights):raise ValueError('BB horizon/weights mismatch')
    for action,weight in zip(result['path'],weights):
        gw=int(action['gw'])
        if gw<=result['gw']:raise ValueError('BB must follow WC, not share its deadline')
        if set(action['outgoing'])-set(state.squad):raise ValueError('WC path sells an unowned player')
        selected=(set(state.squad)-set(action['outgoing']))|set(action['incoming'])
        state,_,_=_apply_selected_squad(state,selected,meta)
        if state.bank!=action['bank_after']:raise ValueError('WC path bank mismatch')
        state.free_transfers=int(action['free_transfers_after'])
        lineup=plan_squad(projection,list(state.squad),gw)
        if abs(lineup.expected_score-action['projected_manager_score'])>1e-6:raise ValueError('BB baseline differs from WC path score')
        available=not any((used<=19)==(gw<=19)for used in state.chips_used['bench_boost'])
        reserved=gw in reserved_chip_gws;estimate=evaluate_bench_boost(lineup.rows);threshold=locked_bb_threshold(gw)
        gain=float(estimate.incremental_xp);surplus=gain-threshold
        if weight<=0 or not all(math.isfinite(v)for v in [weight,gain,threshold,estimate.bench_xp,estimate.expected_autosub_xp]):raise ValueError('Invalid BB estimate')
        candidates.append(dict(gw=gw,available=available,reserved_for_other_chip=reserved,bench_xp=float(estimate.bench_xp),normal_autosub_xp=float(estimate.expected_autosub_xp),incremental_xp=gain,threshold=threshold,net_value=surplus,weight=float(weight),weighted_net_value=float(weight)*surplus,bench_ids=list(map(int,estimate.bench_player_ids)),squad_ids=sorted(state.squad),lineup=json.loads(lineup.rows.to_json(orient='records')),decision='SAVE'))
    # One use per chip period, positive surplus required; ties prefer earlier
    # deadlines. These are conditional future choices, replanned each deadline.
    chosen=[]
    for half in [True,False]:
        eligible=[c for c in candidates if (c['gw']<=19)==half and c['available']and not c['reserved_for_other_chip']and c['net_value']>0]
        if eligible:
            best=max(eligible,key=lambda c:(c['weighted_net_value'],-c['gw']));best['decision']='USE_BB_PLANNED';chosen.append(best)
    by_gw={c['gw']:c for c in chosen}
    result['wc_without_bb_six_gw_xp_after_hits']=result['six_gw_xp_after_hits']
    result['wc_without_bb_weighted_objective']=result['weighted_objective_before_chip_timing_threshold']
    for action in result['path']:
        action['normal_projected_manager_score']=action['projected_manager_score'];choice=by_gw.get(action['gw']);gain=choice['incremental_xp']if choice else 0.
        action.update(chip='bench_boost'if choice else None,bench_boost_incremental_xp=gain,projected_manager_score=action['projected_manager_score']+gain)
        if 'utility_this_gw'in action:
            action['normal_utility_this_gw']=action['utility_this_gw'];action['utility_this_gw']+=gain
    result['six_gw_xp_after_hits']+=sum(c['incremental_xp']for c in chosen)
    result['weighted_objective_before_chip_timing_threshold']+=sum(c['weight']*c['incremental_xp']for c in chosen)
    result['bench_boost']=dict(schema=SCHEMA,status='planned'if chosen else('no_future_rounds'if not candidates else'unavailable'if not any(c['available']for c in candidates)else'save'),selected_gws=[c['gw']for c in chosen],candidates=candidates,selection_scope='Conditional on fixed WC squad and original transfer path; existing joint-PM BB value, locked BB threshold and TS weights. WC/transfer choices not reoptimized for BB; no complete FH/TC future calendar.',replan_at_each_deadline=True)
    return result
