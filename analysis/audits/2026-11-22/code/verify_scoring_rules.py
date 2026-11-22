"""Replay archived official BPS/DC labels through byte-preserved scoring functions."""
from pathlib import Path
import json,gzip
from reference.bps import allocate_bonus_points
from reference.defcon import dc_points_from_count
R=Path(__file__).resolve().parents[1];P={1:'GK',2:'DEF',3:'MID',4:'FWD'}
def load(n):return json.loads(gzip.decompress((R/'inputs/archive'/n).read_bytes()))
current={p['id']:p for p in load('bootstrap.json.gz')['elements']};fixtures=players=dc_mismatch=count_mismatch=bonus_mismatch=0
for gw in [8,9,10]:
 f=load(f'gw{gw}-forecast.json.gz');pos={p['id']:p['position']for p in f['players']};games={}
 for p in load(f'gw{gw}-live.json.gz')['elements']:
  if len(p['explain'])!=1:continue
  players+=1;s=p['stats'];e=p['explain'][0];position=pos.get(p['id'],current[p['id']]['element_type']);points={x['identifier']:x['points']for x in e['stats']};dc_mismatch+=dc_points_from_count(P[position],s['defensive_contribution'])!=points.get('defensive_contribution',0);count=0 if position==1 else s['clearances_blocks_interceptions']+s['tackles']+(s['recoveries']if position in (3,4)else 0);count_mismatch+=count!=s['defensive_contribution']
  if s['minutes']>0:games.setdefault(e['fixture'],[]).append(p)
 for game,rows in games.items():
  fixtures+=1;bonus=allocate_bonus_points({str(p['id']):p['stats']['bps']for p in rows});bonus_mismatch+=any(bonus[str(p['id'])]!=p['stats']['bonus']for p in rows)
out={'fixtures':fixtures,'official_player_rows':players,'dc_threshold_mismatches':dc_mismatch,'dc_count_mismatches':count_mismatch,'bonus_fixture_mismatches':bonus_mismatch,'scope':'Actual known-event rules; does not validate probabilistic event forecasts or missing background BPS'}
assert fixtures==30 and players==2011 and dc_mismatch==count_mismatch==bonus_mismatch==0
(R/'results/scoring-rule-verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
