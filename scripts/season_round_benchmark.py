"""Exact hindsight XI benchmark, deliberately without a budget or transfers.

This is not a forecast or an attainable full-season manager strategy.
"""
import json,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint

def best_xi(players):
    if len(players)<11:return None
    n=len(players);constraints=[];lo=[];hi=[]
    def row(indices,lower,upper):
        r=np.zeros(2*n)
        for i,value in indices:r[i]=value
        constraints.append(r);lo.append(lower);hi.append(upper)
    row([(i,1)for i in range(n)],11,11);row([(n+i,1)for i in range(n)],1,1)
    for pos,minimum,maximum in [(1,1,1),(2,3,5),(3,2,5),(4,1,3)]:row([(i,1)for i,p in enumerate(players)if p['position']==pos],minimum,maximum)
    for team in {p['team_id']for p in players}:row([(i,1)for i,p in enumerate(players)if p['team_id']==team],0,3)
    for i in range(n):row([(i,-1),(n+i,1)],-np.inf,0)
    points=np.array([p['points']for p in players],dtype=float)
    result=milp(-np.concatenate([points,points]),integrality=np.ones(2*n),bounds=Bounds(0,1),constraints=LinearConstraint(np.array(constraints),lo,hi),options={'time_limit':20,'mip_rel_gap':0})
    if result.status!=0:return None
    chosen=[dict(p,role='C'if result.x[n+i]>.5 else'XI')for i,p in enumerate(players)if result.x[i]>.5]
    if len(chosen)!=11 or sum(p['role']=='C'for p in chosen)!=1:raise ValueError('Invalid benchmark optimum')
    return dict(rows=chosen,points=sum(p['points']*(2 if p['role']=='C'else 1)for p in chosen),optimal=True,scope='Hindsight XI across PL, legal formation, max three per club, double captain; NO budget, transfers, bench or chip constraints. Not a feasible season strategy.')

def build(source):
    source=Path(source);base=source/'history';index=json.loads((base/'index.json').read_text())
    for name in ['match-results.json','current-players.json']:
        if hashlib.sha256((base/name).read_bytes()).hexdigest()!=index['files'][name]:raise ValueError('Unverified benchmark results')
    h=json.loads((base/'match-results.json').read_text());catalogue={p['id']:p for p in json.loads((base/'current-players.json').read_text())['players']};out={}
    for gw in h['completed_gws']:
        teams={}
        for r in h['match_rows']:
            if r['gw']==gw and r.get('team_id')is not None:teams.setdefault(r['player_id'],set()).add(r['team_id'])
        players=[]
        for r in h['gw_rows']:
            club=teams.get(r['player_id'],set());p=catalogue.get(r['player_id'])
            if r['gw']!=gw or not r.get('gw_complete')or not(r['stats']['minutes']>0 or r['stats'].get('starts',0)>0 or r['stats'].get('yellow_cards',0)>0 or r['stats'].get('red_cards',0)>0 or r['stats'].get('played')is True) or len(club)!=1 or not p:continue
            players.append(dict(id=p['id'],name=p['web_name'],position=p['position'],team_id=next(iter(club)),points=r['stats']['total_points']))
        result=best_xi(players)
        if result:out[str(gw)]=result
    return out
