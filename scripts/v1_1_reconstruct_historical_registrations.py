#!/usr/bin/env python3
"""Reconstruct historical PL registration/team membership from FPL GW rosters.

Registration-only: no injury/suspension status is invented.
The historical merged-GW source contains all FPL-listed players for teams that
have a fixture in the GW, including zero-minute players. Therefore blank-GW
teams are not updated at all.

Each reconstructed roster is timestamped at a transparent deadline proxy:
90 minutes before the earliest kickoff in that GW.
"""
from __future__ import annotations
import argparse, sqlite3
import pandas as pd


def team_key(season, team_id):
    return f"{season}:{int(team_id)}"


def insert_event(con, pid, season, team, t, status, source):
    before=con.total_changes
    con.execute(
        "INSERT OR IGNORE INTO player_registration_v2 "
        "(external_player_id,team_external_id,observed_at,registration_status,source_name,payload_path) "
        "VALUES (?,?,?,?,?,?)",
        (pid,team_key(season,team),t,status,source,'player_fixture_observations')
    )
    return int(con.total_changes>before)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--seasons',default='2022-23,2024-25,2025-26')
    ap.add_argument('--deadline-offset-minutes',type=int,default=90)
    ap.add_argument('--source-name',default='historical_fpl_roster_proxy')
    a=ap.parse_args()
    seasons=[s.strip() for s in a.seasons.split(',') if s.strip()]
    con=sqlite3.connect(a.db)
    total_ins=0; audit=[]

    for season in seasons:
        d=pd.read_sql_query(
            "SELECT gw,team_id,player_uuid,kickoff_at FROM player_fixture_observations "
            "WHERE season=? AND gw IS NOT NULL AND team_id IS NOT NULL AND kickoff_at IS NOT NULL",
            con,params=[season]
        )
        if d.empty:
            audit.append({'season':season,'status':'no_rows'}); continue
        d['kickoff_at']=pd.to_datetime(d['kickoff_at'],utc=True,errors='coerce')
        d=d[d.kickoff_at.notna()].copy()
        deadlines=d.groupby('gw',as_index=False).kickoff_at.min()
        deadlines['deadline']=deadlines.kickoff_at-pd.to_timedelta(a.deadline_offset_minutes,unit='m')
        deadline_map=dict(zip(deadlines.gw.astype(int),deadlines.deadline))

        # Only teams with a fixture in the GW have a roster snapshot here.
        rosters={}
        for gw,g in d.groupby('gw'):
            rosters[int(gw)]={
                int(team): set(str(x) for x in tg.player_uuid.dropna().unique())
                for team,tg in g.groupby('team_id')
            }

        prev_team_roster={}
        player_team={}
        inserted=registrations=lefts=transfers=departures=0
        all_players=set()

        for gw in sorted(rosters):
            current_by_team=rosters[gw]
            t=deadline_map[gw].isoformat()
            current_player_team={pid:team for team,ps in current_by_team.items() for pid in ps}
            all_players.update(current_player_team)

            # Close old memberships only for teams that actually have a current roster snapshot.
            for team,current in current_by_team.items():
                previous=prev_team_roster.get(team,set())
                for pid in previous-current:
                    n=insert_event(con,pid,season,team,t,'left',a.source_name)
                    inserted+=n; lefts+=n
                    new_team=current_player_team.get(pid)
                    if new_team is not None and new_team!=team: transfers+=1
                    else: departures+=1
                    if player_team.get(pid)==team:
                        player_team.pop(pid,None)

            # Open new memberships. If old team did not play this GW, close it here.
            for team,current in current_by_team.items():
                previous=prev_team_roster.get(team,set())
                for pid in current-previous:
                    old_team=player_team.get(pid)
                    if old_team is not None and old_team!=team:
                        n=insert_event(con,pid,season,old_team,t,'left',a.source_name)
                        inserted+=n; lefts+=n
                        transfers+=1
                    n=insert_event(con,pid,season,team,t,'registered',a.source_name)
                    inserted+=n; registrations+=n
                    player_team[pid]=team
                prev_team_roster[team]=current

        con.commit(); total_ins+=inserted
        audit.append({
            'season':season,'gameweeks_with_fixtures':len(rosters),'players_union':len(all_players),
            'inserted':inserted,'registered_events':registrations,'left_events':lefts,
            'team_change_or_reassignment_events':transfers,'roster_departure_events':departures,
            'deadline_proxy':f'earliest kickoff - {a.deadline_offset_minutes}m'
        })

    print({'total_inserted':total_ins,'seasons':audit})

if __name__=='__main__': main()
