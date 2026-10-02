#!/usr/bin/env python3
"""Unified role-aware deadline P(start) -> canonical xMins output.

This is the bridge between the tactical role layer and the existing event model.
It keeps the existing fitted duration/cameo mechanics, but replaces the old
coarse-position start probability with role-aware constrained P(start).

Required DB tables:
  club_matches_v2, player_match_roles_v2, player_availability_v2,
  player_registration_v2, player_cold_start_role_prior_v2, forecast_match_context_v2

Required role features:
  data_v1_1/features/pstart_v2_roles/player_role_state.csv
  data_v1_1/features/pstart_v2_roles/role_capacities.csv
"""
from __future__ import annotations
import argparse, sqlite3, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.pstart_v2 import (
    AvailabilityState, ColdStartPrior, MatchImportanceParams, PlayerRoleInput,
    availability_from_status, blend_role_state_with_cold_prior,
    constrained_start_probabilities_deadline, match_importance, minutes_features,
)
from fpl_v1_1_model.minutes import project_minutes

DEFAULT_BASE_VALUES={'PL':1.0,'CL':1.2,'EL':0.9,'ECL':0.75,'FA':0.65,'LC':0.45}
# Frozen Phase3A duration/cameo parameters from the standing model.
DURATION_HALF_LIFE=0.32192611540889443
ROLE_HALF_LIFE_OLD=1.3150986300759975
START_LOGIT_INTERCEPT=0.03186876473704488
START_LOGIT_SLOPE=0.6645162300313383


def latest_before(df, deadline, keys, time_col='asof'):
    if df.empty:return df
    x=df.copy(); x[time_col]=pd.to_datetime(x[time_col],utc=True,errors='coerce')
    x=x[x[time_col].notna() & (x[time_col]<=deadline)]
    if x.empty:return x
    return x.sort_values(time_col).groupby(keys,as_index=False).tail(1)


def load_availability(con, team_id, deadline):
    try:
        d=pd.read_sql_query('''SELECT external_player_id,status,chance_of_playing,reason,observed_at
                               FROM player_availability_v2
                               WHERE team_external_id=? AND observed_at<=? ORDER BY observed_at''',
                            con,params=[str(team_id),deadline.isoformat()])
    except Exception:return {}
    if d.empty:return {}
    d=d.sort_values('observed_at').groupby('external_player_id',as_index=False).tail(1)
    return {str(r.external_player_id):availability_from_status(r.status,r.chance_of_playing,
            reason=r.reason,observed_at=r.observed_at) for r in d.itertuples(index=False)}


def load_registered_players(con, team_id, deadline):
    try:
        d=pd.read_sql_query("""SELECT external_player_id,registration_status,observed_at
                               FROM player_registration_v2 WHERE team_external_id=? AND observed_at<=?
                               ORDER BY observed_at""",con,params=[str(team_id),deadline.isoformat()])
    except Exception:return set()
    if d.empty:return set()
    d=d.sort_values('observed_at').groupby('external_player_id',as_index=False).tail(1)
    inactive={'deregistered','left','loaned_out','inactive'}
    return {str(r.external_player_id) for r in d.itertuples(index=False) if str(r.registration_status).lower() not in inactive}


def load_cold_priors(con, team_id, deadline):
    try:
        d=pd.read_sql_query("""SELECT external_player_id,role,q_prior,hierarchy_prior,prior_equivalent_matches,observed_at,source_name
                               FROM player_cold_start_role_prior_v2
                               WHERE team_external_id=? AND observed_at<=? ORDER BY observed_at""",
                            con,params=[str(team_id),deadline.isoformat()])
    except Exception:return {}
    if d.empty:return {}
    d=d.sort_values('observed_at').groupby(['external_player_id','role'],as_index=False).tail(1)
    return {(str(r.external_player_id),str(r.role)):ColdStartPrior(float(r.q_prior),float(r.hierarchy_prior),
            float(r.prior_equivalent_matches),str(r.observed_at),str(r.source_name)) for r in d.itertuples(index=False)}


