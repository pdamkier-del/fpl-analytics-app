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
from fpl_v1_1_model.role_classifier import classify_lineup, ROLES, template, valid_coordinate

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
        prior,_,_=history.state(team,ko.isoformat())
        try:
            patterns=template(formation)
            geometry={}
            # Average-position coordinates become evidence only AFTER
            # the match was completed. Never use these for future target matches.
            if patterns and len(lineup)==11:
                offset=1
                for roles in patterns:
                    line=lineup[offset:offset+len(roles)]
                    if len(line)==len(roles) and all(valid_coordinate(p) for p in line):
                        for p,role in zip(sorted(line,key=lambda x:(float(x['y']),x['player_uuid'])),roles):
                            geometry[p['player_uuid']]=role
                    offset+=len(roles)
            classified=classify_lineup(formation,lineup,geometry,prior)
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
        # Observed shape is recorded as past-game evidence, never current XI.
        game=history.games[int(team)][-1]
        game['formation']=formation
        game['season']=source
        game['kickoff']=ko.isoformat()
    return {'source':source,'confirmed_teams_games':sum(len(v) for v in history.games.values()),
            'missing_actual_minutes':missing_min}

def historical_formations(history, teams, *, current_season='2026/27', half_life=4.0, recent_limit=10):
    """Latest observed formations from confirmed lineup evidence, per club.

    This is a *prior*, not a current-formation forecast. It tracks changes of
    shape with exponential recency, but cannot detect a coaching change in a
    season for which confirmed lineups are unavailable.
    """
    result=[]
    for team in teams:
        code=team.get('code')
        if code is None:continue
        games=[g for g in history.games.get(int(code),[])
               if g.get('formation') and g.get('kickoff')]
        if not games:continue
        games=sorted(games,key=lambda g:(g['kickoff'],g['fixture']))[-recent_limit:]
        mass=defaultdict(float);season_mass=defaultdict(float)
        for lag,g in enumerate(reversed(games)):
            weight=2**(-lag/half_life)
            mass[g['formation']]+=weight
            if g.get('season')=='2026/27':season_mass[g['formation']]+=weight
        total=sum(mass.values())
        ordered=sorted(mass.items(),key=lambda x:(-x[1],x[0]))
        latest=games[-1]
        result.append({
            'team_id':int(team['id']),'club':team.get('short_name'),
            'observed_latest_formation':latest['formation'],
            'observed_latest_at':latest['kickoff'],
            'latest_observed_season':latest.get('season'),
            'recent_observations':len(games),
            'formations':[{'formation':formation,
                           'weighted_share':round(value/total,5),
                           'current_season_games':sum(
                               int(x['formation']==formation and x.get('season')=='2026/27')
                               for x in games),
                           'observed_games':sum(int(x['formation']==formation) for x in games)}
                          for formation,value in ordered],
            'confidence':'current_observed' if latest.get('season')=='2026/27'
                else 'historical_prior_only'
        })
    return result


def generate_current_xi(role_data,official,bridge,*,asof,optimizer=None):
    """Use the FROZEN coherent role-slot optimizer only when live inputs certify it.

    Without an up-to-date locked P(start) and actual current-season confirmed
    tactical role observations, returning [] is mandatory: no pseudo-XI.
    """
    meta=bridge.get('meta') or {}
    observed=utc(meta.get('updated'))
    gw=meta.get('next_gw')
    try:gw=int(gw)
    except (TypeError,ValueError):return []
    if str(meta.get('model_version'))!='locked_mm_pm_vfinal':return []
    if observed is None or abs((asof-observed).total_seconds())>72*3600:return []
    if gw!=official.get('official_next_gw'):return []
    if role_data.get('current_tactical_lineups_found',0)<1:return []
    if optimizer is None:
        # Use the frozen implementation, not a fallback that invents slots.
        from fpl_v1_1_model.xi_assignment import optimize_best_formation
        optimizer=optimize_best_formation
    by_code={int(p['id']):p for p in role_data.get('players',[])}
    club_short={int(t['id']):t.get('short_name') for t in official.get('teams',[])
                if t.get('id') is not None}
    grouped=defaultdict(list)
    for p in bridge.get('forecasts') or []:
        pid=int(p['id'])
        evidence=by_code.get(pid)
        if not evidence or evidence['role_source']!='current_season_confirmed':continue
        q=evidence.get('q') or {}; H=evidence.get('H') or {}
        if not q or not H:continue
        forecast=next((row for row in p.get('gws',[]) if row.get('gw')==gw),None)
        if forecast is None or not isinstance(forecast.get('pstart'),(int,float)):continue
        if not evidence.get('team_id'):continue
        grouped[int(evidence['team_id'])].append({
            'player_uuid':str(pid),'base_p_start':forecast['pstart'],
            'q':q,'H':H,'evidence':evidence.get('evidence',0),
            'xmins':forecast.get('xmins'),'player':p.get('player')})
    lineups=[]
    for team_id,players in sorted(grouped.items()):
        if len(players)<11:continue
        team_prior=next((x for x in role_data.get('team_formations',[])
                         if x.get('team_id')==team_id),None)
        if not team_prior or team_prior.get('confidence')!='current_observed':
            # Cannot assign today's XI using historical seasons' manager shape.
            continue
        approved={f['formation']:f['weighted_share']
                  for f in team_prior.get('formations',[])
                  if f['current_season_games']>0}
        if not approved:continue
        from math import log
        form_logs={f:log(max(.001,share)) for f,share in approved.items()}
        try:
            chosen=optimizer(players,formations=tuple(approved),
                             formation_log_prior=form_logs)
        except (ValueError,RuntimeError,ImportError):continue
        choices=chosen.get('xi') or []
        if len(choices)!=11:continue
        if any(float(x.q_role)<.08 or float(x.hierarchy)<.01 for x in choices):
            continue
        if len(set(x.player_uuid for x in choices))!=11:continue
        if sum(x.role=='GK' for x in choices)!=1:continue
        club=club_short.get(team_id)
        if not club:continue
        lookup={p['player_uuid']:p for p in players}
        lineups.append({
            'club':club,'gw':gw,'formation':chosen['formation'],
            'role_source':'current_cutoff_verified',
            'players':[{'id':int(x.player_uuid),'role':x.role,
                        'q_role':round(float(x.q_role),4),
                        'hierarchy':round(float(x.hierarchy),4),
                        'pstart':float(x.base_p_start),
                        'xmins':lookup[x.player_uuid].get('xmins')}
                       for x in choices]
        })
    return lineups


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
    formations=historical_formations(hist,official['teams'])
    formation_by_team={int(x['team_id']):x for x in formations}
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
    result={
        'schema_version':1,'observed_at_utc':official.get('observed_at_utc'),
        'season':official.get('season'),'official_next_gw':official.get('official_next_gw'),
        'model':'locked_role_history_prior_bridge',
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
        'team_formations':formations,
        'players':output,'expected_lineups':[]
    }
    result['expected_lineups']=generate_current_xi(result,official,bridge,asof=cutoff)
    result['current_xi_certified']=bool(result['expected_lineups'])
    return result

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
