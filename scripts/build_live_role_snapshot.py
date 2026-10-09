#!/usr/bin/env python3
"""Cross-season *evidence-backed* q/H, optionally coherent XI.

Uses the FROZEN RoleHistory, classify_lineup and xi_assignment implementation.
No handcrafted player role tags and no lineup inference from generic FPL positions.

2025/26 confirmed PL lineups are legitimate HISTORICAL priors only. Without
2026/27 confirmed tactical lineup source, they are NEVER relabelled as current.
FPL player's stable 'code' and team's stable 'code' establish identity; never
join seasons by per-season FPL element ID or fuzzy player name.
"""
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.role_history import RoleHistory
from fpl_v1_1_model.role_classifier import classify_lineup, ROLES

RAW_PRIOR=ROOT/'data_v1_1/raw/fpl-core-2025-26'
RAW_CURRENT=ROOT/'data_v1_1/raw/fpl-core-2026-27'
STATS_PRIOR=ROOT/'data_v1_1/raw/all-competitions-2025-26'
IDENT_PRIOR=ROOT/'data_v1_1/derived/mm_v2_ratings/identity_source/data/2025-2026/players.csv'
LIVE_OFFICIAL=ROOT/'data_v1_1/derived/fpl_schedule_knowledge/live/latest.json'
BRIDGE_DATA=ROOT/'model/base_data.json'
OUT=ROOT/'app/role-data.js'

def rows(path):
    if not path.is_file():return []
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def number(value,default=None):
    try:return float(value)
    except (TypeError,ValueError):return default

def is_true(value):
    return str(value).lower() in ('true','yes','1')

def utc(value):
    if not value:return None
    try:
        t=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)
    except ValueError:return None

def evidence_from_directory(history,raw_root,stats_root,code_by_historical_id,cutoff,source):
    """Only confirmed, completed matches strictly BEFORE observed time."""
    stats_by_key={}
    for folder in sorted(raw_root.glob('GW*')):
        p=(stats_root/folder.name/'playermatchstats.csv') if stats_root else None
        for row in rows(p) if p else []:
            key=(row.get('match_id'),row.get('player_id'))
            mins=number(row.get('minutes_played'))
            if mins is not None and mins>=0:
                stats_by_key[key]=mins
    games=[]; missing_min=0
    for folder in sorted(raw_root.glob('GW*'),key=lambda x:int(x.name[2:]) if x.name[2:].isdigit() else 100):
        fixture={x['match_id']:x for x in rows(folder/'fixtures.csv') if x.get('match_id')}
        groups=defaultdict(list)
        averages={(x.get('match_id'),x.get('team_side'),x.get('player_id')):x
                  for x in rows(folder/'average_positions.csv')}
        for line in rows(folder/'lineups.csv'):
            if line.get('match_id') and is_true(line.get('is_starting')):
                groups[(line['match_id'],line.get('team_side'))].append(line)
        for (mid,side),lineup in groups.items():
            fixture_row=fixture.get(mid)
            if not fixture_row or not is_true(fixture_row.get('finished')) or len(lineup)!=11:
                continue
            ko=utc(fixture_row.get('kickoff_time'))
            if not ko or ko+timedelta(hours=4)>=cutoff:
                continue
            team_code=number(lineup[0].get('team_code'))
            if team_code is None or any(number(p.get('team_code'))!=team_code for p in lineup):
                continue
            if not lineup[0].get('formation') or not all(p.get('lineup_status')=='confirmed' for p in lineup):
                continue
            lineup_rows=[]
            for j,p in enumerate(lineup,1):
                ext_id=p.get('player_id')
                stable=code_by_historical_id.get(str(ext_id))
                if not stable:break
                avg=averages.get((mid,side,ext_id),{})
                lineup_rows.append({
                    'player_uuid':str(stable),'slot':j,'position':p.get('position'),
                    'x':avg.get('x'),'y':avg.get('y'),'player_id':ext_id})
            if len(lineup_rows)!=11:continue
            games.append((ko,mid,int(team_code),lineup[0]['formation'],lineup_rows,folder.name,source))
    for ko,mid,team,formation,lineup,gw,season in sorted(games,key=lambda x:(x[0],x[1],x[2])):
        prior,_,_=history.state(team,ko)
        try:
            classified=classify_lineup(formation,lineup,{},prior)
        except (ValueError,TypeError,IndexError,KeyError,AssertionError):
            continue
        players=[]
        for p in lineup:
            rec=classified.get(str(p['player_uuid'])) or {}
            role=rec.get('final_role')
            minutes=stats_by_key.get((mid,p['player_id']))
            if minutes is None:
                # Never invent 90 minutes from the fact a player started.
                missing_min+=1
                continue
            players.append({'player_uuid':p['player_uuid'],'role':role,'started':True,
                            'minutes':minutes,'disagreement':rec.get('disagreement',False)})
        if len(players)<9:continue
        history.add_game(team,(ko+timedelta(hours=4)).isoformat(),mid,players,
                         importance=1.0,competition='PL')
    return {'source':season,'confirmed_teams_games':sum(len(v) for v in history.games.values()),
            'missing_actual_minutes':missing_min}

