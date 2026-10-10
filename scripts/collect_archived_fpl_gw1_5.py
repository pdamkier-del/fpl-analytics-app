#!/usr/bin/env python3
"""Discover archived official FPL predeadline bootstrap player snapshots GW1-5.

GitHub public Randdalf/fplcache stores official bootstrap JSON 4x/day.
Choose archive strictly before official GW cutoff. Record content hashes,
source URLs and current-to-historic IDs; DO NOT promote reconstructed MM yet.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib,json,lzma,os,sys
import requests

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/live-final-model'
OUT=WORK/'predeadline_2026_archives'
BASE='https://api.github.com/repos/Randdalf/fplcache/contents/cache'
HEAD={'Accept':'application/vnd.github+json','User-Agent':'FPL-Analytics-cutoff-safety-audit'}
if os.getenv('GH_READ_TOKEN'):
    HEAD['Authorization']='Bearer '+os.getenv('GH_READ_TOKEN')

def github_json(url):
    r=requests.get(url,headers=HEAD,timeout=40)
    r.raise_for_status()
    return r.json()

def cutoff(value):
    return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)

def collect():
    live=json.loads((WORK/'bootstrap.json').read_text())
    events={int(e['id']):e for e in live['events']}
    current_ids={int(p['id']) for p in live['elements']}
    OUT.mkdir(parents=True,exist_ok=True)
    logs=[]
    for gw in range(1,6):
        deadline=cutoff(events[gw]['deadline_time'])
        cutoff_safe=deadline-timedelta(minutes=15)
        candidates=[]
        for day in (deadline.date()-timedelta(days=1),deadline.date()):
            url=f'{BASE}/{day.year}/{day.month}/{day.day}'
            entries=github_json(url)
            if not isinstance(entries,list):raise ValueError('Unexpected archive listing')
            for file in entries:
                name=file['name']
                if not name.endswith('.json.xz'):continue
                stem=name[:4]
                if len(stem)!=4 or not stem.isdigit():continue
                hour,minute=int(stem[:2]),int(stem[2:4])
                if hour>23 or minute>59:continue
                observed=datetime(day.year,day.month,day.day,hour,minute,tzinfo=timezone.utc)
                if observed>=cutoff_safe:continue
                candidates.append((observed,file))
        if not candidates:raise ValueError(f'GW{gw}: no safely predeadline archive')
        observed,file=max(candidates,key=lambda z:z[0])
        source=file.get('download_url')
        if not source or not source.startswith('https://raw.githubusercontent.com/Randdalf/fplcache/'):
            raise ValueError('Untrusted source URL')
        r=requests.get(source,headers=HEAD,timeout=60);r.raise_for_status()
        packed=r.content
        data=json.loads(lzma.decompress(packed))
        upcoming=[int(e['id']) for e in data['events'] if e.get('is_next')]
        if upcoming!=[gw]:
            raise ValueError(f'GW{gw}: archived bootstrap is scoped to {upcoming}, not this GW')
        archived_deadline=cutoff(next(e['deadline_time'] for e in data['events'] if int(e['id'])==gw))
        if archived_deadline<observed or archived_deadline>deadline+timedelta(hours=12):
            raise ValueError('Archive gameweek deadline mismatch')
        people=[p for p in data['elements'] if p['element_type']!=5]
        if len(people)<300 or len({int(p['id']) for p in people})!=len(people):
            raise ValueError('Archived player roster is incomplete/duplicate')
        recorded={int(p['id']) for p in people}
        row={
            'gw':gw,'official_deadline':deadline.isoformat(),
            'snapshot_at_utc':observed.isoformat(),
            'age_to_deadline_minutes':round((deadline-observed).total_seconds()/60,2),
            'source_url':source,'blob_sha':file['sha'],'source_sha256':hashlib.sha256(packed).hexdigest(),
            'players':len(people),'overlap_current_ids':len(recorded&current_ids),
            'dropped_ids_since_deadline':len(recorded-current_ids),
            'new_ids_since_deadline':len(current_ids-recorded),
            'team_counts':dict(Counter(str(p['team']) for p in people)),
            'news_status_counts':dict(Counter(str(p['status']) for p in people)),
            'players_out_of_team':len([p for p in people if not 1<=int(p['team'])<=20]),
            'same_daypoint_source':True}
        rows=[dict(id=int(p['id']),code=p.get('code'),team=int(p['team']),
              position=int(p['element_type']),status=p.get('status'),
              chance_next=p.get('chance_of_playing_next_round'),
              news=p.get('news'),news_added=p.get('news_added'),
              name=p.get('web_name')) for p in people]
        (OUT/f'gw{gw}.json').write_text(json.dumps({'evidence':row,'players':rows},ensure_ascii=False,separators=(',',':')))
        logs.append(row)
    audit={'classification':'ACTUAL_ARCHIVED_PREDEADLINE_FPL_SNAPSHOT_SOURCE_NOT_CERTIFIED_MM',
           'season':'2026-27','count':len(logs),'official_archive':'Randdalf/fplcache',
           'snapshot_selection':'latest snapshot at least 15 minutes before official GW deadline',
           'captured_all_five_gws':len(logs)==5,
           'times_utc':True,'predeadline_sources_only':True,'retrained_MM':False,
           'rows':logs}
    (OUT/'archive_manifest.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    print('ARCHIVED GW1-5 PREDEADLINE ROSTER EVIDENCE',
          json.dumps([{k:r[k] for k in ('gw','snapshot_at_utc','age_to_deadline_minutes','players',
           'overlap_current_ids','dropped_ids_since_deadline','new_ids_since_deadline','source_sha256')} for r in logs]))
    return audit

if __name__=='__main__':collect()
