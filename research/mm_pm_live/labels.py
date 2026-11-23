"""Official final-GW adapter, compatible with the existing completed-GW collector.

DGWstarts require official per-fixture history. No minute-based start inference.
"""
import hashlib
import json
from datetime import datetime,timezone

MAP={'minutes':'appearance_points','goals_scored':'goal_points','assists':'assist_points',
     'clean_sheets':'cs_points','goals_conceded':'gc_points','saves':'save_points',
     'penalties_saved':'penalty_save_points','defensive_contribution':'dc_points',
     'bonus':'bonus_points','yellow_cards':'negative_points','red_cards':'negative_points',
     'own_goals':'negative_points','penalties_missed':'negative_points'}
COMP=tuple(dict.fromkeys(MAP.values()))
ZERO_FIELDS=['minutes','starts','total_points','goals_scored','assists','clean_sheets',
             'goals_conceded','own_goals','penalties_saved','penalties_missed','yellow_cards',
             'red_cards','saves','bonus','bps','defensive_contribution']


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def normalize(f,original_bootstrap,original_fixtures,payload,identities,history=None):
    gw=f['gws'][0];event=payload['official_event'];history=history or{}
    if payload['season']!=f['season']or payload['gw']!=gw or event['id']!=gw:raise ValueError('Label season/origin mismatch')
    if not(event.get('finished')is True and event.get('data_checked')is True):
        return dict(status='awaiting_results',rows=[],missing=[],scored_rows=0)
    fixtures={r['id']:r for r in payload['official_fixtures']}
    if len(fixtures)!=len(payload['official_fixtures'])or any(not r.get('finished')for r in fixtures.values()):raise ValueError('Unfinished/duplicate fixtures')
    if payload.get('observed_at_utc'):
        observed=datetime.fromisoformat(payload['observed_at_utc'].replace('Z','+00:00'))
        if any(r.get('kickoff_time')and datetime.fromisoformat(r['kickoff_time'].replace('Z','+00:00'))>observed for r in fixtures.values()):
            raise ValueError('Future fixture cannot have a final observed result')
    live=payload['official_player_live']
    if isinstance(live,dict):
        live=[dict(v,id=int(k))for k,v in live.items()]
    actual={r['id']:r for r in live}
    if len(actual)!=len(live):raise ValueError('Duplicate live player IDs')
    original={r['id']:r for r in original_bootstrap['elements']};codes={r['id']:r['code']for r in identities}
    if len(codes)!=len(identities):raise ValueError('Duplicate stable codes')
    rows=[];missing=[];blank=[]
    for p in f['players']:
        pid=p['id'];w=next(w for w in p['weeks']if w['gw']==gw)
        def reject(reason):missing.append(dict(id=pid,reason=reason))
        if pid not in original or codes.get(pid)!=original[pid].get('code'):
            reject('stable_identity_missing_or_changed');continue
        expected={int(x['fixture_uuid'].rsplit('-',1)[1])for x in w['fixtures']}
        source_schedule={r['id']for r in original_fixtures if r.get('event')==gw and p['team_id']in[r['team_h'],r['team_a']]}
        final_schedule={r['id']for r in fixtures.values()if r.get('event')==gw and p['team_id']in[r['team_h'],r['team_a']]}
        if expected!=source_schedule or expected!=final_schedule:
            reject('original_or_final_schedule_changed');continue
        a=actual.get(pid)
        if a is None:reject('explicit_official_player_missing');continue
        stats=a['stats'];explain={r['fixture']:r['stats']for r in a.get('explain',[])}
        if len(explain)!=len(a.get('explain',[])):raise ValueError('Duplicate fixture explain')
        if set(explain)-expected:reject('unexpected_fixture_or_player_transfer');continue
        if not expected:
            if stats.get('total_points')!=0 or stats.get('minutes')!=0:reject('blank_with_observed_points');continue
            blank.append(pid);continue
        if sum(s['points']for entries in explain.values()for s in entries)!=stats.get('total_points'):
            reject('official_event_point_ledger_mismatch');continue
        closed_zero=all(stats.get(k)==0 for k in ZERO_FIELDS)
        local=[];problem=None
        for fixture in sorted(expected):
            items=explain.get(fixture)
            if items is None:
                if closed_zero:items=[]
                else:problem='missing_fixture_explain_not_proven_zero';break
            components={c:0. for c in COMP};values={}
            for item in items:
                if item['identifier']not in MAP or item.get('points_modification',0):
                    problem='unknown_or_modified_point_rule';break
                components[MAP[item['identifier']]]+=item['points'];values[item['identifier']]=item['value']
            if problem:break
            minutes=values.get('minutes',0)
            if type(minutes)is not int or not 0<=minutes<=90:problem='reported_minutes_outside_contract';break
            h=history.get((pid,fixture))
            starts=h.get('starts')if h else stats.get('starts')if len(expected)==1 else 0 if closed_zero else None
            if starts not in (None,0,1):problem='invalid_official_start';break
            if h and (h.get('minutes')!=minutes or h.get('total_points')!=sum(components.values())):
                problem='official_history_live_disagreement';break
            if h and len(expected)==1 and h.get('bps')is not None and stats.get('bps')!=h['bps']:
                problem='official_bps_revision_disagreement';break
            local.append(dict(id=pid,fixture=fixture,minutes=minutes,starts=starts,points=sum(components.values()),
                              components=components,goals=values.get('goals_scored',0),assists=values.get('assists',0),
                              dc_count=h.get('defensive_contribution')if h else stats.get('defensive_contribution')if len(expected)==1 else None,
                              bps=h.get('bps')if h else stats.get('bps')if len(expected)==1 else None,
                              official_card_only=minutes==0 and (values.get('yellow_cards',0)>0 or values.get('red_cards',0)>0)))
        if problem:reject(problem);continue
        if sum(r['minutes']for r in local)!=stats.get('minutes'):
            reject('official_fixture_minute_sum_mismatch');continue
        if all(r['starts']is not None for r in local)and sum(r['starts']for r in local)!=stats.get('starts'):
            reject('official_fixture_start_sum_mismatch');continue
        if any(sum(r[k]for r in local)!=stats.get(source)for k,source in [('goals','goals_scored'),('assists','assists')]):
            reject('official_goal_assist_count_mismatch');continue
        if all(r['bps']is not None for r in local)and sum(r['bps']for r in local)!=stats.get('bps'):
            reject('official_fixture_bps_sum_mismatch');continue
        rows.extend(local)
    return dict(status='complete'if not missing else'partial_labels',rows=rows,missing=missing,blank_player_ids=blank,
                expected_players=len(f['players']),scored_players=len({r['id']for r in rows})+len(blank),
                mm_start_unknown=sum(r['starts']is None for r in rows),fixtures=len(fixtures))