def history_rows(con,pid,deadline,n=30):
    d=pd.read_sql_query('''SELECT m.kickoff_at,p.started,p.minutes,p.in_matchday_squad
                           FROM club_matches_v2 m JOIN player_match_roles_v2 p USING(source_match_id)
                           WHERE p.external_player_id=? AND m.kickoff_at<?
                           ORDER BY m.kickoff_at DESC LIMIT ?''',con,
                        params=[str(pid),deadline.isoformat(),int(n)])
    score=[]; duration=[]
    for j,r in enumerate(d.itertuples(index=False),1):
        ko=pd.to_datetime(r.kickoff_at,utc=True,errors='coerce')
        if pd.isna(ko):continue
        # Confirmed absence is not tactical negative evidence.
        if r.in_matchday_squad==0:continue
        rec={'lag_games':j,'started':int(r.started or 0),'minutes':float(r.minutes or 0),
             'days_ago':max(0.,(deadline-ko).total_seconds()/86400.)}
        score.append(rec)
        duration.append({'started':int(r.started or 0),'minutes':float(r.minutes or 0)})
    return score,list(reversed(duration))


def map_player_uuid(con, external_id, source_name=None):
    s=str(external_id)
    # Standing-model identity policy: whenever possible external_player_id is
    # already our stable player_uuid. This is the preferred zero-ambiguity path.
    row=con.execute('SELECT player_uuid FROM players WHERE player_uuid=?',(s,)).fetchone()
    if row:return row[0]
    # Preferred explicit cross-source mapping.
    try:
        if source_name:
            row=con.execute("SELECT player_uuid FROM player_external_ids_v2 WHERE source_name=? AND external_player_id=?",(str(source_name),s)).fetchone()
            if row:return row[0]
        rows=con.execute("SELECT DISTINCT player_uuid FROM player_external_ids_v2 WHERE external_player_id=? LIMIT 2",(s,)).fetchall()
        if len(rows)==1:return rows[0][0]
    except Exception:
        pass
    # Stable native IDs where available.
    rows=con.execute('SELECT player_uuid FROM players WHERE opta_code=? OR CAST(pl_person_id AS TEXT)=? LIMIT 2',(s,s)).fetchall()
    return rows[0][0] if len(rows)==1 else None


