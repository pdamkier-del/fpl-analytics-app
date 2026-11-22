"""Write the fixed synthetic suite, without importing or running TS or an oracle."""
from pathlib import Path
import itertools,json
OUT=Path(__file__).resolve().parents[1]/'inputs/instances.json'
BASE_POS=[1,1]+[2]*5+[3]*5+[4]*3
BASE_XP=[3,2,6,5,4,1,0.5,12,10,8,6,2,9,8,7]
BASE_XI=[1,3,4,5,8,9,10,11,13,14,15]
def make_det(i):
 family=i//6;variant=i%6;n=17
 pos=BASE_POS+[2,3];price=[50]*n;buy=price.copy();xp=[BASE_XP.copy()+[3,15]for _ in range(6)];bank=variant%3;ft=variant
 label=['budget_enabler','timing_and_FT','sale_price','club_limit','zero_or_negative_leg'][family]
 if family==0:
  price[2]=70;buy[2]=70;price[15]=40;buy[15]=40;price[16]=80;buy[16]=80
  # Negative individual DEF leg frees exactly the funds needed by the stronger MID.
  for w in xp:w[15]=2;w[16]=20+variant
 elif family==1:
  for g,w in enumerate(xp):
   w[15]=[0,2,10,12,8,8][g]+variant/4;w[16]=[0,1,4,16,18,18][g]
 elif family==2:
  price[2]=61+variant;buy[2]=50;price[15]=40;buy[15]=40;price[16]=66;buy[16]=66
  for w in xp:w[15]=3+variant/4;w[16]=18
 elif family==3:
  for g,w in enumerate(xp):w[15]=7+(g%2);w[16]=14+variant
 else:
  for g,w in enumerate(xp):w[15]=1 if variant<3 else -1;w[16]=13+(g==5)*10
 players=[]
 for j in range(n):
  team=j%6+1
  if family==3:
   # Team1 already owns players1,7,13; external16/17 also team1.
   team=1 if j in [0,6,12,15,16]else j%5+2
  players.append(dict(id=j+1,position=pos[j],team=team,price=price[j],purchase=buy[j],points=[[float(xp[g][j])]for g in range(6)],minutes=[[90]for _ in range(6)]))
 return dict(id=f'D{i+1:02}',level='deterministic',family=label,initial_ids=list(range(1,16)),bank=bank,free_transfers=ft,players=players,nomination_domain='all legal XI, all distinct starting C/VC, all legal outfield bench orders (all play, so VC/order score-invariant)')
def make_dnp(i):
 n=8;family=i%4;shift=i//4
 players=[]
 for j,pos in enumerate(BASE_POS):
  target=BASE_XP[j];plays=[True]*n
  if j==7:plays=[s not in [0,1,2]for s in range(n)]
  if j==8:plays=[s not in ([0,1,3]if family%2==0 else[3,4,5])for s in range(n)]
  if j in [2,3,4]:plays=[s!=(j+shift)%n for s in range(n)]
  if j==0:plays=[s not in [6,7]for s in range(n)]
  if j in [5,6,11]:plays=[s!=(j+family+shift)%n for s in range(n)]
  # Exact integer scenario points, with prescribed ranking of means; no model simulation.
  pts=[target*n/sum(plays)if v else 0. for v in plays];mins=[90 if v else 0 for v in plays]
  players.append(dict(id=j+1,position=pos,team=j%6+1,price=50,purchase=50,points=[pts.copy()for _ in range(6)],minutes=[mins.copy()for _ in range(6)]))
 alternative=([1,3,4,6,8,9,10,11,13,14,15]if family<2 else[1,3,4,5,8,9,10,12,13,14,15])
 keeper=[2,*BASE_XI[1:]]
 return dict(id=f'N{i+1:02}',level='restricted_DNP',family=['correlated_captain','anticorrelated_captain','midfield_autosub','keeper_and_priority'][family],initial_ids=list(range(1,16)),bank=shift,free_transfers=i%6,players=players,xi_menu=[BASE_XI,alternative,keeper],nomination_domain='exactly these 3 XI; all 6 outfield-bench permutations and all 110 distinct starting C/VC pairs; 1980 nominations/GW; no transfers because pool=15')
def generate():
 ds=[make_det(i)for i in range(30)];ns=[make_dnp(i)for i in range(12)];cases=[]
 # Five deterministic and two DNP cases per block: both levels represented if timeout occurs.
 for k in range(6):cases.extend(ds[k*5:k*5+5]);cases.extend(ns[k*2:k*2+2])
 return dict(schema='TS-exact-small-inputs-v1',synthetic=True,randomness='none',horizon_gws=[1,2,3,4,5,6],cases=cases)
if __name__=='__main__':OUT.write_text(json.dumps(generate(),indent=2,allow_nan=False)+'\n');print('Wrote 30 deterministic and 12 restricted-DNP cases; no optimizer executed.')