def get_official(endpoint):
    # Same official public transport contract as collect_completed_2026_gws.py.
    import urllib.request
    request=urllib.request.Request('https://fantasy.premierleague.com/api/'+endpoint,
        headers={'User-Agent':'FPL-Analytics-2026-weekly-observation-collector'})
    with urllib.request.urlopen(request,timeout=35)as response:return json.load(response)


def fetch_final(f):
    """Never request live outcomes for an unfinished GW. No manager endpoints."""
    gw=f['gws'][0];bootstrap=get_official('bootstrap-static/')
    event=next(e for e in bootstrap['events']if e['id']==gw)
    if not(event.get('finished')is True and event.get('data_checked')is True):
        return dict(status='awaiting_results',event={k:event[k]for k in ['id','finished','data_checked']})
    first=min(datetime.fromisoformat(e['deadline_time'].replace('Z','+00:00'))for e in bootstrap['events'])
    if f['season']!=f'{first.year}-{str(first.year+1)[-2:]}':raise ValueError('Official outcome calendar is another season')
    fixtures=[r for r in get_official('fixtures/')if r.get('event')==gw]
    if any(not r.get('finished')for r in fixtures):return dict(status='awaiting_results',event=event)
    live=get_official(f'event/{gw}/live/')['elements']
    histories={}
    for p in f['players']:
        week=next(w for w in p['weeks']if w['gw']==gw)
        if len(week['fixtures'])>1:
            # Existing live GWstarts are aggregate; augment only necessary DGWs.
            for h in get_official(f'element-summary/{p["id"]}/').get('history',[]):
                if h['fixture']in{int(x['fixture_uuid'].rsplit('-',1)[1])for x in week['fixtures']}:
                    histories[p['id'],h['fixture']]=h
    return dict(status='final',payload=dict(season=f['season'],gw=gw,observed_at_utc=datetime.now(timezone.utc).isoformat(),
                official_event={k:event[k]for k in ['id','deadline_time','finished','data_checked']},official_fixtures=fixtures,official_player_live=live),
                identities=[dict(id=p['id'],code=p['code'])for p in bootstrap['elements']],
                history=[dict(id=pid,fixture=fx,stats=h)for(pid,fx),h in histories.items()])
