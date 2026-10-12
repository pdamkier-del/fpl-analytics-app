"""Public display-only match history from existing official completed-GW feeds.
Does not change historical model inputs or infer missing per-match values.
"""
import json
from pathlib import Path

def build(official,fixtures,events):
    if official['fetched_at']!=fixtures['fetched_at']:raise ValueError('Player/fixture snapshot mismatch')
    ids={p['id'] for p in official['players']}
    matches={f['id']:f for f in fixtures['fixtures']}
    complete=[gw for gw in events if all(f.get('finished') for f in fixtures['fixtures'] if f.get('gw')==gw)]
    results=[];gws=[]
    for gw,event in sorted(events.items()):
        for p in event.get('elements',[]):
            if p.get('id') not in ids:continue
            stats=p.get('stats') or {}
            explain=p.get('explain') or []
            if gw in complete or explain and all(matches.get(e.get('fixture'),{}).get('finished') for e in explain):
                gws.append(dict(player_id=p['id'],gw=gw,stats=stats,gw_complete=gw in complete))
            for item in explain:
                f=matches.get(item.get('fixture'))
                if not f or f.get('gw')!=gw:raise ValueError('Fixture identity/GW mismatch')
                if not f.get('finished'):continue
                # GW totals cannot be allocated to individual DGW matches.
                single=len(explain)==1 and all(sum(x.get('gw')==gw and team in (x['home'],x['away']) for x in fixtures['fixtures'])==1 for team in (f['home'],f['away']))
                parts=item.get('stats') or []
                points=sum(s['points'] for s in parts) if isinstance(item.get('stats'),list) and all(isinstance(s.get('points'),(int,float)) for s in parts) else None
                results.append(dict(player_id=p['id'],fixture_id=f['id'],gw=gw,total_points=points,
                    stats=stats if single else {},stats_scope='single_fixture_gw' if single else 'gw_only',point_breakdown=parts))
    if len({(r['player_id'],r['fixture_id']) for r in results})!=len(results):raise ValueError('Duplicate player/fixture history')
    return dict(schema_version=1,source='Official FPL event/{gw}/live + fixtures',observed_at=official['fetched_at'],available_gws=sorted(events),completed_gws=sorted(complete),gw_rows=gws,match_rows=results,note='Display-only actual outcomes. Per-match xG and other GW totals are unavailable for ambiguous double gameweeks.')

def write(official,fixtures,events,path):
    Path(path).write_text(json.dumps(build(official,fixtures,events),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
