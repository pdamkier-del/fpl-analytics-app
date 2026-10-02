#!/usr/bin/env python3
"""Build role-aware deadline P(start) + xMins from cutoff-safe states.

Inputs
------
* player_role_state.csv from v1_1_build_role_hierarchy.py
* role_capacities.csv from same builder
* player_availability_v2 timestamped snapshots (optional, SQLite)
* historical club match roles for recent minutes/workload
* one forecast match context row (deadline, competition, opponent strength)

The script never reads a state observed after the deadline.
"""
from __future__ import annotations
import argparse, sqlite3, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.pstart_v2 import (
    AvailabilityState, MatchImportanceParams, MinutesFeatures, PlayerRoleInput,
    ColdStartPrior, availability_from_status, blend_role_state_with_cold_prior,
    constrained_start_probabilities_deadline, expected_minutes_from_start_probability,
    match_importance, minutes_features,
)

DEFAULT_BASE_VALUES={'PL':1.0,'CL':1.2,'EL':0.9,'ECL':0.75,'FA':0.65,'LC':0.45}


def latest_before(df, deadline, keys, time_col='asof'):
    if df.empty:return df
    x=df.copy(); x[time_col]=pd.to_datetime(x[time_col],utc=True,errors='coerce')
    x=x[x[time_col].notna() & (x[time_col]<=deadline)]
    if x.empty:return x
    return x.sort_values(time_col).groupby(keys,as_index=False).tail(1)


def load_availability(con, team_id, deadline):
    try:
        q='''SELECT external_player_id,status,chance_of_playing,reason,observed_at
             FROM player_availability_v2
             WHERE team_external_id=? AND observed_at<=?
             ORDER BY observed_at'''
        d=pd.read_sql_query(q,con,params=[str(team_id),deadline.isoformat()])
    except Exception:
        return {}
    if d.empty:return {}
    d=d.sort_values('observed_at').groupby('external_player_id',as_index=False).tail(1)
    out={}
    for r in d.itertuples(index=False):
        out[str(r.external_player_id)]=availability_from_status(
            r.status,r.chance_of_playing,reason=r.reason,observed_at=r.observed_at)
    return out




def load_registered_players(con, team_id, deadline):
    try:
        q="""SELECT external_player_id,registration_status,observed_at
             FROM player_registration_v2
             WHERE team_external_id=? AND observed_at<=?
             ORDER BY observed_at"""
        d=pd.read_sql_query(q,con,params=[str(team_id),deadline.isoformat()])
    except Exception:
        return set()
    if d.empty:return set()
    d=d.sort_values('observed_at').groupby('external_player_id',as_index=False).tail(1)
    inactive={'deregistered','left','loaned_out','inactive'}
    return {str(r.external_player_id) for r in d.itertuples(index=False) if str(r.registration_status).lower() not in inactive}


def load_cold_priors(con, team_id, deadline):
    try:
        q="""SELECT external_player_id,role,q_prior,hierarchy_prior,prior_equivalent_matches,observed_at,source_name
             FROM player_cold_start_role_prior_v2
             WHERE team_external_id=? AND observed_at<=?
             ORDER BY observed_at"""
        d=pd.read_sql_query(q,con,params=[str(team_id),deadline.isoformat()])
    except Exception:
        return {}
    if d.empty:return {}
    d=d.sort_values('observed_at').groupby(['external_player_id','role'],as_index=False).tail(1)
    out={}
    for r in d.itertuples(index=False):
        out[(str(r.external_player_id),str(r.role))]=ColdStartPrior(
            q_role=float(r.q_prior), hierarchy_role=float(r.hierarchy_prior),
            prior_equivalent_matches=float(r.prior_equivalent_matches),
            observed_at=str(r.observed_at),source_name=str(r.source_name))
    return out


