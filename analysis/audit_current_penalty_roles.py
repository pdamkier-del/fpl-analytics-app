"""Audit every current B fixture/team penalty rate and official player rank."""
import argparse,json,hashlib,math
from pathlib import Path
import pandas as pd


def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 bootstrap=json.loads((a.inputs/'bootstrap.json').read_text());prov=json.loads((a.inputs/'provenance.json').read_text());f=pd.read_csv(a.inputs/'pm.csv.gz',low_memory=False);catalogue={p['id']:p for p in bootstrap['elements']};rows=[]
 assert not f.duplicated(['fixture_uuid','player_uuid']).any()
 for (fx,team),g in f.groupby(['fixture_uuid','team_id']):
  assert g.lambda_pen.nunique()==1 and g.team_pen_conversion.nunique()==1
  rate=float(g.lambda_pen.iloc[0]);assert math.isfinite(rate) and rate>=0
  players=[]
  for r in g.itertuples():
   official=catalogue[int(r.fpl_element)];assert int(official['team'])==int(team)
   order=official.get('penalties_order');assert order is None or(isinstance(order,(int,float))and math.isfinite(order)and order>0 and order==int(order))
   players.append(dict(player_uuid=r.player_uuid,fpl_element=int(r.fpl_element),name=official['web_name'],official_rank=order,historical_weight=float(r.pen_weight),conversion=float(r.pen_conversion)))
  assert abs(sum(x['historical_weight']for x in players)-1)<1e-6
  assert all(0<=x['conversion']<=1 and x['historical_weight']>=0 for x in players)
  rows.append(dict(fixture_uuid=fx,team_id=int(team),gw=int(g.target_gw.iloc[0]),expected_attempts=rate,p_at_least_one=-math.expm1(-rate),players=players))
 assert len(rows)==120 and f.fixture_uuid.nunique()==60
 a.out.write_text(json.dumps(dict(source_data_at=prov['data_at'],official_roles_observed_at=prov['bootstrap_observed_at'],input_sha256={n:hashlib.sha256((a.inputs/n).read_bytes()).hexdigest()for n in ['bootstrap.json','pm.csv.gz','provenance.json']},fixture_team_rows=len(rows),player_fixture_rows=len(f),all_probabilities_valid=True,unconditional_taker_probabilities_not_inferred_from_static_weights=True,team_fixtures=rows),ensure_ascii=False,indent=2)+'\n')
 print('All',len(f),'player-fixtures and',len(rows),'team-fixtures checked')
if __name__=='__main__':main()
