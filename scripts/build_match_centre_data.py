#!/usr/bin/env python3
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'data_v1_1'/'raw'/'fpl-core-2025-26'
IDENT=ROOT/'data_v1_1'/'derived'/'mm_v2_ratings'/'identity_source'/'data'/'2025-2026'
OUT=ROOT/'app'/'match-data.js'

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

team_short={}
for r in rows(IDENT/'teams.csv'):
    team_short[str(r.get('code','')).strip()]=r.get('short_name') or r.get('name')

player_code={}
for r in rows(IDENT/'players.csv'):
    pid=str(r.get('player_id','')).strip()
    code=str(r.get('player_code','')).strip()
    if pid and code:
        player_code[pid]=int(float(code))

matches=[]
lineups=[]
for gw in range(1,39):
    gd=CORE/f'GW{gw}'
    fp=gd/'fixtures.csv'
    lp=gd/'lineups.csv'
    if fp.exists():
        for r in rows(fp):
            mid=r.get('match_id')
            if not mid: continue
            def f(name):
                v=r.get(name)
                if v in (None,''): return None
                try: return float(v)
                except: return v
            def i(name):
                v=f(name)
                return int(v) if isinstance(v,float) and v.is_integer() else v
            hc=str(i('home_team') or '')
            ac=str(i('away_team') or '')
            matches.append({
                'match_id':mid,
                'gw':i('gameweek') or gw,
                'kickoff_time':r.get('kickoff_time'),
                'home':team_short.get(hc,hc),
                'away':team_short.get(ac,ac),
                'home_score':i('home_score'),'away_score':i('away_score'),
                'finished':str(r.get('finished','')).lower()=='true',
                'fotmob_id':i('fotmob_id'),
                'stats':{
                    'possession':[f('home_possession'),f('away_possession')],
                    'xg':[f('home_expected_goals_xg'),f('away_expected_goals_xg')],
                    'shots':[i('home_total_shots'),i('away_total_shots')],
                    'sot':[i('home_shots_on_target'),i('away_shots_on_target')],
                    'big_chances':[i('home_big_chances'),i('away_big_chances')],
                    'big_chances_missed':[i('home_big_chances_missed'),i('away_big_chances_missed')],
                    'passes':[i('home_accurate_passes'),i('away_accurate_passes')],
                    'pass_pct':[f('home_accurate_passes_pct'),f('away_accurate_passes_pct')],
                    'corners':[i('home_corners'),i('away_corners')],
                    'fouls':[i('home_fouls_committed'),i('away_fouls_committed')],
                    'yellow':[i('home_yellow_cards'),i('away_yellow_cards')],
                    'red':[i('home_red_cards'),i('away_red_cards')],
                    'saves':[i('home_keeper_saves'),i('away_keeper_saves')],
                    'touches_box':[i('home_touches_in_opposition_box'),i('away_touches_in_opposition_box')],
                    'npxg':[f('home_non_penalty_xg'),f('away_non_penalty_xg')],
                    'xgot':[f('home_xg_on_target_xgot'),f('away_xg_on_target_xgot')]
                }
            })
    if lp.exists():
        for r in rows(lp):
            pid=str(r.get('player_id','')).strip()
            lineups.append({
                'match_id':r.get('match_id'),
                'side':r.get('team_side'),
                'club':team_short.get(str(r.get('team_code','')).strip(),str(r.get('team_code','')).strip()),
                'id':int(float(pid)) if pid else None,
                'player_code':player_code.get(pid),
                'player':r.get('player_name'),
                'pos':r.get('position'),
                'shirt':int(float(r['jersey_number'])) if r.get('jersey_number') not in (None,'') else None,
                'starting':str(r.get('is_starting','')).lower()=='true',
                'formation':r.get('formation'),
                'status':r.get('lineup_status')
            })

payload={'season':'2025/26','matches':matches,'lineups':lineups}
OUT.write_text('window.FPL_MATCH_DATA='+json.dumps(payload,separators=(',',':'),ensure_ascii=False)+';\n',encoding='utf-8')
print(f'wrote {OUT} with {len(matches)} matches and {len(lineups)} lineup rows')

if __name__=='__main__':
    pass
