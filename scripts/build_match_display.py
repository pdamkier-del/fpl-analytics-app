"""Public display-only match history from existing official completed-GW feeds.
Does not change historical model inputs or infer missing per-match values.
"""
import json
from pathlib import Path
from fpl_match_status import played

def build(official,fixtures,events,membership=None):
    membership=membership or {}
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
            if gw in complete or explain and all(played(matches.get(e.get('fixture'),{})) for e in explain):
                gws.append(dict(player_id=p['id'],gw=gw,stats=stats,gw_complete=gw in complete))
            for item in explain:
                f=matches.get(item.get('fixture'))
                if not f or f.get('gw')!=gw:raise ValueError('Fixture identity/GW mismatch')
                if not played(f):continue
                # GW totals cannot be allocated to individual DGW matches.
                single=len(explain)==1 and all(sum(x.get('gw')==gw and team in (x['home'],x['away']) for x in fixtures['fixtures'])==1 for team in (f['home'],f['away']))
                parts=item.get('stats') or []
                points=sum(s['points'] for s in parts) if isinstance(item.get('stats'),list) and all(isinstance(s.get('points'),(int,float)) for s in parts) else None
                sides={side for s in f.get('stats',[]) for side in ('h','a') for entry in s.get(side,[]) if entry['element']==p['id']}
                side=next(iter(sides)) if len(sides)==1 else None
                verified=membership.get((p['id'],f['id'])) if not sides else None
                was_home=side=='h' if side else verified if isinstance(verified,bool) else None
                results.append(dict(side_source='fixture_events' if side else 'element_summary_history' if isinstance(verified,bool) else None,was_home=was_home,team_id=(f['home'] if was_home else f['away']) if isinstance(was_home,bool) else None,player_id=p['id'],fixture_id=f['id'],gw=gw,total_points=points,
                    stats=stats if single else {},stats_scope='single_fixture_gw' if single else 'gw_only',provisional=not f.get('finished'),point_breakdown=parts))
    if len({(r['player_id'],r['fixture_id']) for r in results})!=len(results):raise ValueError('Duplicate player/fixture history')
    return dict(schema_version=1,source='Official FPL event/{gw}/live + fixtures + element-summary historical sides',observed_at=official['fetched_at'],available_gws=sorted(events),completed_gws=sorted(complete),gw_rows=gws,match_rows=results,note='Display-only actual outcomes. Per-match xG and other GW totals are unavailable for ambiguous double gameweeks.')

def write(official,fixtures,events,path,membership=None):
    Path(path).write_text(json.dumps(build(official,fixtures,events,membership),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
