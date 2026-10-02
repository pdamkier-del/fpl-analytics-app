#!/usr/bin/env python3
"""Backfill all official matches/lineups for selected PL clubs from FotMob.

Unofficial endpoint; raw JSON is cached append-only.  The script is deliberately
rate-limited and resumable. It does not overwrite v1.0/v1.1 historical core.

Usage (on a machine with internet):
  python scripts/v1_1_backfill_fotmob_multicomp.py --from 2025-07-01 --to 2026-06-30 \
      --team-names "Chelsea,Arsenal,..."

The daily match list is used for discovery, then matchDetails provides lineups.
"""
import argparse, datetime as dt, hashlib, json, os, sqlite3, time
from pathlib import Path
import requests

BASE='https://www.fotmob.com/api'
KEEP={'Premier League':'PL','Champions League':'CL','Europa League':'EL','Conference League':'ECL',
      'FA Cup':'FA','EFL Cup':'LC','Carabao Cup':'LC','League Cup':'LC'}

def get_json(url,params,session,retries=4):
    for k in range(retries):
        r=session.get(url,params=params,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
        if r.ok:
            try:return r.json()
            except Exception: pass
        time.sleep(1.5*(k+1))
    raise RuntimeError(f'GET failed {r.status_code}: {r.url}')

def daterange(a,b):
    d=a
    while d<=b:
        yield d; d+=dt.timedelta(days=1)

def find_lineup(payload):
    c=payload.get('content',{}) if isinstance(payload,dict) else {}
    return c.get('lineup') or payload.get('lineup') or {}

def flatten_players(obj):
    """Best-effort parser over known FotMob lineup variants; raw is always cached."""
    out=[]
    def walk(x, team_id=None, started_hint=None):
        if isinstance(x,dict):
            tid=x.get('teamId') or x.get('team_id') or team_id
            st=started_hint
            for key in ('starters','startingXI','startingLineup'):
                if key in x: walk(x[key],tid,True)
            for key in ('bench','substitutes','subs'):
                if key in x: walk(x[key],tid,False)
            # player-like node
            pid=x.get('id') or x.get('playerId')
            name=x.get('name') or x.get('playerName')
            if pid is not None and name and any(k in x for k in ('position','role','minutesPlayed','minutes','shirt','number','rating')):
                pos=x.get('position') or x.get('role') or x.get('positionString')
                mins=x.get('minutesPlayed',x.get('minutes',90 if st else 0))
                try: mins=float(mins or 0)
                except: mins=90.0 if st else 0.0
                started=bool(x.get('isStarter',x.get('starter',st if st is not None else mins>45)))
                coord=x.get('positionCoordinates') or x.get('coordinates') or {}
                out.append({'player_id':str(pid),'name':str(name),'team_id':str(tid) if tid is not None else None,
                            'started':int(started),'minutes':mins,'position':pos,
                            'x':coord.get('x') if isinstance(coord,dict) else None,
                            'y':coord.get('y') if isinstance(coord,dict) else None})
            for k,v in x.items():
                if k not in ('starters','startingXI','startingLineup','bench','substitutes','subs'):
                    if isinstance(v,(dict,list)): walk(v,tid,st)
        elif isinstance(x,list):
            for v in x: walk(v,team_id,started_hint)
    walk(obj)
    uniq={}
    for p in out: uniq[(p['team_id'],p['player_id'])]=p
    return list(uniq.values())

def role_from_position(pos,x=None,y=None):
    s=str(pos or '').upper().replace(' ','')
    aliases={'G':'GK','GK':'GK','GOALKEEPER':'GK','CB':'CB','LCB':'CB','RCB':'CB',
             'LB':'LB','LWB':'LB','RB':'RB','RWB':'RB','DM':'DM','CDM':'DM',
             'CM':'CM','LCM':'CM','RCM':'CM','AM':'AM','CAM':'AM',
             'RW':'HW','RM':'HW','RWF':'HW','LW':'VW','LM':'VW','LWF':'VW',
             'ST':'ST','CF':'ST','FW':'ST','F':'ST'}
    if s in aliases:return aliases[s]
    # conservative coordinate fallback only when provider gives normalized x/y
    try:
        xx=float(x); yy=float(y)
        if xx<20:return 'GK'
        if xx<45:return 'LB' if yy<30 else ('RB' if yy>70 else 'CB')
        if xx<68:return 'DM' if 35<=yy<=65 else ('VW' if yy<35 else 'HW')
        if xx<84:return 'AM' if 30<=yy<=70 else ('VW' if yy<30 else 'HW')
        return 'ST'
    except:return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--from',dest='dfrom',required=True); ap.add_argument('--to',dest='dto',required=True)
    ap.add_argument('--team-names',required=True,help='comma separated exact/substring club names')
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3'); ap.add_argument('--raw-dir',default='data_v1_1/raw/fotmob_multicomp')
    ap.add_argument('--sleep',type=float,default=0.35); a=ap.parse_args()
    teams=[x.strip().lower() for x in a.team_names.split(',') if x.strip()]
    raw=Path(a.raw_dir); raw.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(a.db); sess=requests.Session(); seen=set()
    now=lambda:dt.datetime.now(dt.timezone.utc).isoformat()
    for d in daterange(dt.date.fromisoformat(a.dfrom),dt.date.fromisoformat(a.dto)):
        listing=get_json(BASE+'/matches',{'date':d.strftime('%Y%m%d')},sess)
        for lg in listing.get('leagues',[]):
            comp=KEEP.get(lg.get('name',''))
            if not comp: continue
            for m in lg.get('matches',[]):
                hn=str(m.get('home',{}).get('name','')); an=str(m.get('away',{}).get('name',''))
                if not any(t in hn.lower() or t in an.lower() for t in teams): continue
                mid=str(m.get('id')); 
                if not mid or mid in seen: continue
                seen.add(mid)
                p=raw/f'{mid}.json'
                if p.exists(): detail=json.loads(p.read_text(encoding='utf-8'))
                else:
                    detail=get_json(BASE+'/matchDetails',{'matchId':mid},sess); p.write_text(json.dumps(detail,ensure_ascii=False),encoding='utf-8'); time.sleep(a.sleep)
                gen=detail.get('general',{})
                ko=(m.get('status',{}) or {}).get('utcTime') or gen.get('matchTimeUTC') or d.isoformat()
                stage=m.get('tournamentStage') or gen.get('roundName') or gen.get('round')
                con.execute('''INSERT OR IGNORE INTO club_matches_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (mid, f'{d.year}-{str((d.year+1)%100).zfill(2)}', ko, comp, str(stage) if stage else None, None,
                             hn,an,str(m.get('home',{}).get('id','')),str(m.get('away',{}).get('id','')),'fotmob',str(p),now()))
                for pl in flatten_players(find_lineup(detail)):
                    role=role_from_position(pl['position'],pl['x'],pl['y'])
                    con.execute('''INSERT OR REPLACE INTO player_match_roles_v2
                      (source_match_id,external_player_id,player_name,team_external_id,started,minutes,in_matchday_squad,role,role_x,role_y,source_name,observed_at)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (mid,pl['player_id'],pl['name'],pl['team_id'],pl['started'],pl['minutes'],1,role,pl['x'],pl['y'],'fotmob',now()))
                con.commit()
        print(d,'matches',len(seen))
    print('done',len(seen),'matches')
if __name__=='__main__': main()
