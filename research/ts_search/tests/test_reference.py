import importlib.util,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];CODE=ROOT/'research/ts_search/code';sys.path.insert(0,str(CODE))
from reference import sale,transition,legal_squads,legal_nomination,scalar_score,deterministic_best
from generate_instances import generate,BASE_XI,BASE_POS

def test_half_profit_and_price_fall_are_integer_exact():
 assert sale(50,61)==55;assert sale(50,62)==56;assert sale(60,49)==49

def test_ft_carry_hits_bank_and_repurchase():
 players={i:dict(price=50,position=2,team=i)for i in range(1,18)};players[1]['price']=61;players[16]['price']=65
 state=tuple((i,50)for i in range(1,16));selected=tuple(range(2,17));r=transition(state,10,0,selected,players)
 assert r[0][1]==0 and r[0][2]==1 and r[3:]==(4,1)
 assert dict(r[0][0])[16]==65
 keep=transition(state,0,5,tuple(range(1,16)),players);assert keep[0][2]==5 and keep[3:]==(0,0)
 assert transition(state,9,0,selected,players)is None

def test_hand_scored_correlated_captain_and_autosub():
 ids=tuple(range(1,16));xi=tuple(BASE_XI);bench=(6,7,12,2);nom=(xi,bench,8,9)
 pts=np.ones((2,15));mins=np.ones((2,15))*90;pts[0,7]=0;mins[0,7]=0;pts[0,8]=4;pts[1,7]=10;pts[1,8]=4
 # Scenario0: nominated13 + reserve1 + vice4 =18. Scenario1:23 + captain10 =33.
 assert scalar_score(ids,tuple(BASE_POS),pts,mins,nom)==25.5
 assert legal_nomination(ids,tuple(BASE_POS),nom)
 assert not legal_nomination(ids,tuple(BASE_POS),(xi,bench,8,8))

def test_minimum_defenders_blocks_midfield_replacement():
 ids=tuple(range(1,16));xi=tuple(BASE_XI);nom=(xi,(12,6,7,2),8,9);pts=np.ones((1,15));mins=np.ones((1,15))*90;pts[0,2]=0;mins[0,2]=0;pts[0,11]=100;pts[0,5]=3
 # A MID reserve cannot replace the third DEF; DEF6 fills it instead. 10+3+captain1.
 assert scalar_score(ids,tuple(BASE_POS),pts,mins,nom)==14

def test_generated_inputs_are_exactly_registered_suite_and_keep_heuristic_menu():
 suite=generate();assert suite==json.loads((CODE.parent/'inputs/instances.json').read_text());cases=suite['cases'];assert len(cases)==42
 assert sum(c['level']=='deterministic'for c in cases)==30;assert sum(c['level']=='restricted_DNP'for c in cases)==12
 for c in cases:
  assert len(c['players'])<=17 and all(len(p['points'])==6 and all(len(x)<=8 for x in p['points'])for p in c['players'])
  players={p['id']:p for p in c['players']};squads=legal_squads(players);assert tuple(c['initial_ids'])in squads
  if c['level']=='restricted_DNP':assert len(c['xi_menu'])==3

def test_deterministic_exact_nomination_hand_witness():
 ids=tuple(range(1,16));means=np.array([3,2,6,5,4,1,.5,12,10,8,6,2,9,8,7]);value,nom,count=deterministic_best(ids,tuple(BASE_POS),means)
 assert value==90.;assert count>0;assert legal_nomination(ids,tuple(BASE_POS),nom)
 assert scalar_score(ids,tuple(BASE_POS),means[None,:],np.ones((1,15))*90,nom)==90.
