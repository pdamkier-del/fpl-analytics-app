#!/usr/bin/env python3
"""Verified archived event bridges for the unchanged historical penalty/BPS code.

A sparse numeric field is zero only when the team's measured total equals
all explicitly reported player values. Missing evidence is quarantined.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,gzip,hashlib,json,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from collect_current_locked_inputs import club
from audit_current_locked_inputs import readjl,csvgz,dump
from live_provider_stat_evidence import passing_percentage,manifest_details
import run_bps_background_experiment as frozen_bps
WORK=ROOT/'work/live-final-model';BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
CORE_SHA='561bd00f699ec25ce095a0245e6ad52300ebdc01'
CORE=ROOT/'data_v1_1/raw/verified-core-2026-27'/CORE_SHA
FIELDS=['minutes_played','accurate_crosses','blocks','clearances','interceptions','recoveries',
        'tackles_won','chances_created','successful_dribbles','was_fouled','shots_on_target',
        'accurate_passes','accurate_passes_percent','big_chances_missed','fouls_committed',
        'offsides','total_shots','dispossessed']
ALIASES={'blocks':'shot_blocks','successful_dribbles':'dribbles_succeeded',
         'shots_on_target':'ShotsOnTarget','big_chances_missed':'big_chance_missed_title',
         'fouls_committed':'fouls','offsides':'Offsides'}
TEAM_KEYS={'accurate_crosses':'accurate_crosses','blocks':'shot_blocks',
           'successful_dribbles':'dribbles_succeeded','shots_on_target':'ShotsOnTarget',
           'big_chances_missed':'big_chance_missed_title','fouls_committed':'fouls','was_fouled':'fouls',
           'offsides':'Offsides','total_shots':'total_shots',
           'clearances':'clearances','interceptions':'interceptions','recoveries':'recoveries'}


def verified_sparse_zeros(values,total):
    """Conservation proof; total must be observed and nonnegative counts."""
    if total is None:return None
    if any(v is not None and (not np.isfinite(v) or v<0) for v in values):raise ValueError('Invalid measured count')
    measured=sum(v for v in values if v is not None)
    if not np.isfinite(total) or total<0:return None
    if abs(measured-float(total))>1e-8:return None
    return [0. if v is None else float(v) for v in values]


def archive_details():
    return manifest_details(ROOT,json.loads((WORK/'source_manifest.json').read_text()))


def build():
    bootstrap=json.loads((WORK/'bootstrap.json').read_text());fixtures=json.loads((WORK/'fixtures.json').read_text())
    identity=json.loads((WORK/'current_identity.json').read_text())
    idmap={int(p['fpl_element']):p['player_uuid'] for p in identity}
    codeids={int(p['code']):int(p['id']) for p in bootstrap['elements']}
    teams={club(t['name']):int(t['id']) for t in bootstrap['teams']}
    cohort=pd.read_csv(WORK/'mm_frozen_diagnostic_six_gw.csv.gz')
    cut=pd.Timestamp(cohort.cutoff.iloc[0]);origin=int(cohort.gw.iloc[0])
    games=readjl(WORK/'match_actuals.jsonl.gz');games={str(g['provider_match_id']):g for g in games}
    eventmap={(str(r['match_id']).rsplit('-',1)[-1],str(r['provider_player_id'])):r for r in readjl(WORK/'player_match_events.jsonl.gz')}
    detail=archive_details();attempts=[];sides=[];all_attempts=[];unresolved=[];external=[];proof=[];rawbps=[];quarantine=[];matchmaps=[]
    corestats={};coreplayers={}
    for folder in sorted(CORE.glob('GW*')):
        players=pd.read_csv(folder/'players.csv');stats=pd.read_csv(folder/'playermatchstats.csv');fx=pd.read_csv(folder/'fixtures.csv')
        for p in players.itertuples():
            fid=codeids.get(int(p.player_code))
            if fid is not None and fid==int(p.player_id):coreplayers[(int(folder.name[2:]),fid)]=int(p.player_code)
        for f in fx.itertuples():
            if str(f.match_url).rsplit('#',1)[-1].isdigit():
                mid=str(f.match_url).rsplit('#',1)[-1]
                for r in stats[stats.match_id==f.match_id].itertuples():corestats[(mid,int(r.player_id))]=r._asdict()
    for mid,(d,path) in sorted(detail.items()):
        game=games.get(mid)
        if game is None or pd.Timestamp(game['available_at'])>=cut:continue
        gen=d['general'];is_pl=game['tournament']=='prem'
        gw=int(game['gameweek']) if is_pl else None
        # Cup events retained separately; the original penalty model is PL-only.
        lineup=d['content'].get('lineup') or {};ps=d['content'].get('playerStats') or {}
        shots=d['content'].get('shotmap') or {};shots=shots.get('shots',[]) if isinstance(shots,dict) else shots
        by_side={};provider_side={}
        for side in ('home','away'):
            team=teams.get(club(gen[side+'Team']['name']))
            if team is None:continue
            block=lineup.get(side+'Team') or {}
            ids={str(p['id']) for kind in ('starters','subs') for p in block.get(kind,[])}
            by_side[side]=ids
            for pid in ids:provider_side[pid]=(side,team)
        seen=set();eventcount=Counter();scored=Counter();missed=Counter()
        for shot in shots:
            if shot.get('situation')!='Penalty' or shot.get('period')=='PenaltyShootout':continue
            sid=shot.get('id')
            if sid is None or sid in seen:raise ValueError('Missing/duplicate penalty shot ID')
            seen.add(sid);pid=str(shot.get('playerId'));r=eventmap.get((mid,pid));pair=provider_side.get(pid)
            typ=shot.get('eventType')
            if typ not in ('Goal','Post','AttemptSaved','Miss'):unresolved.append(dict(mid=mid,shot=sid,reason='Unknown explicit outcome'));continue
            team=teams.get(club(next((gen[k+'Team']['name'] for k in ('home','away') if int(gen[k+'Team']['id'])==int(shot['teamId'])),'')))
            if team is None and not is_pl:
                external.append(dict(mid=mid,shot=sid,provider_player_id=pid,provider_team_id=shot['teamId'],player_name=shot.get('playerName'),reason='Opponent outside Premier League identity namespace'))
                continue
            if not r or not pair or int(r['team_id'])!=team:
                unresolved.append(dict(mid=mid,shot=sid,reason='No exact provider-player-team mapping'));continue
            row=dict(player_uuid=r['player_uuid'],player_id=int(r['player_id']),match_id=game['match_id'],
                     provider_match_id=mid,provider_player_id=pid,shot_id=sid,team_code=team,gw=gw,
                     attempts=1,penalties_scored=int(typ=='Goal'),penalties_missed=int(typ!='Goal'),
                     event_type=typ,competition=game['tournament'],available_at=game['available_at'],
                     source_path=str(path.relative_to(ROOT)))
            all_attempts.append(row)
            if is_pl:attempts.append(row);eventcount[team]+=1;scored[team]+=int(typ=='Goal');missed[team]+=int(typ!='Goal')
        if not is_pl:continue
        if gw>=origin:raise ValueError('Future GW entered historical source')
        h=teams[club(gen['homeTeam']['name'])];a=teams[club(gen['awayTeam']['name'])]
        ko=pd.Timestamp(gen['matchTimeUTCDate'])
        matches=[f for f in fixtures if int(f['team_h'])==h and int(f['team_a'])==a and pd.Timestamp(f.get('kickoff_time'))==ko]
        if len(matches)!=1:raise ValueError('Nonexact PL fixture identity')
        f=matches[0]
        if int(f['event'])!=gw:raise ValueError('Historical GW mismatch')
        for team,opp in ((h,a),(a,h)):
            sides.append(dict(gw=gw,match_id=game['match_id'],fixture_uuid=f"historical-2026-27-fpl-{f['id']}",
                              team_code=team,opp_code=opp,attempts=eventcount[team],scored=scored[team],
                              missed=missed[team],available_at=game['available_at'],source_path=str(path.relative_to(ROOT))))
        teamstats={}
        for sec in ((d['content'].get('stats') or {}).get('Periods',{}).get('All',{}).get('stats',[])):
            for stat in sec.get('stats',[]):
                vals=stat.get('rawStats') or []
                if len(vals)==2:teamstats[stat.get('key')]=[v.get('value') if isinstance(v,dict) else None for v in vals]
        observed_shots=teamstats.get('total_shots')
        if observed_shots is None:raise ValueError('Cannot verify shotmap completeness')
        for side_index,side_key in enumerate(('home','away')):
            count=sum(s.get('teamId')==gen[side_key+'Team']['id'] and not s.get('isOwnGoal') for s in shots)
            if count!=observed_shots[side_index]:raise ValueError('Incomplete team shotmap')
        for side,ids in by_side.items():
            pos=[];sid=0 if side=='home' else 1;team=h if sid==0 else a
            for pid in ids:
                obj=ps.get(pid) or {};values={v.get('key',k):v.get('stat',{}) for sec in obj.get('stats',[]) for k,v in sec.get('stats',{}).items()}
                mins=(values.get('minutes_played') or {}).get('value')
                if mins is None or float(mins)<=0:continue
                mapped=eventmap.get((mid,pid));fid=int(mapped['player_id']) if mapped else None
                observed={k:(values.get(ALIASES.get(k,k)) or {}).get('value') for k in FIELDS}
                observed['accurate_passes_percent']=passing_percentage(values.get('accurate_passes') or {})
                # tackles_won has verified canonical meaning; raw Tackles is NOT an alias.
                canonical=corestats.get((mid,fid),{})
                if fid is not None and (gw,fid) in coreplayers:
                    observed['tackles_won']=canonical.get('tackles_won')
                    if pd.isna(observed['tackles_won']):observed['tackles_won']=None
                pos.append(dict(pid=pid,fid=fid,mapped=mapped,values=observed))
            # Verify missing counts against complete team evidence, using ALL
            # provider players (including those not on the current FPL roster).
            for field,key in TEAM_KEYS.items():
                vals=[x['values'][field] for x in pos]
                if not any(v is None for v in vals):continue
                total=teamstats.get(key,[None,None])[1-sid if field=='was_fouled' else sid]
                done=verified_sparse_zeros(vals,total)
                if done is not None:
                    for x,v in zip(pos,done):
                        if x['values'][field] is None:proof.append(dict(mid=mid,team_id=team,provider_player_id=x['pid'],field=field,team_total=total,reported_player_sum=sum(z for z in vals if z is not None),value=v))
                        x['values'][field]=v
            for x in pos:
                if not x['mapped']:continue
                missing=[k for k,v in x['values'].items() if v is None or pd.isna(v)]
                if missing:quarantine.append(dict(mid=mid,player_id=x['fid'],missing=missing));continue
                rawbps.append(dict(player_id=x['fid'],match_id=game['match_id'],**x['values']))
                matchmaps.append(dict(match_id=game['match_id'],fixture_uuid=f"historical-2026-27-fpl-{f['id']}",kickoff_time=game['kickoff_time']))
    # Only verified non-null rows reach the original background computation.
    csvgz(BASE/'verified_penalty_all_competitions_events.csv.gz',pd.DataFrame(all_attempts))
    csvgz(BASE/'verified_penalty_attempts.csv.gz',pd.DataFrame(attempts))
    csvgz(BASE/'verified_penalty_team_sides.csv.gz',pd.DataFrame(sides))
    dump(WORK/'live_penalty_identity_audit.json',dict(all_competitions_mapped_attempts=len(all_attempts),pl_attempts=len(attempts),pl_sides=len(sides),unresolved=unresolved,opponent_events_without_FPL_identity=external,live_certified=False))
    if rawbps:
        stats=pd.DataFrame(rawbps);fx=pd.DataFrame(matchmaps).drop_duplicates();fxpath=WORK/'bps_exact_fixture_mapping.csv';fx.to_csv(fxpath,index=False)
        originals=(frozen_bps.read_all,frozen_bps.player_id_map,frozen_bps.CLASSIFIED)
        try:
            frozen_bps.read_all=lambda name:stats if name=='playermatchstats' else fx
            frozen_bps.player_id_map=lambda:idmap
            frozen_bps.CLASSIFIED=fxpath
            ledger=frozen_bps.actual_background_ledger()
        finally:frozen_bps.read_all,frozen_bps.player_id_map,frozen_bps.CLASSIFIED=originals
        known={g['match_id']:g['available_at'] for g in games.values()}
        ledger['available_at']=ledger.match_id.map(known)
        csvgz(BASE/'verified_bps_action_ledger.csv.gz',ledger)
        csvgz(BASE/'verified_bps_raw_actions.csv.gz',stats)
    dump(WORK/'live_bps_source_audit.json',dict(verified_player_match_rows=len(rawbps),quarantined_rows=len(quarantine),missing_fields=dict(Counter(k for r in quarantine for k in r['missing'])),quarantine=quarantine,source_core_commit=CORE_SHA,canonical_zero_imputation=False,zero_conservation_proofs=len(proof),original_function='run_bps_background_experiment.actual_background_ledger',live_certified=False))
    dump(WORK/'live_bps_zero_evidence.json',proof)
    print(json.dumps(dict(penalties=len(attempts),all_competition_penalties=len(all_attempts),sides=len(sides),bps_rows=len(rawbps),quarantined=len(quarantine),missing_fields=dict(Counter(k for r in quarantine for k in r['missing'])))),flush=True)
    if unresolved:raise ValueError('Unresolved explicit penalty events: '+str(unresolved))
    eligible=[f for f in fixtures if f.get('event') is not None and int(f['event'])<origin and f.get('kickoff_time')
              and (f.get('finished') or (f.get('finished_provisional') and f.get('started') and f.get('minutes')==90))
              and pd.Timestamp(f['kickoff_time'])+pd.Timedelta(hours=4)<cut]
    expected={(int(f['event']),f"historical-2026-27-fpl-{f['id']}",int(team)) for f in eligible for team in (f['team_h'],f['team_a'])}
    observed={(int(s['gw']),s['fixture_uuid'],int(s['team_code'])) for s in sides}
    if observed!=expected or len(sides)!=len(expected):
        raise ValueError('Incomplete pre-cutoff PL penalty side coverage; missing='+str(expected-observed)+'; extra='+str(observed-expected))
if __name__=='__main__':build()