def player_history(con, player_id, deadline, n=20):
    q='''SELECT m.kickoff_at,p.started,p.minutes,p.in_matchday_squad
         FROM club_matches_v2 m JOIN player_match_roles_v2 p USING(source_match_id)
         WHERE p.external_player_id=? AND m.kickoff_at<?
         ORDER BY m.kickoff_at DESC LIMIT ?'''
    d=pd.read_sql_query(q,con,params=[str(player_id),deadline.isoformat(),int(n)])
    rows=[]
    for j,r in enumerate(d.itertuples(index=False),1):
        ko=pd.to_datetime(r.kickoff_at,utc=True,errors='coerce')
        if pd.isna(ko):continue
        # If we explicitly know he was out of the matchday squad, don't treat the
        # zero as tactical negative evidence in start-rate denominators.
        if r.in_matchday_squad == 0:
            continue
        rows.append({'lag_games':j,'started':int(r.started or 0),'minutes':float(r.minutes or 0),
                     'days_ago':max(0.,(deadline-ko).total_seconds()/86400.)})
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--role-state',default='data_v1_1/features/player_role_state.csv')
    ap.add_argument('--role-capacities',default='data_v1_1/features/role_capacities.csv')
    ap.add_argument('--team-id',required=True); ap.add_argument('--deadline',required=True)
    ap.add_argument('--competition',default='PL'); ap.add_argument('--round-strength',type=float,default=0.5)
    ap.add_argument('--opponent-strength',type=float,default=0.5)
    ap.add_argument('--active-competitions',default='PL,CL,FA,LC')
    ap.add_argument('--out',required=True)
    a=ap.parse_args()

    deadline=pd.to_datetime(a.deadline,utc=True)
    rs=pd.read_csv(a.role_state); rc=pd.read_csv(a.role_capacities)
    rs=rs[rs.team_external_id.astype(str)==str(a.team_id)].copy()
    rc=rc[rc.team_external_id.astype(str)==str(a.team_id)].copy()
    rs=latest_before(rs,deadline,['external_player_id','role'])
    rc=latest_before(rc,deadline,['role'])
    if rs.empty or rc.empty: raise SystemExit('no cutoff-safe role state/capacity for team before deadline')

    con=sqlite3.connect(a.db)
    avail=load_availability(con,a.team_id,deadline)
    registered=load_registered_players(con,a.team_id,deadline)
    cold_priors=load_cold_priors(con,a.team_id,deadline)

    # New signings can exist before their first new-club appearance.  Add their
    # prior role edges to the deadline state, then let empirical-Bayes blending
    # fade the prior as actual new-team evidence accumulates.
    role_rows=[]
    observed_keys=set()
    for r in rs.itertuples(index=False):
        pid=str(r.external_player_id); role=str(r.role); observed_keys.add((pid,role))
        prior=cold_priors.get((pid,role))
        qev=float(getattr(r,'role_evidence',0.0) or 0.0)
        hev=float(getattr(r,'hierarchy_evidence',0.0) or 0.0)
        qv,hv=blend_role_state_with_cold_prior(
            q_observed=float(r.q_role),q_evidence=qev,
            hierarchy_observed=float(r.hierarchy_role),hierarchy_evidence=hev,prior=prior)
        role_rows.append((pid,role,qv,hv,qev,hev))
    for (pid,role),prior in cold_priors.items():
        if (pid,role) in observed_keys: continue
        if registered and pid not in registered: continue
        role_rows.append((pid,role,float(prior.q_role),float(prior.hierarchy_role),0.0,0.0))

    active=[x.strip() for x in a.active_competitions.split(',') if x.strip()]
    imp=match_importance(competition=a.competition,active_competitions=active,
                         round_strength=a.round_strength,opponent_strength=a.opponent_strength,
                         base_values=DEFAULT_BASE_VALUES,params=MatchImportanceParams())

    inputs=[]; minute_cache={}
    for pid,role,qv,hv,qev,hev in role_rows:
        if registered and pid not in registered: continue
        if pid not in minute_cache:
            minute_cache[pid]=minutes_features(player_history(con,pid,deadline))
        inputs.append(PlayerRoleInput(pid,role,float(qv),float(hv),
                                      minute_cache[pid],is_goalkeeper=role=='GK'))

    capacities={str(r.role):float(r.capacity) for r in rc.itertuples(index=False) if float(r.capacity)>1e-5}
    # Normalize learned formation usage to exactly 11. GK is forced to one if present;
    # outfield proportions retain the team's learned formation shape.
    if 'GK' in capacities: capacities['GK']=1.0
    out_roles={k:v for k,v in capacities.items() if k!='GK'}
    s=sum(out_roles.values())
    if s>0:
        for k in out_roles: capacities[k]=10.0*out_roles[k]/s

    pstart,alloc=constrained_start_probabilities_deadline(inputs,importance=imp,role_capacity=capacities,
                                                          availability=avail)
    rows=[]
    for pid,ps in sorted(pstart.items()):
        av=avail.get(pid,AvailabilityState()).cap
        # Duration/cameo parameters are deliberately transparent defaults here;
        # production can inject the existing fitted Phase3A duration model.
        xm=expected_minutes_from_start_probability(ps,expected_minutes_if_start=78.0,
                                                    p_cameo_if_bench=0.35,expected_minutes_if_cameo=22.0,
                                                    availability_cap=av)
        roles=sorted([(r,v) for (p,r),v in alloc.items() if p==pid and v>1e-7],key=lambda z:z[1],reverse=True)
        rows.append({'deadline':deadline.isoformat(),'team_external_id':a.team_id,'external_player_id':pid,
                     'match_importance':imp,'availability_cap':av,'p_start':ps,'expected_minutes':xm,
                     'primary_start_role':roles[0][0] if roles else None,
                     'primary_start_role_mass':roles[0][1] if roles else 0.0,
                     'cold_start':int(any(k[0]==pid for k in cold_priors)),
                     'new_team_role_evidence':max([x[4] for x in role_rows if x[0]==pid] or [0.0])})
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(rows).to_csv(out,index=False)
    print('wrote',out,'players',len(rows),'sum P(start)=',sum(pstart.values()),'importance=',imp)

if __name__=='__main__':main()
