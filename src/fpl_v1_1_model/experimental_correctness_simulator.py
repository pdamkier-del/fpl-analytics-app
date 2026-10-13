"""Opt-in correctness candidate. Locked simulator remains byte-for-byte unchanged.

Start marginals are projected to the feasible 1-goalkeeper/10-outfield XI polytope and
sampled with unbiased dependent rounding. Substitution slots separate goalkeepers from outfield players. FPL position
labels do not identify tactical slots; requested cameo minutes may be capped
by the vacant interval.
No role, availability or injury labels are invented.
"""
from contextlib import contextmanager
from functools import lru_cache, partial
from math import exp
from typing import Any
import numpy as np
from scipy.optimize import brentq
from . import joint_simulator as locked
from .joint_simulator import (MatchSimInput,PlayerSimResult,GOAL_POINTS,CS_POINTS,
    _sample_minutes,_weighted_choice,_sample_nb2,_sample_calibrated_saves)
from .bps import BPSComponents, bps_2024_25,bps_2025_26,bps_2026_27,allocate_bonus_points
from .defcon import dc_points_from_count
from .keeper import save_points
from .negative_events import sample_discipline,direct_negative_points

BOUNDS={"GK":(1,1),"DEF":(0,10),"MID":(0,10),"FWD":(0,10)}
def position(p):
    return "GK" if p.is_keeper or p.position in ("GK","GKP") else p.position

def shift_probabilities(raw,target):
    raw=np.asarray(raw,dtype=float);fixed=raw==1;free=(raw>0)&(raw<1)
    remaining=float(target)-fixed.sum()
    if remaining < -1e-9 or remaining > free.sum()+1e-9:
        raise ValueError("Infeasible hard start probabilities")
    result=fixed.astype(float)
    if not free.any():return result
    if remaining<=1e-10:return result
    if remaining>=free.sum()-1e-10:result[free]=1;return result
    odds=np.log(raw[free]/(1-raw[free]))
    def sigmoid(x):return 1/(1+np.exp(-np.clip(x,-700,700)))
    shift=brentq(lambda b:sigmoid(odds+b).sum()-remaining,-100,100,xtol=1e-12)
    result[free]=sigmoid(odds+shift)
    return result

@lru_cache(maxsize=2048)
def start_marginals(inp):
    if len({p.player_id for p in inp.players})!=len(inp.players):raise ValueError("Duplicate player IDs")
    if inp.home_team==inp.away_team:raise ValueError("Duplicate team")
    result={};diagnostics={}
    for team in (inp.home_team,inp.away_team):
        groups={pos:[p for p in inp.players if p.team==team and position(p)==pos] for pos in BOUNDS}
        if sum(map(len,groups.values()))!=sum(p.team==team for p in inp.players):raise ValueError("Unknown position")
        raw={pos:np.array([p.p_start if p.start_minutes_mean>0 else 0. for p in group]) for pos,group in groups.items()}
        if any(np.any(~np.isfinite(v)) or np.any((v<0)|(v>1)) for v in raw.values()):raise ValueError("Invalid start probability")
        lower={pos:max(BOUNDS[pos][0],int((v==1).sum())) for pos,v in raw.items()}
        upper={pos:min(BOUNDS[pos][1],int((v>0).sum())) for pos,v in raw.items()}
        if any(lower[pos]>upper[pos] for pos in BOUNDS) or sum(lower.values())>11 or sum(upper.values())<11:raise ValueError("No legal XI under hard caps")
        # Clubs can field a false nine: FPL positions do not justify FPL
        # manager formation constraints or forcing a lone striker to start.
        keepers=groups["GK"]
        outfield=[p for pos in ("DEF","MID","FWD") for p in groups[pos]]
        keeper_marginals=shift_probabilities(raw["GK"],1.)
        field_raw=np.array([p.p_start if p.start_minutes_mean>0 else 0. for p in outfield])
        field_marginals=shift_probabilities(field_raw,10.)
        for p,v in zip(keepers,keeper_marginals):result[p.player_id]=float(v)
        for p,v in zip(outfield,field_marginals):result[p.player_id]=float(v)
        target={pos:sum(result[p.player_id] for p in group) for pos,group in groups.items()}
        diagnostics[team]={"raw_start_sum":float(sum(v.sum() for v in raw.values())),"adjusted_start_sum":sum(result[p.player_id] for g in groups.values() for p in g),"max_abs_marginal_change":max(abs(result[p.player_id]-p.p_start) for g in groups.values() for p in g),"position_totals":target}
    if any(p.team not in (inp.home_team,inp.away_team) for p in inp.players):raise ValueError("Unknown team")
    return result,diagnostics

