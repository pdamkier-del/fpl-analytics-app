#!/usr/bin/env python3
"""Synchronise existing cutoff-safe FPL state into the standing P(start) v2 tables.

Identity policy
---------------
* external_player_id := stable internal player_uuid
* team_external_id   := '<season>:<fpl_team_id>'

This prevents season-local FPL element/team IDs from colliding across seasons.
For registration snapshots, a team change writes a `left` event for the old team
and a `registered` event for the new team at the same cutoff timestamp.
"""
from __future__ import annotations
import argparse, sqlite3
from pathlib import Path

STATUS = {
    'a': 'available',
    'd': 'doubtful',
    'i': 'injured',
    's': 'suspended',
    'u': 'unavailable',
    'n': 'unavailable',
}

def team_key(season, team_id):
    return f"{season}:{int(team_id)}" if team_id is not None else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--source-name',default='fpl_cutoff_state_sync')
    a=ap.parse_args()
    con=sqlite3.connect(a.db)
    con.row_factory=sqlite3.Row

    # v2 tables are created by v1_1_init_multicomp_pstart_v2.py.
    needed={'player_registration_v2','player_availability_v2'}
    have={r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    missing=needed-have
    if missing:
        raise SystemExit(f"missing v2 tables: {sorted(missing)}; run v1_1_init_multicomp_pstart_v2.py first")

    regs=con.execute('''
        SELECT player_uuid,season,team_id,active,observed_at
        FROM player_registrations
        WHERE team_id IS NOT NULL AND observed_at IS NOT NULL
        ORDER BY player_uuid,season,observed_at,team_id
    ''').fetchall()

    reg_rows=0; left_rows=0
    current={}
    for r in regs:
        pid=str(r['player_uuid']); season=str(r['season']); t=str(r['observed_at'])
        tid=team_key(season,r['team_id']); key=(pid,season)
        prev=current.get(key)
        if prev is not None and prev != tid:
            con.execute('''INSERT OR IGNORE INTO player_registration_v2
                (external_player_id,team_external_id,observed_at,registration_status,source_name,payload_path)
                VALUES (?,?,?,?,?,?)''',(pid,prev,t,'left',a.source_name,'player_registrations'))
            left_rows += con.total_changes > 0
        status='registered' if int(r['active'] or 0)==1 else 'inactive'
        before=con.total_changes
        con.execute('''INSERT OR IGNORE INTO player_registration_v2
            (external_player_id,team_external_id,observed_at,registration_status,source_name,payload_path)
            VALUES (?,?,?,?,?,?)''',(pid,tid,t,status,a.source_name,'player_registrations'))
        if con.total_changes>before: reg_rows += 1
        current[key]=tid

    states=con.execute('''
        SELECT player_uuid,season,team_id,status_code,chance_this_round,news_text,observed_at
        FROM player_state_snapshots
        WHERE team_id IS NOT NULL AND observed_at IS NOT NULL
        ORDER BY observed_at
    ''').fetchall()
    av_rows=0
    for r in states:
        pid=str(r['player_uuid']); season=str(r['season']); tid=team_key(season,r['team_id'])
        status=STATUS.get(str(r['status_code'] or '').lower(),'unknown')
        chance=r['chance_this_round']
        before=con.total_changes
        con.execute('''INSERT OR IGNORE INTO player_availability_v2
            (external_player_id,team_external_id,observed_at,status,chance_of_playing,reason,source_name,payload_path)
            VALUES (?,?,?,?,?,?,?,?)''',(
                pid,tid,str(r['observed_at']),status,chance,r['news_text'],a.source_name,'player_state_snapshots'))
        if con.total_changes>before: av_rows += 1

    con.commit()
    print({
        'registration_source_rows':len(regs),
        'registration_v2_inserted':reg_rows,
        'synthetic_left_events_attempted':left_rows,
        'availability_source_rows':len(states),
        'availability_v2_inserted':av_rows,
        'identity_policy':'external_player_id=player_uuid; team_external_id=season:team_id',
    })

if __name__=='__main__': main()
