#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, sqlite3
from collections import defaultdict
from pathlib import Path


def season_from_team(t):
    if not t or ':' not in t:
        return None
    return t.split(':',1)[0]


def audit_integrity(con):
    reg = con.execute("""
      SELECT external_player_id, team_external_id, observed_at, registration_status, source_name
      FROM player_registration_v2 ORDER BY observed_at, external_player_id, team_external_id
    """).fetchall()
    by_season_times=defaultdict(set)
    for p,t,obs,status,src in reg:
        s=season_from_team(t)
        if s: by_season_times[s].add(obs)
    # At each registration event time, carry forward latest state per player/team.
    multi=[]
    for s,times in sorted(by_season_times.items()):
        state={}
        rows=[r for r in reg if season_from_team(r[1])==s]
        idx=0
        rows=sorted(rows,key=lambda r:(r[2],r[0],r[1]))
        for obs in sorted(times):
            while idx<len(rows) and rows[idx][2] <= obs:
                p,t,o,status,src=rows[idx]
                state[(p,t)] = status
                idx += 1
            active=defaultdict(list)
            for (p,t),status in state.items():
                if status=='registered': active[p].append(t)
            for p,teams in active.items():
                if len(teams)>1:
                    multi.append({'season':s,'observed_at':obs,'external_player_id':p,'active_teams':';'.join(sorted(teams))})
    # Every true cutoff availability row should have an exact matching registered row.
    missing_exact=con.execute("""
      SELECT COUNT(*)
      FROM player_availability_v2 a
      LEFT JOIN player_registration_v2 r
        ON r.external_player_id=a.external_player_id
       AND r.team_external_id=a.team_external_id
       AND r.observed_at=a.observed_at
       AND r.registration_status='registered'
       AND r.source_name='fpl_cutoff_state_sync'
      WHERE a.source_name='fpl_cutoff_state_sync' AND r.external_player_id IS NULL
    """).fetchone()[0]
    bad_player_ids=con.execute("""
      SELECT COUNT(*) FROM (
        SELECT external_player_id FROM player_registration_v2
        UNION ALL SELECT external_player_id FROM player_availability_v2
      ) x LEFT JOIN players p ON p.player_uuid=x.external_player_id
      WHERE p.player_uuid IS NULL
    """).fetchone()[0]
    bad_team_format=con.execute("""
      SELECT COUNT(*) FROM (
        SELECT team_external_id t FROM player_registration_v2
        UNION ALL SELECT team_external_id t FROM player_availability_v2 WHERE team_external_id IS NOT NULL
      ) WHERE t NOT LIKE '____-__:_%'
    """).fetchone()[0]
    return {
      'registration_rows': con.execute('SELECT COUNT(*) FROM player_registration_v2').fetchone()[0],
      'availability_rows': con.execute('SELECT COUNT(*) FROM player_availability_v2').fetchone()[0],
      'multi_active_registration_cases': len(multi),
      'availability_without_exact_registered_row': missing_exact,
      'unknown_stable_player_ids': bad_player_ids,
      'bad_season_safe_team_id_format': bad_team_format,
      'multi_active_examples': multi[:25],
    }, multi


def availability_calibration_2023(con):
    # The 38 source snapshots are chronological GW1..GW38 deadlines.
    times=[r[0] for r in con.execute("""
      SELECT DISTINCT observed_at FROM player_state_snapshots
      WHERE season='2023-24' ORDER BY observed_at
    """)]
    gw_by_obs={obs:i+1 for i,obs in enumerate(times)}
    actual={}
    for p,gw,st,mins in con.execute("""
      SELECT player_uuid, gw, MAX(started), SUM(minutes)
      FROM player_fixture_observations
      WHERE season='2023-24'
      GROUP BY player_uuid, gw
    """):
        actual[(p,int(gw))]=(int(st or 0),float(mins or 0))
    raw=[]
    for p,status,chance,obs in con.execute("""
      SELECT player_uuid, status_code, chance_this_round, observed_at
      FROM player_state_snapshots WHERE season='2023-24'
    """):
        gw=gw_by_obs.get(obs)
        if gw is None: continue
        st,mins=actual.get((p,gw),(0,0.0))
        raw.append((status or 'NULL', chance, st, mins>0))
    def agg(keyfn):
        d=defaultdict(lambda:[0,0,0])
        for row in raw:
            k=keyfn(row); d[k][0]+=1; d[k][1]+=row[2]; d[k][2]+=int(row[3])
        out=[]
        for k,(n,starts,plays) in sorted(d.items(), key=lambda kv:str(kv[0])):
            out.append({'group':str(k),'n':n,'start_rate':starts/n if n else None,'play_rate':plays/n if n else None})
        return out
    status=agg(lambda r:r[0])
    doubt=agg(lambda r:(r[0],r[1]) if r[0]=='d' else None)
    doubt=[x for x in doubt if x['group']!='None']
    available_chance=agg(lambda r:(r[0],r[1]) if r[0]=='a' else None)
    available_chance=[x for x in available_chance if x['group']!='None']
    return {'n_snapshots':len(raw),'status':status,'doubtful_by_chance':doubt,'available_by_chance':available_chance}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(args.db)
    integrity,multi=audit_integrity(con)
    calib=availability_calibration_2023(con)
    con.close()
    (out/'registration_availability_integrity.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')
    (out/'availability_calibration_2023_24.json').write_text(json.dumps(calib,indent=2),encoding='utf-8')
    for name,rows in [('availability_status_2023_24.csv',calib['status']),('availability_doubtful_chance_2023_24.csv',calib['doubtful_by_chance']),('availability_available_chance_2023_24.csv',calib['available_by_chance'])]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['group','n','start_rate','play_rate']); w.writeheader(); w.writerows(rows)
    if multi:
        with (out/'multi_active_registration_cases.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=multi[0].keys()); w.writeheader(); w.writerows(multi)
    print(json.dumps({'integrity':integrity,'availability_calibration':calib},indent=2))

if __name__=='__main__': main()