def round_pair(values,i,j,rng):
    a,b=values[i],values[j];up=min(1-a,b);down=min(a,1-b)
    if rng.random()<down/(up+down):values[i]+=up;values[j]-=up
    else:values[i]-=down;values[j]+=down
    for k in (i,j):
        if values[k]<1e-10:values[k]=0.
        if values[k]>1-1e-10:values[k]=1.

def sample_starters(inp,rng):
    marginal,_=start_marginals(inp);selected=set()
    for team in (inp.home_team,inp.away_team):
        players=[p for p in inp.players if p.team==team];values=np.array([marginal[p.player_id] for p in players])
        # Round within position first: each position count ends at floor/ceil of
        # its feasible expectation. Then preserve the exact combined count.
        for pos in BOUNDS:
            indexes=[i for i,p in enumerate(players) if position(p)==pos]
            while True:
                free=[i for i in indexes if 0<values[i]<1]
                if len(free)<2:break
                round_pair(values,free[0],free[1],rng)
        while True:
            free=np.flatnonzero((values>0)&(values<1))
            if len(free)<2:break
            round_pair(values,int(free[0]),int(free[1]),rng)
        chosen=[p for p,v in zip(players,values) if v>.5]
        if len(chosen)!=11 or any(not BOUNDS[pos][0]<=sum(position(p)==pos for p in chosen)<=BOUNDS[pos][1] for pos in BOUNDS):raise AssertionError("Dependent rounding produced illegal XI")
        selected.update(p.player_id for p in chosen)
    return selected

def sample_intervals(inp,rng,trace=None):
    selected=sample_starters(inp,rng);intervals={p.player_id:(90,90) for p in inp.players};slots={}
    for p in inp.players:
        if p.player_id in selected:
            m=int(np.clip(round(rng.normal(p.start_minutes_mean,10.)),1,90))
            intervals[p.player_id]=(0,m);slots[p.player_id]=(p.team,position(p),m)
    capped=0;rejected=0;windows_adjusted=0;assignments={pid:pid for pid in selected}
    for team in (inp.home_team,inp.away_team):
        used=set();substitutions=0
        bench=[p for p in inp.players if p.team==team and p.player_id not in selected]
        for i in rng.permutation(len(bench)):
            p=bench[int(i)]
            if p.cameo_minutes_mean<=0 or rng.random()>=p.p_cameo_given_bench:continue
            requested=int(np.clip(round(rng.normal(p.cameo_minutes_mean,7.)),1,45))
            available=[pid for pid,(t,pos,m) in slots.items() if t==team and (pos=="GK")== (position(p)=="GK") and m<90 and pid not in used]
            if not available or substitutions>=5:rejected+=1;continue
            adequate=[pid for pid in available if 90-slots[pid][2]>=requested]
            if adequate:available=adequate
            else:
                largest=max(90-slots[pid][2] for pid in available)
                available=[pid for pid in available if 90-slots[pid][2]==largest]
            slot=available[int(rng.integers(len(available)))];room=90-slots[slot][2]
            actual=min(requested,room);capped+=int(actual<requested)
            intervals[p.player_id]=(90-actual,90);used.add(slot);substitutions+=1;assignments[p.player_id]=slot
        # Normal PL substitutes use at most three in-play windows; half-time
        # is exempt. Merge closest windows later, never into an occupied slot.
        groups={}
        for p in bench:
            a,b=intervals[p.player_id]
            if b>a and a!=45:groups.setdefault(a,[]).append(p.player_id)
        while len(groups)>3:
            times=sorted(groups)
            a,b=min(zip(times,times[1:]),key=lambda pair:pair[1]-pair[0])
            for pid in groups[a]:intervals[pid]=(b,90);windows_adjusted+=1
            groups[b].extend(groups.pop(a))
    if trace is not None:trace.update(starters=selected,slot_assignments=assignments,cameo_windows_adjusted=windows_adjusted,cameos_capped=capped,cameos_rejected=rejected,start_marginals=start_marginals(inp)[0],marginal_diagnostics=start_marginals(inp)[1])
    return intervals,selected