def normalise_capacities(rc):
    caps={str(r.role):float(r.capacity) for r in rc.itertuples(index=False) if float(r.capacity)>1e-5}
    if 'GK' in caps:caps['GK']=1.0
    out={k:v for k,v in caps.items() if k!='GK'}; s=sum(out.values())
    if s>0:
        for k in out:caps[k]=10.0*out[k]/s
    return caps


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--role-state',default='data_v1_1/features/pstart_v2_roles/player_role_state.csv')
    ap.add_argument('--role-capacities',default='data_v1_1/features/pstart_v2_roles/role_capacities.csv')
    ap.add_argument('--context-csv',required=True,help='rows: team_external_id,deadline,competition,round_strength,opponent_strength,active_competitions[,season,gw,fixture_uuid]')
    ap.add_argument('--out',default='outputs/v1_1/role_aware_minutes/role_aware_minutes.csv')
    a=ap.parse_args()
    con=sqlite3.connect(ROOT/a.db if not Path(a.db).is_absolute() else a.db)
    rs=pd.read_csv(ROOT/a.role_state if not Path(a.role_state).is_absolute() else a.role_state)
    rc=pd.read_csv(ROOT/a.role_capacities if not Path(a.role_capacities).is_absolute() else a.role_capacities)
    ctx=pd.read_csv(a.context_csv)
    rows=[]
    for c in ctx.itertuples(index=False):
        deadline=pd.to_datetime(c.deadline,utc=True)
        tid=str(c.team_external_id)
        rsi=latest_before(rs[rs.team_external_id.astype(str)==tid],deadline,['external_player_id','role'])
        rci=latest_before(rc[rc.team_external_id.astype(str)==tid],deadline,['role'])
        if rsi.empty or rci.empty:continue
        avail=load_availability(con,tid,deadline)
        registered=load_registered_players(con,tid,deadline)
        cold_priors=load_cold_priors(con,tid,deadline)
        # Blend observed new-team role state with pre-debut priors.  New signings
        # can therefore enter the forecast before their first match; the prior
        # fades mechanically as new-team evidence accumulates.
        role_rows=[]; observed_keys=set()
        for r in rsi.itertuples(index=False):
            pid=str(r.external_player_id); role=str(r.role); observed_keys.add((pid,role))
            qev=float(getattr(r,'role_evidence',0.0) or 0.0); hev=float(getattr(r,'hierarchy_evidence',0.0) or 0.0)
            qv,hv=blend_role_state_with_cold_prior(q_observed=float(r.q_role),q_evidence=qev,
                hierarchy_observed=float(r.hierarchy_role),hierarchy_evidence=hev,prior=cold_priors.get((pid,role)))
            role_rows.append((pid,role,qv,hv,qev,hev))
        for (pid,role),prior in cold_priors.items():
            if (pid,role) in observed_keys:continue
            if registered and pid not in registered:continue
            role_rows.append((pid,role,float(prior.q_role),float(prior.hierarchy_role),0.0,0.0))
        active=[z.strip() for z in str(getattr(c,'active_competitions','PL')).split(',') if z.strip()]
        imp=match_importance(competition=str(c.competition),active_competitions=active,
            round_strength=float(c.round_strength),opponent_strength=float(c.opponent_strength),
            base_values=DEFAULT_BASE_VALUES,params=MatchImportanceParams())
        inputs=[]; cache={}; dur={}
        for pid,role,qv,hv,qev,hev in role_rows:
            if registered and pid not in registered:continue
            if pid not in cache:
                hscore,hdur=history_rows(con,pid,deadline); cache[pid]=minutes_features(hscore)
                # duration only: p_start below is discarded and replaced by role-aware P(start)
                dur[pid]=project_minutes(hdur,role_half_life=ROLE_HALF_LIFE_OLD,
                    duration_half_life=DURATION_HALF_LIFE,start_logit_intercept=START_LOGIT_INTERCEPT,
                    start_logit_slope=START_LOGIT_SLOPE)
            inputs.append(PlayerRoleInput(pid,role,float(qv),float(hv),cache[pid],role=='GK'))
        caps=normalise_capacities(rci)
        ps,alloc=constrained_start_probabilities_deadline(inputs,importance=imp,role_capacity=caps,availability=avail)
        for pid,p_start in ps.items():
            av=avail.get(pid,AvailabilityState()).cap
            d=dur[pid]
            bench_available=max(0.0,av-p_start)
            xmins=p_start*d.expected_minutes_given_start + bench_available*d.p_cameo_given_bench*d.expected_minutes_given_cameo
            ar=sorted([(role,v) for (p,role),v in alloc.items() if p==pid and v>1e-9],key=lambda z:-z[1])
            rec={'deadline':deadline.isoformat(),'team_external_id':tid,'external_player_id':pid,
                 'player_uuid':map_player_uuid(con,pid,getattr(c,'source_name',None)),'match_importance':imp,'availability_cap':av,
                 'role_aware_p_start':p_start,'role_aware_expected_minutes':xmins,
                 'expected_minutes_if_start':d.expected_minutes_given_start,
                 'p_cameo_given_bench':d.p_cameo_given_bench,'expected_minutes_if_cameo':d.expected_minutes_given_cameo,
                 'primary_start_role':ar[0][0] if ar else None,'primary_start_role_mass':ar[0][1] if ar else 0.0,
                 'role_assignment_json':';'.join(f'{rr}:{vv:.6f}' for rr,vv in ar),
                 'cold_start':int(any(k[0]==pid for k in cold_priors)),
                 'new_team_role_evidence':max([x[4] for x in role_rows if x[0]==pid] or [0.0])}
            for col in ('season','gw','fixture_uuid'):
                if hasattr(c,col):rec[col]=getattr(c,col)
            rows.append(rec)
    out=pd.DataFrame(rows)
    p=ROOT/a.out if not Path(a.out).is_absolute() else Path(a.out); p.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(p,index=False)
    audit={'rows':len(out),'teams':int(out.team_external_id.nunique()) if len(out) else 0,
           'sum_p_start_by_team_context':out.groupby(['deadline','team_external_id']).role_aware_p_start.sum().round(10).to_dict() if len(out) else {}}
    import json
    p.with_suffix('.audit.json').write_text(json.dumps(audit,indent=2,default=str),encoding='utf-8')
    print(json.dumps(audit,indent=2,default=str))

if __name__=='__main__':main()
