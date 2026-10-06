"""Exact identity/match joins and raw rating extraction; no MM/PM/TS maths."""
from collections import defaultdict
import math
import re
import unicodedata
import pandas as pd


def norm(value):
    text=str(value or '').translate(str.maketrans({'ø':'o','Ø':'O','ł':'l','Ł':'L','đ':'d','Đ':'D'}))
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().casefold()
    return re.sub('[^a-z0-9]','',text)


def unique_choice(choices):
    choices={str(x) for x in choices if pd.notna(x) and str(x).strip()}
    return (next(iter(choices)),'mapped') if len(choices)==1 else (None,'ambiguous' if choices else 'unresolved')


def scalar_stat(value, labels):
    """Read the provider's numeric stat as-is; never standardise or round."""
    labels={norm(x) for x in labels}
    if isinstance(value,dict):
        if norm(value.get('key','')) in labels or norm(value.get('title','')) in labels:
            stat=value.get('stat',value.get('value'))
            if isinstance(stat,dict):stat=stat.get('value')
            if isinstance(stat,(int,float)) and not isinstance(stat,bool):return float(stat)
        for key,item in value.items():
            if norm(key) in labels:
                stat=item
                if isinstance(stat,dict):stat=stat.get('stat',stat.get('value'))
                if isinstance(stat,dict):stat=stat.get('value')
                if isinstance(stat,(int,float)) and not isinstance(stat,bool):return float(stat)
            result=scalar_stat(item,labels)
            if result is not None:return result
    elif isinstance(value,list):
        for item in value:
            result=scalar_stat(item,labels)
            if result is not None:return result
    return None


def extract_fotmob(detail, event, season, competition, team_lookup):
    general=detail.get('general') or {};header=detail.get('header') or {}
    if str(general.get('matchId'))!=str(event['id']):raise ValueError('Provider event ID mismatch')
    if not general.get('finished') or not (header.get('status') or {}).get('finished'):
        return []
    kickoff=pd.to_datetime(general.get('matchTimeUTCDate'),utc=True,errors='raise')
    inventory_ko=pd.to_datetime(event['status']['utcTime'],utc=True,errors='raise')
    if kickoff != inventory_ko:raise ValueError('Provider inventory/detail kickoff mismatch')
    # No original publication clock: six hours after kickoff, rather than during
    # or immediately after 90/120-minute play. Revision timing remains unknown.
    available=kickoff+pd.Timedelta(hours=6)
    content=detail.get('content') or {};lineup=content.get('lineup') or {}
    stats=content.get('playerStats') or {};result=[]
    for side in ['home','away']:
        team=general.get(side+'Team') or {}
        local=team_lookup.get(str(team.get('id')))
        if local is None:continue
        block=lineup.get(side+'Team') or {}
        players={str(p['id']):p for field in ['starters','subs'] for p in block.get(field,[]) if p.get('id') is not None}
        for provider_id,player in players.items():
            statrow=stats.get(provider_id,{})
            if statrow.get('teamId') is not None and str(statrow['teamId'])!=str(team['id']):
                raise ValueError('Provider stat/player team mismatch')
            rating=scalar_stat(statrow,['FotMob rating','rating_title'])
            origin='playerStats.FotMob rating'
            if rating is None:
                rating=(player.get('performance') or {}).get('rating');origin='lineup.performance.rating'
            if rating is None:continue
            if isinstance(rating,bool):raise ValueError('Boolean is not a rating')
            try:rating=float(rating)
            except (TypeError,ValueError):raise ValueError('Non-numeric provider rating')
            minutes=scalar_stat(statrow,['Minutes played','minutes_played'])
            result.append(dict(provider='fotmob',season=season,provider_match_id=str(event['id']),
                provider_player_id=provider_id,provider_opta_id=str(statrow.get('optaId') or ''),
                player_name=statrow.get('name') or player.get('name',''),
                team_id=local.get('team_id'),team_code=local['team_code'],team_name=local['team_name'],
                provider_team_id=str(team['id']),competition=competition,kickoff=kickoff.isoformat(),
                available_at=available.isoformat(),rating=rating,minutes=minutes,
                provider_position_id=player.get('positionId'),rating_origin=origin,
                available_at_policy='kickoff+6h proxy; original publication/revision clock unavailable'))
    return result


def resolve_player(row, provider_ids, opta_ids, match_names):
    """Known provider ID -> known Opta/FPL code -> exact name/team/match."""
    provider_key=(str(row['provider']),str(row['provider_player_id']))
    uid,status=unique_choice(provider_ids.get(provider_key,set()))
    if status!='unresolved':return uid,status,'known_provider_id'
    opta=str(row.get('provider_opta_id') or '')
    uid,status=unique_choice(opta_ids.get(opta,set()))
    if status!='unresolved':return uid,status,'exact_opta_fpl_code'
    key=(str(row.get('match_id') or ''),row.get('team_id'),norm(row.get('player_name')))
    uid,status=unique_choice(match_names.get(key,set()))
    return uid,status,'exact_name_team_match'


def resolve_match(row, registry, known_provider_matches):
    season=str(row['season']);comp=str(row['competition'])
    date=pd.to_datetime(row['kickoff'],utc=True).date().isoformat()
    key=(season,comp,date,int(row['team_code']))
    allowed=registry.get(key,set())
    direct=known_provider_matches.get((row['provider'],str(row['provider_match_id'])),set())
    # Direct IDs are still required to agree with competition, date and club.
    if direct:
        return unique_choice(set(direct)&set(allowed))
    return unique_choice(allowed)


def map_rows(raw,registry,known_matches,provider_ids,opta_ids,names,roles):
    audits=[];mapped=[]
    # Do not bootstrap IDs by order. First collect all exact Opta/FPL evidence;
    # contradictory provider-ID anchors stay ambiguous across every match.
    learned=defaultdict(set)
    for key,values in provider_ids.items():learned[key].update(values)
    for r in raw.to_dict('records'):
        uid,status=unique_choice(opta_ids.get(str(r.get('provider_opta_id') or ''),set()))
        if status=='mapped':learned[(r['provider'],str(r['provider_player_id']))].add(uid)
    for r in raw.to_dict('records'):
        r=dict(r);mid,mstatus=resolve_match(r,registry,known_matches)
        r['match_id']=mid or ''
        uid,pstatus,method=resolve_player(r,learned,opta_ids,names)
        valid=math.isfinite(float(r['rating'])) and 0<=float(r['rating'])<=10
        status='mapped' if mid and uid and valid else ('invalid_rating' if not valid else
            ('ambiguous' if 'ambiguous' in [mstatus,pstatus] else 'unresolved'))
        audits.append({**r,'player_uuid':uid or '', 'mapping_status':status,
            'player_mapping_status':pstatus,'match_mapping_status':mstatus,'mapping_rule':method})
        if status=='mapped':
            r['player_uuid']=uid;r['mapping_rule']=method;r['role']=roles.get((mid,uid),'UNKNOWN')
            mapped.append(r)
    return pd.DataFrame(mapped),pd.DataFrame(audits)
