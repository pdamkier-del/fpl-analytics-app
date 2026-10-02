#!/usr/bin/env python3
"""Build deadline-safe role-share q and hierarchy H snapshots from multi-comp data.

Writes append-only CSV snapshots; does not overwrite Historical Core.
"""
import argparse, sqlite3, math
from collections import defaultdict
from pathlib import Path
import pandas as pd

ROLES=['GK','RB','CB','LB','DM','CM','AM','HW','VW','ST']

def w(lag,half): return 2**(-max(0,float(lag))/half)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--out',default='data_v1_1/features/pstart_v2_role_state.csv')
    ap.add_argument('--role-half-life',type=float,default=10.0); ap.add_argument('--hier-half-life',type=float,default=10.0)
    a=ap.parse_args(); con=sqlite3.connect(a.db)
    q='''select m.source_match_id,m.kickoff_at,m.competition,m.round_strength,
                p.external_player_id,p.player_name,p.team_external_id,p.started,p.minutes,
                p.in_matchday_squad,p.role
         from club_matches_v2 m join player_match_roles_v2 p using(source_match_id)
         order by m.kickoff_at,m.source_match_id,p.team_external_id,p.external_player_id'''
    df=pd.read_sql_query(q,con)
    if df.empty:
        print('no multi-competition rows yet'); return
    df['kickoff_at']=pd.to_datetime(df.kickoff_at,utc=True,errors='coerce')
    out=[]
    for (tid,pid),g in df.groupby(['team_external_id','external_player_id'],dropna=False):
        g=g.sort_values('kickoff_at').reset_index(drop=True)
        role_mass=defaultdict(lambda:0.20) # mild symmetric smoothing
        pos=neg=1.0
        prev=None
        for row in g.itertuples(index=False):
            if prev is not None:
                days=max(0.,(row.kickoff_at-prev).total_seconds()/86400.)
                # convert approximate weekly half-life into elapsed-time decay
                decay=2**(-(days/7.0)/a.hier_half_life)
                pos*=decay; neg*=decay
                for r in list(role_mass): role_mass[r]*=2**(-(days/7.0)/a.role_half_life)
            imp=0.5 # replaced at forecast build time when opponent/active-competition state is available
            iw=0.25+0.75*imp
            if row.in_matchday_squad is not False and not pd.isna(row.in_matchday_squad):
                ev=1.0 if int(row.started) else 0.30*max(0,min(1,float(row.minutes)/90.0))
                pos+=iw*ev; neg+=iw*(1-ev)
            if row.role in ROLES:
                role_mass[row.role]+=max(0,float(row.minutes))/90.0
            den=sum(role_mass.values())
            H=pos/(pos+neg)
            for role in ROLES:
                out.append({'asof':row.kickoff_at.isoformat(),'team_external_id':tid,'external_player_id':pid,
                            'player_name':row.player_name,'role':role,'q_role':role_mass[role]/den,'hierarchy':H})
            prev=row.kickoff_at
    o=Path(a.out); o.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(out).to_csv(o,index=False); print('wrote',o,len(out))
if __name__=='__main__': main()
