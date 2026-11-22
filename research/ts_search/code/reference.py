"""Independent finite-state/nomination enumeration. No TS candidate/beam calls.

The frozen arbitrary-nomination score is supplied by the adapter; the independent
scalar rule calculation is only a cross-check, never a replacement objective.
"""
import itertools
from collections import Counter
from functools import lru_cache
import numpy as np
COUNTS={1:2,2:5,3:5,4:3};MIN={2:3,3:2,4:1};MAX={2:5,3:5,4:3}
def sale(purchase,current):return current if current<=purchase else purchase+(current-purchase)//2
def transition(purchases,bank,ft,selected,players):
 owned=dict(purchases);selected=set(selected);out=tuple(sorted(set(owned)-selected));inc=tuple(sorted(selected-set(owned)))
 bank2=bank+sum(sale(owned[p],players[p]['price'])for p in out)-sum(players[p]['price']for p in inc)
 if bank2<0:return None
 after=tuple(sorted((p,owned[p]if p in owned else players[p]['price'])for p in selected));paid=max(0,len(inc)-ft)
 return (after,bank2,min(5,max(0,ft-len(inc))+1)),out,inc,4*paid,paid

def legal_squads(players):
 out=[]
 for ids in itertools.combinations(sorted(players),15):
  if Counter(players[p]['position']for p in ids)!=COUNTS:continue
  if max(Counter(players[p]['team']for p in ids).values())>3:continue
  out.append(ids)
 return out

@lru_cache(None)
def legal_xis(ids,positions):
 by={p:[i for i in ids if positions[ids.index(i)]==p]for p in COUNTS};out=[]
 for g in by[1]:
  for d in range(3,6):
   for m in range(2,6):
    f=10-d-m
    if not 1<=f<=3:continue
    for ds in itertools.combinations(by[2],d):
     for ms in itertools.combinations(by[3],m):
      for fs in itertools.combinations(by[4],f):out.append(tuple([g,*ds,*ms,*fs]))
 return tuple(out)

def legal_nomination(ids,positions,nom):
 xi,bench,c,v=nom;lookup=dict(zip(ids,positions))
 return len(xi)==11 and len(set(xi))==11 and len(bench)==4 and set(xi).isdisjoint(bench) and set(xi)|set(bench)==set(ids)and sum(lookup[p]==1 for p in xi)==1 and all(MIN[p]<=sum(lookup[i]==p for i in xi)<=MAX[p]for p in MIN)and lookup[bench[-1]]==1 and all(lookup[p]!=1 for p in bench[:-1])and c in xi and v in xi and c!=v

def scalar_autosubs(ids,positions,points,minutes,xi,bench):
 """Scalar matching: maximize valid filled slots, then lexicographic bench priority.

 Retain unfilled slots in the nominated formation. A GK has a separate reserve.
 Match each selected substitute to one absent starting slot and check formation.
 """
 pos=dict(zip(ids,positions));result=[]
 for row,mins in zip(points,minutes):
  pts=dict(zip(ids,row));playing={p:m>0 for p,m in zip(ids,mins)};score=sum(pts[p]for p in xi);gk=next(p for p in xi if pos[p]==1);reserve=next(p for p in bench if pos[p]==1)
  if not playing[gk]and playing[reserve]:score+=pts[reserve]
  absent=[p for p in xi if pos[p]!=1 and not playing[p]];subs=[p for p in bench if pos[p]!=1];best=None
  for k in range(min(3,len(absent))+1):
   for chosen in itertools.combinations(subs,k):
    if not all(playing[p]for p in chosen):continue
    valid=False
    for removed in itertools.combinations(absent,k):
     field=[p for p in xi if pos[p]!=1 and p not in removed]+list(chosen);counts=Counter(pos[p]for p in field)
     if all(MIN[p]<=counts[p]<=MAX[p]for p in MIN):valid=True;break
    if valid:
     key=(k,tuple(p in chosen for p in subs))
     if best is None or key>best[0]:best=(key,sum(pts[p]for p in chosen))
  assert best is not None;result.append(score+best[1])
 return np.array(result)

def scalar_score(ids,positions,points,minutes,nom):
 xi,bench,c,v=nom;index={p:i for i,p in enumerate(ids)};base=scalar_autosubs(ids,positions,points,minutes,xi,bench)
 bonus=np.array([r[index[c]]if m[index[c]]>0 else r[index[v]]for r,m in zip(points,minutes)])
 return float(np.mean(base+bonus))

def deterministic_best(ids,positions,means):
 xis=legal_xis(ids,positions);ix={p:i for i,p in enumerate(ids)};a=np.array([[ix[p]for p in xi]for xi in xis]);values=means[a].sum(axis=1)+means[a].max(axis=1);best=int(np.argmax(values));xi=xis[best];c=max(xi,key=lambda p:(means[ix[p]],-p));v=next(p for p in xi if p!=c);bench=tuple(sorted(p for p in ids if p not in xi and positions[ix[p]]!=1))+tuple(p for p in ids if p not in xi and positions[ix[p]]==1)
 return float(values[best]),(xi,bench,c,v),len(xis)*110*6

def restricted_best(ids,positions,points,minutes,xi_menu,score):
 best=None;count=0;audits=0;mismatches=[];ix={p:i for i,p in enumerate(ids)}
 for given in xi_menu:
  xi=tuple(given);remaining=[p for p in ids if p not in xi];gk=next(p for p in remaining if positions[ix[p]]==1);field=[p for p in remaining if p!=gk]
  # Captain choice separates additively from bench points; enumerate every pair.
  pairs=[(c,v)for c in xi for v in xi if c!=v];bonus=[float(np.mean([r[ix[c]]if m[ix[c]]>0 else r[ix[v]]for r,m in zip(points,minutes)]))for c,v in pairs];c,v=pairs[int(np.argmax(bonus))]
  for order in itertools.permutations(field):
   nom=(xi,tuple([*order,gk]),c,v);value=score(nom);independent=scalar_score(ids,positions,points,minutes,nom);audits+=1
   if abs(value-independent)>1e-9:mismatches.append(dict(nomination=nom,frozen=value,independent=independent))
   count+=len(pairs)
   if best is None or value>best[0]+1e-12:best=(value,nom)
 return *best,count,audits,mismatches

def exact_path(case,players,squads,score_tables,weights,buffer):
 initial=(tuple(sorted((p,players[p]['purchase'])for p in case['initial_ids'])),case['bank'],case['free_transfers']);layer={initial:(0.,[])};sizes=[];transitions=0
 for g,w in enumerate(weights):
  next_layer={}
  for (purchases,bank,ft),(value,path)in sorted(layer.items()):
   for squad in squads:
    moved=transition(purchases,bank,ft,squad,players)
    if moved is None:continue
    after,out,inc,hits,paid=moved;assert len(inc)<=2
    score=score_tables[g][squad];total=value+w*score-hits-buffer*paid;transitions+=1
    if after not in next_layer or total>next_layer[after][0]+1e-12:
     next_layer[after]=(total,[*path,dict(gw=g+1,ids=squad,outgoing=out,incoming=inc,bank_before=bank,bank_after=after[1],free_transfers_before=ft,free_transfers_after=after[2],official_hit_points=hits,uncertainty_penalty=buffer*paid,projected_manager_score=score)])
  layer=next_layer;sizes.append(len(layer))
 assert layer
 best=max(layer.values(),key=lambda r:r[0]);return dict(objective=best[0],path=best[1],state_counts=sizes,transitions=transitions)
