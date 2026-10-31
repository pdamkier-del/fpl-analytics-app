"""B-only conserved event process; locked joint_simulator is never edited.

Reuse its physical timeline, conditional penalty law, scoring and BPS helpers.
Inclusive score means reserve both explicit penalty and own-goal mass.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import numpy as np
from . import joint_simulator as legacy
from .experimental_penalty_neutral import conditional_penalty_conversion
from .experimental_physical_timeline import validate_timeline
VERSION='B-conserved-goal-events-v1'

@dataclass(frozen=True)
class GoalEvent:
    time:float
    team:str
    kind:str
    scorer:str|None=None
    assister:str|None=None
    own_goal_committer:str|None=None
    assist_eligible:bool=False

def attribute(event,players,out):
    by={p.player_id:p for p in players}
    if event.kind not in ('ordinary','penalty','own_goal','unlisted'):raise ValueError('Unknown goal category')
    if event.kind=='unlisted':raise ValueError('Unlisted scoring event is Not Available for strict verified roster')
    if event.kind=='own_goal':
        if event.scorer is not None or event.own_goal_committer not in by or by[event.own_goal_committer].team==event.team:raise ValueError('Invalid own-goal attribution')
        out[event.own_goal_committer].own_goal+=1
    else:
        if event.scorer not in by or by[event.scorer].team!=event.team:raise ValueError('Team goal has no valid scorer')
        out[event.scorer].goals+=1
        if event.kind=='penalty':out[event.scorer].penalty_goals+=1
    if event.assister is not None:
        if not event.assist_eligible or event.assister not in by or by[event.assister].team!=event.team or event.assister==event.scorer:raise ValueError('Ineligible FPL assist')
        out[event.assister].assists+=1

def takers(inp,active):
    candidates=active
    if inp.experimental_penalty_hierarchy:
        ranked=[p for p in active if p.penalty_order is not None and p.penalty_order>0]
        if ranked:candidates=[p for p in ranked if p.penalty_order==min(q.penalty_order for q in ranked)]
    weights=[p.penalty_weight for p in candidates]
    if sum(weights)<=0:weights=[p.goal_weight if p.penalty_fallback_weight is None else p.penalty_fallback_weight for p in candidates]
    return candidates,weights

def simulate_match(inp,rng,*,trace=None,timeline=None):
    if timeline is None:raise ValueError('Conserved B events require the shared physical minute timeline')
    validate_timeline(inp,timeline)
    ps=list(inp.players);out={p.player_id:legacy.PlayerSimResult()for p in ps};intervals={}
    for p in ps:
        m,a,b=timeline[p.player_id];out[p.player_id].minutes=m;out[p.player_id].started=int(m>0 and a==0);intervals[p.player_id]=(a,b)
    def active(team,t):return [p for p in ps if p.team==team and intervals[p.player_id][0]<=t<intervals[p.player_id][1]]
    mass={inp.home_team:0.,inp.away_team:0.};events=[]
    for p in ps:
        a,b=intervals[p.player_id]
        if b<=a:continue
        probability=float(p.p_own_goal)
        if not np.isfinite(probability)or not 0<=probability<=1:raise ValueError('Invalid own-goal probability')
        opp=inp.away_team if p.team==inp.home_team else inp.home_team;mass[opp]+=probability
        if rng.random()<probability:events.append(GoalEvent(min(float(rng.uniform(a,b)),float(np.nextafter(b,a))),opp,'own_goal',own_goal_committer=p.player_id))
    attempts={inp.home_team:float(inp.lambda_home_penalties),inp.away_team:float(inp.lambda_away_penalties)};means={inp.home_team:float(inp.lambda_home_goals),inp.away_team:float(inp.lambda_away_goals)};open_means={};conversion={}
    for team in means:
        if not np.isfinite([means[team],attempts[team]]).all()or min(means[team],attempts[team])<0:raise ValueError('Invalid team goal source')
        conversion[team]=conditional_penalty_conversion(inp,intervals,team)
        ordinary=means[team]-attempts[team]*conversion[team]-mass[team]
        if ordinary < -1e-12:raise ValueError('Own-goal plus conditional penalty budget exceeds inclusive goal mean')
        open_means[team]=max(0.,ordinary)
        edges=sorted({0,90,*[v for p in ps if p.team==team for v in intervals[p.player_id]]})
        for a,b in zip(edges,edges[1:]):
            if a==b:continue
            on=active(team,(a+b)/2)
            if ordinary>0 and sum(p.goal_weight for p in on)<=0:raise ValueError('Positive goal intensity without an eligible scorer')
            if attempts[team]>0 and sum(takers(inp,on)[1])<=0:raise ValueError('Positive penalty intensity without an eligible taker')
        for _ in range(int(rng.poisson(open_means[team]))):
            t=float(rng.uniform(0,90));on=active(team,t);scorer=legacy._weighted_choice(rng,on,[p.goal_weight for p in on])
            if scorer is None:raise ValueError('Unattributed ordinary team goal')
            assister=None
            if rng.random()<inp.assist_probability_per_goal:
                eligible=[p for p in on if p.player_id!=scorer.player_id];assister=legacy._weighted_choice(rng,eligible,[p.assist_weight for p in eligible])
            events.append(GoalEvent(t,team,'ordinary',scorer.player_id,assister.player_id if assister else None,assist_eligible=assister is not None))
    penalty_events=sorted((float(rng.uniform(0,90)),team)for team,lam in attempts.items()for _ in range(int(rng.poisson(lam))))
    for t,team in penalty_events:
        on=active(team,t);candidates,weights=takers(inp,on);taker=legacy._weighted_choice(rng,candidates,weights)
        if taker is None:raise ValueError('Unallocated penalty attempt')
        if rng.random()<np.clip(taker.penalty_conversion,0,1):events.append(GoalEvent(t,team,'penalty',taker.player_id))
        else:
            out[taker.player_id].penalty_miss+=1;opp=inp.away_team if team==inp.home_team else inp.home_team;keepers=[p for p in active(opp,t)if p.is_keeper]
            if keepers and rng.random()<np.clip(inp.p_penalty_save_given_miss,0,1):out[keepers[0].player_id].penalty_saves+=1;out[keepers[0].player_id].saves+=1
    events.sort(key=lambda e:e.time)
    for event in events:attribute(event,ps,out)
    for p in ps:
        r=out[p.player_id];m=r.minutes;a,b=intervals[p.player_id]
        if m<=0:continue
        opp=inp.away_team if p.team==inp.home_team else inp.home_team;r.goals_conceded_while_on_pitch=sum(e.team==opp and a<=e.time<b for e in events);r.clean_sheet=int(m>=60 and r.goals_conceded_while_on_pitch==0)
        if p.is_keeper:
            save_reserve=attempts[opp]*(1-conversion[opp])*np.clip(inp.p_penalty_save_given_miss,0,1);regular=max(0,p.lambda_saves-save_reserve)*m/90;r.saves+=legacy._sample_calibrated_saves(rng,regular,p.save_bucket_tilts)
        r.dc_count=legacy._sample_nb2(rng,max(0,p.dc_mu_90)*m/90,p.dc_alpha);r.dc_points=0 if inp.bps_rules=='2024-25'else legacy.dc_points_from_count(p.position,r.dc_count)
        card=legacy.sample_discipline(rng,p.discipline);r.yellow=int(card=='yellow');r.red=int(card=='red')
    bps={}
    for p in ps:
        r=out[p.player_id];m=r.minutes
        if m<=0:bps[p.player_id]=-10000;continue
        r.points=legacy.nonbonus_total(legacy.point_components(p.position,p.is_keeper,r))
        comp=legacy.BPSComponents(minutes=m,position=p.position,non_penalty_goals=r.goals-r.penalty_goals,penalty_goals=r.penalty_goals,assists=r.assists,clean_sheet=r.clean_sheet,penalty_saves=r.penalty_saves,saves_total=r.saves,saves_inside_box=r.penalty_saves,goals_conceded=r.goals_conceded_while_on_pitch,penalty_misses=r.penalty_miss,yellow_cards=r.yellow,red_cards=r.red,own_goals=r.own_goal)
        rule={'2024-25':legacy.bps_2024_25,'2025-26':legacy.bps_2025_26,'2026-27':legacy.bps_2026_27}.get(inp.bps_rules)
        if rule is None:raise ValueError('Unknown BPS season')
        known=rule(comp)
        if p.bps_background_rate90 is not None:
            frac=m/90;mean=p.bps_background_rate90*frac;sd=(p.bps_background_sd90 or 0)*np.sqrt(frac)
        else:mean=p.bps_background_mean;sd=p.bps_background_sd
        r.bps=int(round(known+(float(rng.normal(mean,sd))if sd>0 else mean)));bps[p.player_id]=r.bps
    for pid,bonus in legacy.allocate_bonus_points(bps).items():
        if out[pid].minutes>0:out[pid].bonus=bonus;out[pid].points+=bonus
    for team in means:
        attributed=sum(out[p.player_id].goals for p in ps if p.team==team);own=sum(out[p.player_id].own_goal for p in ps if p.team!=team)
        if attributed+own!=sum(e.team==team for e in events):raise AssertionError('Shared goal conservation failed')
    if trace is not None:trace.update(events=events,team_scores={t:sum(e.team==t for e in events)for t in means},ordinary_intensity=open_means,own_goal_expected_mass=mass,penalty_conversion=conversion,intervals=intervals,unsupported_forecast_mechanisms=['penalty-winner and own-goal attacking-touch assist occurrence rates: Not Available','causal red-card exit/post-dismissal liability: Not Available'])
    return out

@contextmanager
def conserved_events():
    original=legacy.simulate_match;audit={}
    def observed(inp,rng,*,trace=None,timeline=None):
        receipt={}if trace is None else trace;result=simulate_match(inp,rng,trace=receipt,timeline=timeline)
        for team,total in receipt['team_scores'].items():
            row=audit.setdefault(str(team),dict(draws=0,team_goals=0,ordinary=0,penalty=0,own_goal=0,unattributed=0,assists_without_eligible_event=0,max_expected_budget_error=0.))
            row['draws']+=1;row['team_goals']+=total
            for event in receipt['events']:
                if event.team==team:row[event.kind]+=1
            wanted=inp.lambda_home_goals if team==inp.home_team else inp.lambda_away_goals
            attempts=inp.lambda_home_penalties if team==inp.home_team else inp.lambda_away_penalties
            actual=receipt['ordinary_intensity'][team]+attempts*receipt['penalty_conversion'][team]+receipt['own_goal_expected_mass'][team]
            row['max_expected_budget_error']=max(row['max_expected_budget_error'],abs(actual-wanted))
        return result
    legacy.simulate_match=observed
    try:yield audit
    finally:legacy.simulate_match=original