def build(official,bridge,raw_prior=RAW_PRIOR,stats_prior=STATS_PRIOR,
          raw_current=RAW_CURRENT,*, cutoff=None):
    cutoff=cutoff or utc(official.get('observed_at_utc'))
    if cutoff is None: raise ValueError('No official observed_at_utc timestamp')
    if not official.get('teams') or not official.get('players'):
        raise ValueError('Official FPL snapshot has no stable player/team identifiers')
    prior_ids={str(p.get('player_id')):str(p.get('player_code')) for p in rows(IDENT_PRIOR)
               if p.get('player_id') and p.get('player_code')}
    if not prior_ids:raise ValueError('No 2025/26 stable player identity mapping')
    current_codes={str(p.get('id')):str(p.get('player_code')) for p in official['players']
                   if p.get('id') and p.get('player_code')}
    team_codes={int(t['id']):int(t['code']) for t in official['teams']
                if t.get('id') is not None and t.get('code') is not None}
    hist=RoleHistory()
    prior_report=evidence_from_directory(hist,raw_prior,stats_prior,prior_ids,cutoff,'2025/26')
    prior_games=sum(len(x) for x in hist.games.values())
    current_report={'source':'2026/27','confirmed_teams_games':0}
    current_stats=ROOT/'data_v1_1/raw/all-competitions-2026-27'
    if raw_current.is_dir():
        current_report=evidence_from_directory(hist,raw_current,current_stats,current_codes,cutoff,'2026/27')
    current_games=sum(len(x) for x in hist.games.values())-prior_games
    history_state={};last_team={}
    for team in sorted(hist.games):
        state,caps,games=hist.state(team,cutoff.isoformat())
        history_state[team]=state
        for game in games:
            for player in game['players']:
                if player.get('started'):
                    last_team[str(player['player_uuid'])]=team
    # q is transferable as a role *prior*, but H is NOT transferable across clubs.
    historic_q={}
    for team,state in history_state.items():
        for stable,values in state.items():
            if stable not in historic_q or values['evidence']>historic_q[stable]['evidence']:
                historic_q[stable]=values
    output=[]
    for player in official['players']:
        code=player.get('player_code'); tid=player.get('team_id')
        if code is None or tid is None:continue
        stable=str(code);current_team=team_codes.get(int(tid))
        same=history_state.get(current_team,{}).get(stable)
        old=historic_q.get(stable)
        evidence=same or old
        if not evidence:status='missing_observed_role';q={};H={}
        elif same:
            q=evidence['q'];H=evidence['H']
            status='current_season_confirmed' if current_games>0 and any(
               stable==str(p['player_uuid']) for g in hist.games.get(current_team,[])
               if str(g.get('fixture','')).startswith('26-27-') for p in g['players']
            ) else 'prior_season_same_club'
        else:
            q=evidence['q'];H={};status='prior_season_different_club'
        ranks=sorted(((role,val) for role,val in q.items() if val>=0.05),
                     key=lambda x:(-x[1],x[0]))
        output.append({
            'id':int(player['id']),'player_code':int(code),'team_id':int(tid),
            'team_code':current_team,'name':player.get('name'),
            'primary_role':ranks[0][0] if ranks else None,
            'q':{k:round(float(v),5) for k,v in q.items() if v>=0.001},
            'H':{k:round(float(v),5) for k,v in H.items() if v>=0.0001},
            'evidence':round(float(evidence['evidence']),3) if evidence else 0,
            'role_source':status
        })
    return {
        'schema_version':1,'observed_at_utc':official.get('observed_at_utc'),
        'season':official.get('season'),'model':'locked_role_history_prior_bridge',
        'current_tactical_lineups_found':current_games,
        'historical_tactical_lineups_found':prior_games,
        'current_xi_certified':False,
        'warnings':[
          'Role q/H derive from confirmed historical formations. Current 2026/27 role evidence only counts if formation/lineups/minutes are source-provided.',
          'Last-season roles are historical priors, NOT verified current tactical positions.',
          'A player transferred to another club retains prior q, but historical H is discarded.',
          'No current 2026/27 tactical XI is asserted without official current-season confirmed role evidence and fresh current P(start).'
        ],
        'source_report':{'prior':prior_report,'current':current_report},
        'players':output,'expected_lineups':[]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--official',default=str(LIVE_OFFICIAL))
    p.add_argument('--out',default=str(OUT))
    a=p.parse_args()
    official=json.loads(Path(a.official).read_text(encoding='utf8'))
    bridge=json.loads(BRIDGE_DATA.read_text(encoding='utf8'))
    result=build(official,bridge)
    dst=Path(a.out);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text('window.FPL_ROLE_DATA='+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(json.dumps({'historical_teams_games':result['historical_tactical_lineups_found'],
      'current_teams_games':result['current_tactical_lineups_found'],
      'players':len(result['players']),
      'with_q':sum(bool(x['q']) for x in result['players']),
      'with_H':sum(bool(x['H']) for x in result['players']),
      'saved':str(dst)}))

if __name__=='__main__':main()