def expected_penalty_goals(inp,intervals,team,rate):
    edges=sorted({0,90,*[x for p in inp.players if p.team==team for x in intervals[p.player_id]]});mean=0.
    for a,b in zip(edges,edges[1:]):
        active=[p for p in inp.players if p.team==team and intervals[p.player_id][0]<=a and intervals[p.player_id][1]>=b and b>a]
        weights=[max(0.,p.penalty_weight) for p in active]
        if sum(weights)<=0:weights=[max(0.,p.goal_weight) for p in active]
        if sum(weights)>0:mean+=(b-a)/90*sum(w*min(1.,max(0.,p.penalty_conversion)) for p,w in zip(active,weights))/sum(weights)
    return rate*mean

def simulate_match(inp:MatchSimInput,rng:Any,*,own_goals=True,joint_xi=True,trace=None)->dict[str,PlayerSimResult]:
    if len({p.player_id for p in inp.players})!=len(inp.players):raise ValueError("Duplicate player IDs")
    for p in inp.players:
        probabilities=[p.p_start,p.p_cameo_given_bench,p.p_own_goal]
        if not all(np.isfinite(v) and 0<=v<=1 for v in probabilities):raise ValueError("Invalid player probability")
        if p.team not in (inp.home_team,inp.away_team):raise ValueError("Unknown team")
    if not all(np.isfinite(v) and v>=0 for v in [inp.lambda_home_goals,inp.lambda_away_goals,inp.lambda_home_penalties,inp.lambda_away_penalties]):raise ValueError("Invalid goal intensity")
    if inp.lambda_home_goals<0 or inp.lambda_away_goals<0: raise ValueError("goal means must be non-negative")
    ps=list(inp.players); out={p.player_id:PlayerSimResult() for p in ps}; intervals={}
    if joint_xi:
        intervals, starters = sample_intervals(inp, rng, trace)
        for p in ps:
            a,b=intervals[p.player_id]
            out[p.player_id].minutes=b-a
            out[p.player_id].started=int(p.player_id in starters)
    else:
        for p in ps:
            m,a,b=_sample_minutes(rng,p); out[p.player_id].minutes=m; out[p.player_id].started=int(m>0 and a==0); intervals[p.player_id]=(a,b)

    # Shared penalty process. Expected scored-penalty mass is removed from the
    # ordinary team-goal Poisson before explicit penalties are simulated, so
    # penalties do not inflate the existing team goal mean.
    hp=max(0.0,float(inp.lambda_home_penalties)); ap=max(0.0,float(inp.lambda_away_penalties))
    hc=min(1.0,max(0.0,float(inp.home_penalty_conversion))); ac=min(1.0,max(0.0,float(inp.away_penalty_conversion)))
    own_events=[]
    own_mass={inp.home_team:0.,inp.away_team:0.}
    if own_goals:
        for p in ps:
            a,b=intervals[p.player_id]
            if b<=a: continue
            probability=float(p.p_own_goal)
            if not 0<=probability<=1: raise ValueError("Invalid own-goal probability")
            opponent=inp.away_team if p.team==inp.home_team else inp.home_team
            own_mass[opponent]+=probability
            if rng.random()<probability:
                out[p.player_id].own_goal=1
                own_events.append((float(rng.uniform(a,b)),opponent,p.player_id))
        hpen=expected_penalty_goals(inp,intervals,inp.home_team,hp)
        apen=expected_penalty_goals(inp,intervals,inp.away_team,ap)
        h_open=float(inp.lambda_home_goals)-hpen-own_mass[inp.home_team]
        a_open=float(inp.lambda_away_goals)-apen-own_mass[inp.away_team]
        if min(h_open,a_open)<-1e-12:
            raise ValueError("Explicit goal components exceed total goal intensity")
        h_open=max(0.,h_open);a_open=max(0.,a_open)
    else:
        h_open=max(0.0,float(inp.lambda_home_goals)-hp*hc)
        a_open=max(0.0,float(inp.lambda_away_goals)-ap*ac)
    hg=int(rng.poisson(h_open)); ag=int(rng.poisson(a_open))
    goal_events=[]
    for team,n in ((inp.home_team,hg),(inp.away_team,ag)):
        for _ in range(n): goal_events.append((float(rng.uniform(0,90)),team,None,False))

    penalty_events=[]
    for team,lam in ((inp.home_team,hp),(inp.away_team,ap)):
        for _ in range(int(rng.poisson(lam))):
            penalty_events.append((float(rng.uniform(0,90)),team))
    penalty_events.sort()
    for t,team in penalty_events:
        active=[p for p in ps if p.team==team and intervals[p.player_id][0] <= t < intervals[p.player_id][1] and out[p.player_id].minutes>0]
        taker=_weighted_choice(rng,active,[p.penalty_weight for p in active])
        if taker is None:
            taker=_weighted_choice(rng,active,[p.goal_weight for p in active])
        if taker is None:
            continue
        conv=min(1.0,max(0.0,float(taker.penalty_conversion)))
        if rng.random()<conv:
            goal_events.append((t,team,taker.player_id,True))
        else:
            out[taker.player_id].penalty_miss+=1
            opp=inp.away_team if team==inp.home_team else inp.home_team
            keepers=[p for p in ps if p.team==opp and p.is_keeper and intervals[p.player_id][0] <= t < intervals[p.player_id][1] and out[p.player_id].minutes>0]
            if keepers and rng.random()<min(1.0,max(0.0,float(inp.p_penalty_save_given_miss))):
                k=keepers[0]
                out[k.player_id].penalty_saves+=1
                out[k.player_id].saves+=1
    goal_events.sort(key=lambda x:x[0])

    # Allocate ordinary scorers/assists; explicit scored penalties already have
    # their taker and intentionally receive no assist in this layer.
    for t,team,predetermined,is_pen in goal_events:
        active=[p for p in ps if p.team==team and intervals[p.player_id][0] <= t < intervals[p.player_id][1] and out[p.player_id].minutes>0]
        scorer=next((p for p in active if p.player_id==predetermined),None) if predetermined else _weighted_choice(rng,active,[p.goal_weight for p in active])
        if scorer:
            out[scorer.player_id].goals+=1
            if is_pen: out[scorer.player_id].penalty_goals+=1
        if (not is_pen) and rng.random()<inp.assist_probability_per_goal:
            cand=[p for p in active if scorer is None or p.player_id!=scorer.player_id]
            assister=_weighted_choice(rng,cand,[p.assist_weight for p in cand])
            if assister: out[assister.player_id].assists+=1

    # Own goals share the scoreline, but receive no ordinary scorer/assist.
    goal_events.extend((t,team,None,False) for t,team,committer in own_events)
    if trace is not None:
        trace.update(intervals=intervals, own_goal_events=own_events,
                     goal_events=goal_events, own_goal_expected_mass=own_mass,
                     ordinary_intensity={inp.home_team:h_open,inp.away_team:a_open})

    # Goals conceded while each player is actually on pitch.
    for p in ps:
        a,b=intervals[p.player_id]
        if out[p.player_id].minutes<=0: continue
        opp=inp.away_team if p.team==inp.home_team else inp.home_team
        gc=sum(1 for t,scoring_team,_,_ in goal_events if scoring_team==opp and a<=t<b)
        out[p.player_id].goals_conceded_while_on_pitch=gc
        out[p.player_id].clean_sheet=int(out[p.player_id].minutes>=60 and gc==0)

    # Independent conditional layers selected in prior phases.
    for p in ps:
        r=out[p.player_id]; m=r.minutes
        if m<=0: continue
        if p.is_keeper:
            opp_pen=ap if p.team==inp.home_team else hp
            opp_conv=ac if p.team==inp.home_team else hc
            exp_pen_save=opp_pen*(1-opp_conv)*min(1.0,max(0.0,float(inp.p_penalty_save_given_miss)))
            regular=max(0.0,p.lambda_saves-exp_pen_save)*m/90.0
            r.saves += _sample_calibrated_saves(rng,regular,p.save_bucket_tilts)
        r.dc_count=_sample_nb2(rng,max(0.0,p.dc_mu_90)*m/90.0,p.dc_alpha)
        r.dc_points=0 if inp.bps_rules=="2024-25" else dc_points_from_count(p.position,r.dc_count)
        card=sample_discipline(rng,p.discipline)
        r.yellow=int(card=="yellow"); r.red=int(card=="red")
        if not own_goals: r.own_goal=int(rng.random()<min(1,max(0,p.p_own_goal)))

    # Score non-bonus FPL points and known BPS event components.
    bps={}
    for p in ps:
        r=out[p.player_id]; m=r.minutes
        if m<=0: bps[p.player_id]=-10_000; continue
        pts=2 if m>=60 else 1
        pts += GOAL_POINTS[p.position]*r.goals + 3*r.assists
        pts += CS_POINTS[p.position]*r.clean_sheet
        if p.is_keeper: pts += save_points(r.saves) + 5*r.penalty_saves
        if p.position in ("GK","GKP","DEF"): pts -= r.goals_conceded_while_on_pitch//2
        pts += r.dc_points
        pts += direct_negative_points(yellow=r.yellow,red=r.red,own_goal=r.own_goal,penalty_miss=r.penalty_miss)
        r.points=pts
        comp=BPSComponents(minutes=m,position=p.position,
            non_penalty_goals=max(0,r.goals-r.penalty_goals),penalty_goals=r.penalty_goals,assists=r.assists,
            clean_sheet=r.clean_sheet,penalty_saves=r.penalty_saves,saves_total=r.saves,
            saves_inside_box=r.penalty_saves,goals_conceded=r.goals_conceded_while_on_pitch,
            penalty_misses=r.penalty_miss,yellow_cards=r.yellow,red_cards=r.red,own_goals=r.own_goal)
        if inp.bps_rules=="2024-25":
            known=bps_2024_25(comp)
        elif inp.bps_rules=="2025-26":
            known=bps_2025_26(comp)
        elif inp.bps_rules=="2026-27":
            known=bps_2026_27(comp)
        else:
            raise ValueError("unknown BPS rules season")
        if p.bps_background_rate90 is not None:
            frac=max(0.0,min(1.0,m/90.0))
            mean_bg=float(p.bps_background_rate90)*frac
            sd90=float(p.bps_background_sd90 or 0.0)
            bg=float(rng.normal(mean_bg,sd90*np.sqrt(frac))) if sd90>0 else mean_bg
        else:
            bg=float(rng.normal(p.bps_background_mean,p.bps_background_sd)) if p.bps_background_sd>0 else p.bps_background_mean
        r.bps=int(round(known+bg)); bps[p.player_id]=r.bps
    bonus=allocate_bonus_points(bps)
    for pid,b in bonus.items():
        if out[pid].minutes>0: out[pid].bonus=b; out[pid].points+=b
    return out

@contextmanager
def shadow_simulator(*,own_goals=True,joint_xi=True):
    """Serial offline experiment only; never install in production service."""
    original=locked.simulate_match
    locked.simulate_match=partial(simulate_match,own_goals=own_goals,joint_xi=joint_xi)
    try:yield
    finally:locked.simulate_match=original
