"""Joint match-level Monte Carlo primitives for FPL v1.1.

Phase 4A deliberately joins the already-selected component models without
retuning their half-lives. Penalties remain folded into attack rates until a
complete npxG/penalty source is approved. BPS background is explicit rather
than silently invented from unavailable Opta components.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp
from typing import Any, Iterable
import numpy as np

from .bps import BPSComponents, bps_2026_27, allocate_bonus_points
from .defcon import dc_points_from_count
from .keeper import save_points
from .negative_events import DisciplineProbabilities, sample_discipline, direct_negative_points

GOAL_POINTS={"GK":10,"GKP":10,"DEF":6,"MID":5,"FWD":4}
CS_POINTS={"GK":4,"GKP":4,"DEF":4,"MID":1,"FWD":0}

@dataclass(frozen=True)
class PlayerSimInput:
    player_id: str
    team: str
    position: str
    p_start: float
    p_cameo_given_bench: float
    start_minutes_mean: float
    cameo_minutes_mean: float
    goal_weight: float=0.0
    assist_weight: float=0.0
    dc_mu_90: float=0.0
    dc_alpha: float=0.0
    discipline: DisciplineProbabilities=DisciplineProbabilities(1.0,0.0,0.0)
    p_own_goal: float=0.0
    bps_background_mean: float=0.0
    bps_background_sd: float=0.0
    is_keeper: bool=False
    lambda_saves: float=0.0
    save_bucket_tilts: tuple[float,float,float,float,float]|None=None
    penalty_weight: float=0.0
    penalty_conversion: float=0.78

@dataclass(frozen=True)
class MatchSimInput:
    home_team: str
    away_team: str
    lambda_home_goals: float
    lambda_away_goals: float
    players: tuple[PlayerSimInput,...]
    assist_probability_per_goal: float=0.72
    lambda_home_penalties: float=0.0
    lambda_away_penalties: float=0.0
    home_penalty_conversion: float=0.78
    away_penalty_conversion: float=0.78
    p_penalty_save_given_miss: float=0.0

@dataclass
class PlayerSimResult:
    points: int=0; minutes: int=0; started: int=0; goals: int=0; assists: int=0
    clean_sheet: int=0; saves: int=0; dc_count: int=0; dc_points: int=0
    yellow: int=0; red: int=0; own_goal: int=0; penalty_miss: int=0; penalty_saves: int=0; bonus: int=0; bps: int=0
    goals_conceded_while_on_pitch: int=0

def _sample_minutes(rng: Any,p: PlayerSimInput)->tuple[int,int,int]:
    if rng.random() < p.p_start:
        m=int(np.clip(round(rng.normal(p.start_minutes_mean,10.0)),1,90)); return m,0,m
    if rng.random() < p.p_cameo_given_bench:
        m=int(np.clip(round(rng.normal(p.cameo_minutes_mean,7.0)),1,45)); return m,90-m,90
    return 0,90,90

def _weighted_choice(rng:Any, players:list[PlayerSimInput], weights:list[float])->PlayerSimInput|None:
    s=float(sum(max(0.0,x) for x in weights))
    if not players or s<=0:return None
    q=np.asarray([max(0.0,x)/s for x in weights],dtype=float)
    return players[int(rng.choice(len(players),p=q))]

def _sample_nb2(rng:Any,mu:float,alpha:float)->int:
    if mu<=0:return 0
    if alpha<=1e-12:return int(rng.poisson(mu))
    shape=1.0/alpha; scale=mu*alpha
    return int(rng.poisson(rng.gamma(shape,scale)))

def _sample_calibrated_saves(rng:Any,lam:float,tilts:tuple[float,float,float,float,float]|None)->int:
    lam=max(0.0,float(lam))
    if tilts is None or lam<=0:
        return int(rng.poisson(lam))
    if len(tilts)!=5:
        raise ValueError("save_bucket_tilts must have five entries")
    # Reweight the Poisson count distribution by FPL save-point buckets
    # (0-2, 3-5, 6-8, 9-11, 12+ saves). Conditional shape within each
    # bucket remains the original Poisson shape.
    probs=[];p=exp(-lam);probs.append(p)
    for n in range(1,61):
        p*=lam/n;probs.append(p)
    arr=np.asarray(probs,dtype=float)
    idx=np.minimum(np.arange(len(arr))//3,4)
    arr*=np.exp(np.asarray(tilts,dtype=float)[idx])
    s=float(arr.sum())
    if s<=0 or not np.isfinite(s):
        return int(rng.poisson(lam))
    arr/=s
    return int(rng.choice(len(arr),p=arr))

def simulate_match(inp:MatchSimInput,rng:Any)->dict[str,PlayerSimResult]:
    if inp.lambda_home_goals<0 or inp.lambda_away_goals<0: raise ValueError("goal means must be non-negative")
    ps=list(inp.players); out={p.player_id:PlayerSimResult() for p in ps}; intervals={}
    for p in ps:
        m,a,b=_sample_minutes(rng,p); out[p.player_id].minutes=m; out[p.player_id].started=int(m>0 and a==0); intervals[p.player_id]=(a,b)

    # Shared penalty process. Expected scored-penalty mass is removed from the
    # ordinary team-goal Poisson before explicit penalties are simulated, so
    # penalties do not inflate the existing team goal mean.
    hp=max(0.0,float(inp.lambda_home_penalties)); ap=max(0.0,float(inp.lambda_away_penalties))
    hc=min(1.0,max(0.0,float(inp.home_penalty_conversion))); ac=min(1.0,max(0.0,float(inp.away_penalty_conversion)))
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
        if scorer: out[scorer.player_id].goals+=1
        if (not is_pen) and rng.random()<inp.assist_probability_per_goal:
            cand=[p for p in active if scorer is None or p.player_id!=scorer.player_id]
            assister=_weighted_choice(rng,cand,[p.assist_weight for p in cand])
            if assister: out[assister.player_id].assists+=1

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
        r.dc_points=dc_points_from_count(p.position,r.dc_count)
        card=sample_discipline(rng,p.discipline)
        r.yellow=int(card=="yellow"); r.red=int(card=="red")
        r.own_goal=int(rng.random()<min(1,max(0,p.p_own_goal)))

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
        known=bps_2026_27(BPSComponents(minutes=m,position=p.position,non_penalty_goals=r.goals,assists=r.assists,
            clean_sheet=r.clean_sheet,saves_total=r.saves,goals_conceded=r.goals_conceded_while_on_pitch,
            yellow_cards=r.yellow,red_cards=r.red,own_goals=r.own_goal))
        bg=float(rng.normal(p.bps_background_mean,p.bps_background_sd)) if p.bps_background_sd>0 else p.bps_background_mean
        r.bps=int(round(known+bg)); bps[p.player_id]=r.bps
    bonus=allocate_bonus_points(bps)
    for pid,b in bonus.items():
        if out[pid].minutes>0: out[pid].bonus=b; out[pid].points+=b
    return out

def simulate_many(inp:MatchSimInput,n:int=20_000,seed:int=26092026)->dict[str,dict[str,float]]:
    if n<=0: raise ValueError("n must be positive")
    rng=np.random.default_rng(seed); samples={p.player_id:[] for p in inp.players}; nonbonus={p.player_id:[] for p in inp.players}; bonuses={p.player_id:[] for p in inp.players}; mins={p.player_id:[] for p in inp.players}
    aux={p.player_id:{"start":0,"return":0,"ten":0,"cs":0,"appearance_pts":0.0,"goal_pts":0.0,"assist_pts":0.0,"cs_pts":0.0,"save_pts":0.0,"dc_pts":0.0,"negative_pts":0.0,"gc_pts":0.0,"penalty_miss_pts":0.0,"penalty_save_pts":0.0} for p in inp.players}
    for _ in range(n):
        res=simulate_match(inp,rng)
        for p in inp.players:
            r=res[p.player_id]; samples[p.player_id].append(r.points); nonbonus[p.player_id].append(r.points-r.bonus); bonuses[p.player_id].append(r.bonus); mins[p.player_id].append(r.minutes); aux[p.player_id]["start"]+=r.started
            aux[p.player_id]["return"]+=int(r.goals+r.assists>0); aux[p.player_id]["ten"]+=int(r.points>=10); aux[p.player_id]["cs"]+=r.clean_sheet
            if r.minutes>0:
                aux[p.player_id]["appearance_pts"] += 2 if r.minutes>=60 else 1
                aux[p.player_id]["goal_pts"] += GOAL_POINTS[p.position]*r.goals
                aux[p.player_id]["assist_pts"] += 3*r.assists
                aux[p.player_id]["cs_pts"] += CS_POINTS[p.position]*r.clean_sheet
                aux[p.player_id]["save_pts"] += save_points(r.saves) if p.is_keeper else 0\n                aux[p.player_id]["penalty_save_pts"] += 5*r.penalty_saves if p.is_keeper else 0\n                aux[p.player_id]["penalty_miss_pts"] += -2*r.penalty_miss
                aux[p.player_id]["dc_pts"] += r.dc_points
                aux[p.player_id]["negative_pts"] += direct_negative_points(yellow=r.yellow,red=r.red,own_goal=r.own_goal,penalty_miss=r.penalty_miss)
                aux[p.player_id]["gc_pts"] += -(r.goals_conceded_while_on_pitch//2) if p.position in ("GK","GKP","DEF") else 0
    ans={}
    for p in inp.players:
        a=np.asarray(samples[p.player_id],dtype=float)
        ans[p.player_id]={"xPts":float(a.mean()),"xPts_nonbonus":float(np.mean(nonbonus[p.player_id])),"expected_bonus":float(np.mean(bonuses[p.player_id])),"median":float(np.median(a)),"p10":float(np.quantile(a,.10)),"p90":float(np.quantile(a,.90)),
            "expected_minutes":float(np.mean(mins[p.player_id])),"p_start":aux[p.player_id]["start"]/n,"p_attacking_return":aux[p.player_id]["return"]/n,"p_10_plus":aux[p.player_id]["ten"]/n,"p_clean_sheet_award":aux[p.player_id]["cs"]/n,
            "appearance_points":aux[p.player_id]["appearance_pts"]/n,"goal_points":aux[p.player_id]["goal_pts"]/n,"assist_points":aux[p.player_id]["assist_pts"]/n,"cs_points":aux[p.player_id]["cs_pts"]/n,"save_points":aux[p.player_id]["save_pts"]/n,"dc_points":aux[p.player_id]["dc_pts"]/n,"negative_points":aux[p.player_id]["negative_pts"]/n,"gc_points":aux[p.player_id]["gc_pts"]/n,"penalty_miss_points":aux[p.player_id]["penalty_miss_pts"]/n,"penalty_save_points":aux[p.player_id]["penalty_save_pts"]/n}
    return ans
