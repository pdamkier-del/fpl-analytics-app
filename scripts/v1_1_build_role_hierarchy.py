#!/usr/bin/env python3
"""Build dynamic player role shares q(i,r), role-specific hierarchy H(i,r),
and team candidate groups from historical match-role observations.

Inputs are rows in player_match_roles_v2. Every output row is cutoff-safe: the
state written after a match uses that match and earlier observations only.

Key ideas
---------
q(i,r): recency-weighted fraction of the player's on-pitch role-minutes spent in role r.
H(i,r): recency-weighted share of the team's starter-equivalent evidence in role r,
        adjusted for the recent number of starting slots used in that role.
primary/secondary: derived from q, never from FPL position.
role_capacity: recent weighted mean number of starters in role r per match.

No hand-set player rankings are used.
"""
from __future__ import annotations

import argparse
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

# Fine enough to separate tactical jobs, still stable enough for historical data.
ROLES = [
    'GK',
    'RB','RWB','RCB','CB','LCB','LWB','LB',
    'RDM','DM','LDM','RCM','CM','LCM','RAM','AM','LAM',
    'RW','LW','SS','ST',
]

# Soft smoothing. This is symmetric across players/roles and is not a manual
# football correction factor; it only prevents zero-probability states.
ROLE_ALPHA = 0.05
HIER_ALPHA = 0.10


def decay(days: float, half_life_matches: float) -> float:
    # Seven days is only the clock conversion. Half-life is tuned later by CV.
    return 2.0 ** (-(max(0.0, days) / 7.0) / float(half_life_matches))


def normalize_role(raw: object) -> str | None:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    s = str(raw).upper().replace(' ', '').replace('-', '')
    aliases = {
        'G':'GK','GK':'GK','GOALKEEPER':'GK',
        'RB':'RB','DR':'RB','RWB':'RWB','WBR':'RWB',
        'RCB':'RCB','DCR':'RCB','CB':'CB','DC':'CB','LCB':'LCB','DCL':'LCB',
        'LWB':'LWB','WBL':'LWB','LB':'LB','DL':'LB',
        'RDM':'RDM','DMR':'RDM','CDMR':'RDM','DM':'DM','CDM':'DM','DMC':'DM','LDM':'LDM','DML':'LDM','CDML':'LDM',
        'RCM':'RCM','MCR':'RCM','CM':'CM','MC':'CM','LCM':'LCM','MCL':'LCM',
        'RAM':'RAM','AMR':'RAM','AM':'AM','CAM':'AM','AMC':'AM','LAM':'LAM','AML':'LAM',
        'RW':'RW','RWF':'RW','MR':'RW','LW':'LW','LWF':'LW','ML':'LW',
        'SS':'SS','SECONDSTRIKER':'SS','CF':'SS',
        'ST':'ST','FW':'ST','F':'ST','STRIKER':'ST',
    }
    return aliases.get(s)


def role_family(role: str) -> str:
    if role == 'GK': return 'GK'
    if role in {'RB','RWB','RCB','CB','LCB','LWB','LB'}: return 'DEF'
    if role in {'RDM','DM','LDM','RCM','CM','LCM'}: return 'MID'
    if role in {'RAM','AM','LAM','RW','LW'}: return 'AM'
    return 'FWD'


def primary_secondary(qmap: dict[str,float], primary_cut: float, secondary_cut: float):
    ordered = sorted(qmap.items(), key=lambda kv: (-kv[1], kv[0]))
    primary = ordered[0][0] if ordered else None
    labels = {}
    for r,q in ordered:
        if r == primary and q >= primary_cut:
            labels[r] = 'primary'
        elif q >= secondary_cut:
            labels[r] = 'secondary'
        else:
            labels[r] = 'other'
    return primary, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--out-dir', default='data_v1_1/features/pstart_v2_roles')
    ap.add_argument('--role-half-life', type=float, default=10.0)
    ap.add_argument('--hier-half-life', type=float, default=10.0)
    ap.add_argument('--capacity-half-life', type=float, default=8.0)
    ap.add_argument('--primary-cut', type=float, default=0.50)
    ap.add_argument('--secondary-cut', type=float, default=0.12)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    sql = '''
      SELECT m.source_match_id,m.kickoff_at,m.competition,m.competition_stage,
             p.external_player_id,p.player_name,p.team_external_id,p.started,
             p.minutes,p.in_matchday_squad,p.role,p.role_x,p.role_y
      FROM club_matches_v2 m
      JOIN player_match_roles_v2 p USING(source_match_id)
      ORDER BY m.kickoff_at,m.source_match_id,p.team_external_id,p.external_player_id
    '''
    df = pd.read_sql_query(sql, con)
    if df.empty:
        print('no player_match_roles_v2 rows; run a lineup/role backfill first')
        return
    df['kickoff_at'] = pd.to_datetime(df['kickoff_at'], utc=True, errors='coerce')
    df['role_norm'] = df['role'].map(normalize_role)
    df = df[df['kickoff_at'].notna() & df['team_external_id'].notna() & df['external_player_id'].notna()].copy()

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    # State containers per team. We decay them in elapsed time before each match.
    player_role_minutes = defaultdict(lambda: defaultdict(float))       # (team,player)->role->mass
    player_role_starts = defaultdict(lambda: defaultdict(float))        # (team,player)->role->start-equivalent
    team_role_starts = defaultdict(lambda: defaultdict(float))          # team->role->all starter evidence
    team_role_capacity_num = defaultdict(lambda: defaultdict(float))    # team->role->weighted starter count sum
    team_role_capacity_den = defaultdict(float)                         # team->weighted matches
    names = {}
    last_team_time = {}

    snapshot_rows=[]; candidate_rows=[]; capacity_rows=[]

    # One update per team-match, then one snapshot for all known team players.
    grouped = df.groupby(['kickoff_at','source_match_id','team_external_id'], sort=True, dropna=False)
    for (ko, mid, tid), g in grouped:
        tid=str(tid); ko=pd.Timestamp(ko)
        prev=last_team_time.get(tid)
        if prev is not None:
            days=max(0.0,(ko-prev).total_seconds()/86400.0)
            d_role=decay(days,args.role_half_life)
            d_h=decay(days,args.hier_half_life)
            d_c=decay(days,args.capacity_half_life)
            for key in [k for k in player_role_minutes if k[0]==tid]:
                for r in list(player_role_minutes[key]): player_role_minutes[key][r]*=d_role
                for r in list(player_role_starts[key]): player_role_starts[key][r]*=d_h
            for r in list(team_role_starts[tid]): team_role_starts[tid][r]*=d_h
            for r in list(team_role_capacity_num[tid]): team_role_capacity_num[tid][r]*=d_c
            team_role_capacity_den[tid]*=d_c

        # Capacity evidence: count actual starters in each normalized role this match.
        starter_counts=defaultdict(float)
        for row in g.itertuples(index=False):
            pid=str(row.external_player_id); names[(tid,pid)]=str(row.player_name)
            role=row.role_norm
            if role not in ROLES: continue
            mins=max(0.0,float(row.minutes or 0.0))
            # Role share learns from actual on-pitch use. A full starter gives 1.0 mass.
            role_mass=min(1.35,mins/90.0)
            player_role_minutes[(tid,pid)][role]+=role_mass
            # Hierarchy is role-specific and start-led, with cameo credit.
            ev=1.0 if int(row.started or 0)==1 else 0.30*min(1.0,mins/90.0)
            # An explicitly out-of-squad row must not count as negative evidence.
            if row.in_matchday_squad is False or row.in_matchday_squad == 0:
                ev=0.0
            player_role_starts[(tid,pid)][role]+=ev
            team_role_starts[tid][role]+=ev
            if int(row.started or 0)==1:
                starter_counts[role]+=1.0

        team_role_capacity_den[tid]+=1.0
        for r,c in starter_counts.items(): team_role_capacity_num[tid][r]+=c

        # Build state after this match. This becomes prior information for later matches.
        team_players=sorted({pid for (tt,pid) in player_role_minutes if tt==tid})
        q_by_player={}
        for pid in team_players:
            masses={r:player_role_minutes[(tid,pid)].get(r,0.0)+ROLE_ALPHA for r in ROLES}
            # Do not allow GK smoothing to leak into outfield and vice versa.
            observed=[r for r in ROLES if player_role_minutes[(tid,pid)].get(r,0.0)>0]
            is_gk=(observed and all(r=='GK' for r in observed))
            allowed=['GK'] if is_gk else [r for r in ROLES if r!='GK']
            den=sum(masses[r] for r in allowed)
            qmap={r:(masses[r]/den if r in allowed and den>0 else 0.0) for r in ROLES}
            q_by_player[pid]=qmap

        # Capacity is learned from formation usage rather than hard-coded.
        capacities={}
        den_cap=max(1e-9,team_role_capacity_den[tid])
        for r in ROLES:
            capacities[r]=team_role_capacity_num[tid].get(r,0.0)/den_cap
            if capacities[r]>1e-6:
                capacity_rows.append({'asof':ko.isoformat(),'source_match_id':mid,'team_external_id':tid,'role':r,
                                      'role_family':role_family(r),'capacity':capacities[r]})

        # H(i,r): player role start mass divided by team role start mass, scaled by
        # learned role capacity. Thus two regular CBs can both have high H when the
        # team normally starts two centre-backs.
        H={}
        for r in ROLES:
            total=team_role_starts[tid].get(r,0.0)
            cap=max(0.25,capacities.get(r,0.0)) if total>0 else 0.0
            candidates=[pid for pid in team_players if player_role_starts[(tid,pid)].get(r,0.0)>0 or q_by_player[pid][r]>=args.secondary_cut]
            smooth_den=total + HIER_ALPHA*max(1,len(candidates))
            for pid in team_players:
                mass=player_role_starts[(tid,pid)].get(r,0.0)
                share=(mass+HIER_ALPHA)/(smooth_den) if pid in candidates and smooth_den>0 else 0.0
                H[(pid,r)]=min(0.995,max(0.0,cap*share))

        for pid in team_players:
            qmap=q_by_player[pid]
            primary,labels=primary_secondary(qmap,args.primary_cut,args.secondary_cut)
            for r in ROLES:
                qv=qmap[r]
                if qv < 0.01 and H[(pid,r)] <= 0: continue
                snapshot_rows.append({
                    'asof':ko.isoformat(),'source_match_id':mid,'team_external_id':tid,
                    'external_player_id':pid,'player_name':names.get((tid,pid),pid),
                    'role':r,'role_family':role_family(r),'q_role':qv,
                    'role_label':labels.get(r,'other'),'primary_role':primary,
                    'hierarchy_role':H[(pid,r)],
                    'role_evidence':sum(player_role_minutes[(tid,pid)].values()),
                    'hierarchy_evidence':sum(player_role_starts[(tid,pid)].values()),
                    'role_capacity':capacities.get(r,0.0),
                })

        # Candidate table is role-centric and easy to inspect in UI/model diagnostics.
        for r in ROLES:
            cand=[]
            for pid in team_players:
                qv=q_by_player[pid][r]; hv=H[(pid,r)]
                if qv>=args.secondary_cut or hv>0.03:
                    # Ranking is descriptive only; actual P(start) uses the full score.
                    rank_score=qv*max(hv,1e-6)
                    cand.append((rank_score,pid,qv,hv))
            cand.sort(reverse=True)
            for rank,(_,pid,qv,hv) in enumerate(cand,1):
                candidate_rows.append({
                    'asof':ko.isoformat(),'source_match_id':mid,'team_external_id':tid,'role':r,
                    'role_capacity':capacities.get(r,0.0),'candidate_rank':rank,
                    'external_player_id':pid,'player_name':names.get((tid,pid),pid),
                    'q_role':qv,'hierarchy_role':hv,
                    'candidate_type':'primary' if qv>=args.primary_cut else ('secondary' if qv>=args.secondary_cut else 'depth')
                })
        last_team_time[tid]=ko

    pd.DataFrame(snapshot_rows).to_csv(out_dir/'player_role_state.csv',index=False)
    pd.DataFrame(candidate_rows).to_csv(out_dir/'role_candidates.csv',index=False)
    pd.DataFrame(capacity_rows).to_csv(out_dir/'role_capacities.csv',index=False)

    latest=(pd.DataFrame(candidate_rows).sort_values('asof').groupby(['team_external_id','role'],as_index=False).tail(20)
            if candidate_rows else pd.DataFrame())
    if not latest.empty: latest.to_csv(out_dir/'role_candidates_latest.csv',index=False)
    print('wrote',len(snapshot_rows),'player-role states,',len(candidate_rows),'candidate rows,',len(capacity_rows),'capacity rows')

if __name__=='__main__':
    main()
