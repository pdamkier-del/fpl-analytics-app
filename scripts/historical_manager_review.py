"""Private one-round manager replay. No current plan, model or public data changes.

Model recommendation reuses TS search and PM joint draws. Hindsight is a separate
full-market MILP upper bound certified only if legal FPL rescoring attains it.
"""
import argparse,gzip,hashlib,json,math
from dataclasses import replace
from contextlib import contextmanager
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix,vstack
from fpl_xpts.season_replay import ReplayState,OwnedPlayer,selling_price,valid_squad
from fpl_xpts.transfer_planner import next_free_transfers,plan_transfer_path,execute_first_action,clone_state
from fpl_xpts.optimize import POSITION_COUNTS,START_MIN,START_MAX
from run_joint_fh_wc_stopping_replay import cfg
from b_preview_ts import ScenarioScorer,autosub_points
POSITIONS={1:'GKP',2:'DEF',3:'MID',4:'FWD'}

def states(history,transfers,initial):
    """Reconstruct state before target-GW transfers, with exact official cash checks."""
    weeks={w['gw']:w for w in history['weeks']};prices={p['id']:p['now_cost']for p in initial['elements']};owned={p['element']:prices[p['element']]for p in weeks[1]['picks']}
    bank=1000-sum(owned.values())
    if bank!=weeks[1]['entry_history']['bank']:raise ValueError('Initial purchase prices/bank do not reconcile')
    if any(t['event']==1 for t in transfers):raise ValueError('Unexpected post-selection GW1 transfer ledger')
    ft=1;result={};chips={k:[]for k in ['wildcard','free_hit','bench_boost','triple_captain']};alias={'3xc':'triple_captain','bboost':'bench_boost','freehit':'free_hit','wildcard':'wildcard'}
    if weeks[1].get('active_chip'):chips[alias[weeks[1]['active_chip']]].append(1)
    for gw in sorted(w for w in weeks if w>=2):
        result[gw]=ReplayState({pid:OwnedPlayer(pid,buy)for pid,buy in owned.items()},bank,ft,{k:v[:]for k,v in chips.items()})
        moves=sorted([t for t in transfers if t['event']==gw],key=lambda t:t['time'])
        chip=weeks[gw].get('active_chip')
        if chip in ['wildcard','freehit']:raise ValueError('Historical WC/FH ownership transition needs a separate reconstruction')
        # Transfers may be paired at the same instant; apply all sales before buys.
        if len({t['element_out']for t in moves})!=len(moves)or any(t['element_out']not in owned for t in moves):raise ValueError('Transfer ledger does not match owned squad')
        for t in moves:del owned[t['element_out']];bank+=t['element_out_cost']
        for t in moves:
            if t['element_in']in owned:raise ValueError('Duplicate transfer purchase')
            owned[t['element_in']]=t['element_in_cost'];bank-=t['element_in_cost']
        row=weeks[gw]['entry_history']
        if len(moves)!=row['event_transfers']or bank!=row['bank']or set(owned)!={p['element']for p in weeks[gw]['picks']}:raise ValueError('Official cash/squad history does not reconcile')
        if 4*max(0,len(moves)-ft)!=row['event_transfers_cost']:raise ValueError('Official FT/hit history does not reconcile')
        ft=next_free_transfers(ft,len(moves))
        if chip:chips[alias[chip]].append(gw)
    return result


def actual_score(rows,actual,hits=0,chip=None):
    ids=[r['id']for r in rows];positions=[POSITIONS[r['position']]for r in rows];ix={pid:i for i,pid in enumerate(ids)};xi=[i for i,r in enumerate(rows)if r['role']in ['XI','C','VC']];bench=[i for i,r in enumerate(rows)if r['role']not in ['XI','C','VC']];bench.sort(key=lambda i:(positions[i]=='GKP',rows[i]['bench_order'] if 'bench_order'in rows[i]else i))
    if len(ids)!=15 or len(set(ids))!=15 or len(xi)!=11:raise ValueError('Invalid scoring lineup')
    if any(pid not in actual for pid in ids):raise ValueError('Missing final actual result')
    pts=np.array([[actual[pid]['points']for pid in ids]],float);plays=np.array([[actual[pid]['played']for pid in ids]],bool)
    base=pts.sum()if chip=='bench_boost'else autosub_points(pts,plays,positions,xi,bench)[0]
    captain=next(i for i,r in enumerate(rows)if r['role']=='C');vice=next(i for i,r in enumerate(rows)if r['role']=='VC');cap=captain if plays[0,captain]else vice if plays[0,vice]else None
    return float(base+(2 if chip=='triple_captain'else 1)*(pts[0,cap]if cap is not None else 0)-hits)


def hindsight(state,market,actual,*,seconds=90,chip=None):
    """All roster players, actual deadline budget, sale values, any paid transfers.

    No chip used; no future value of bank/FT. Return a global optimum only when
    the MILP bound is attained after legal autosubs/captain/hit rescoring.
    """
    if chip not in [None,'wildcard','free_hit','bench_boost','triple_captain']:raise ValueError('Unknown chip')
    people=[p for p in market if p['id']in actual and(p.get('status')!='u'or p['id']in state.squad)];n=len(people);size=3*n+1;h=3*n;constraints=[];lower=[];upper=[]
    def add(items,lo,hi):constraints.append(dict(items));lower.append(lo);upper.append(hi)
    for pos,count in POSITION_COUNTS.items():add([(i,1)for i,p in enumerate(people)if POSITIONS[p['position']]==pos],count,count)
    for tid in {p['team_id']for p in people}:add([(i,1)for i,p in enumerate(people)if p['team_id']==tid],0,3)
    sale={pid:selling_price(p.purchase_price,next(x['price_tenths']for x in market if x['id']==pid))for pid,p in state.squad.items()}
    add([(i,sale.get(p['id'],p['price_tenths']))for i,p in enumerate(people)],-np.inf,state.bank+sum(sale.values()))
    add([(n+i,1)for i in range(n)],11,11);add([(2*n+i,1)for i in range(n)],1,1)
    for pos in POSITION_COUNTS:add([(n+i,1)for i,p in enumerate(people)if POSITIONS[p['position']]==pos],START_MIN[pos],START_MAX[pos])
    for i in range(n):add([(n+i,1),(i,-1)],-np.inf,0);add([(2*n+i,1),(n+i,-1)],-np.inf,0)
    add([(h,1)]+[(i,-1)for i,p in enumerate(people)if p['id']not in state.squad],-state.free_transfers,np.inf)
    A=lil_matrix((len(constraints),size))
    for j,r in enumerate(constraints):
        for i,v in r.items():A[j,i]=v
    objective=np.zeros(size)
    for i,p in enumerate(people):objective[i if chip=='bench_boost'else n+i]=-actual[p['id']]['points'];objective[2*n+i]=-(2 if chip=='triple_captain'else 1)*actual[p['id']]['points']
    objective[h]=0 if chip in ['wildcard','free_hit']else 4;bounds=np.ones(size);bounds[h]=15
    result=milp(objective,integrality=np.ones(size),bounds=Bounds(0,bounds),constraints=LinearConstraint(A.tocsr(),lower,upper),options={'time_limit':seconds,'mip_rel_gap':0})
    if result.x is None:raise ValueError('No feasible hindsight transfer solution')
    upper_optimal=result.status==0
    min_transfers_proven=False
    if upper_optimal:
        tie=np.zeros(size)
        for i,p in enumerate(people):tie[i]=int(p['id']not in state.squad)
        tied=milp(tie,integrality=np.ones(size),bounds=Bounds(0,bounds),constraints=LinearConstraint(vstack([A.tocsr(),objective]),list(lower)+[float(result.fun)],list(upper)+[float(result.fun)]),options={'time_limit':seconds,'mip_rel_gap':0})
        if tied.x is not None:result=tied;min_transfers_proven=tied.status==0
    chosen=[i for i in range(n)if result.x[i]>.5];xi=[i for i in range(n)if result.x[n+i]>.5];cap=next(i for i in xi if result.x[2*n+i]>.5);vice=next(i for i in xi if i!=cap);bench=[i for i in chosen if i not in xi];bench.sort(key=lambda i:(-actual[people[i]['id']]['points'],people[i]['id']))
    rows=[dict(people[i],role='C'if i==cap else'VC'if i==vice else'XI'if i in xi else'BGK'if people[i]['position']==1 else'B'+str(bench.index(i)+1),bench_order=bench.index(i)if i in bench else 0)for i in chosen]
    outgoing=sorted(set(state.squad)-{people[i]['id']for i in chosen});incoming=sorted({people[i]['id']for i in chosen}-set(state.squad));hits=0 if chip in ['wildcard','free_hit']else 4*max(0,len(incoming)-state.free_transfers);score=actual_score(rows,actual,hits,chip=chip);bound=float(-np.dot(objective,result.x))
    return dict(chip=chip,rows=rows,outgoing=outgoing,incoming=incoming,hits=hits,points=score,upper_bound=bound,globally_optimal=upper_optimal and abs(score-bound)<1e-7,minimum_transfers_proven=min_transfers_proven,solver_status=int(result.status),bank_after=state.bank+sum(sale[pid]for pid in outgoing)-sum(p['price_tenths']for p in market if p['id']in incoming),scope='Hindsight, single GW, selected chip only, all selectable players, exact budget/sale prices and official hits; no future bank/FT value. Global certificate only when MILP optimum equals legal FPL rescoring.')


class HistoricalScorer(ScenarioScorer):
    """Same B scorer, validating an explicitly retrospective origin capsule."""
    def __init__(self,doc,samples,market):
        if doc['schema']!='B-current-season-backtest-v1'or not doc['scope'].startswith('retrospective_fixed_B_policy')or not pd.Timestamp(doc['cutoff'])<pd.Timestamp(doc['origin_deadline']):raise ValueError('Invalid historical draw source')
        if doc.get('model_source')!='03d5c4d4777b44bc1d37884a1cf4dde106b45cab':raise ValueError('Unreviewed historical model source')
        if samples['gw']!=doc['gw']or samples['cutoff']!=doc['cutoff']or samples['draws']!=doc['draws']:raise ValueError('Draw provenance differs')
        by={(r['fixture_uuid'],r['player_uuid']):r for r in samples['records']}
        if len(by)!=len(samples['records'])or len(by)!=len(doc['players']):raise ValueError('Incomplete draw roster')
        self.players={p['id']:p for p in market};self.weeks={}
        for r in doc['players']:
            if self.players[r['player_id']]['code']!=r['fpl_code']:raise ValueError('Historical player identity differs')
            key=(r['fixture_uuid'],r['player_uuid']);scenario=by[key]['scenarios']
            if any(len(scenario[k])!=doc['draws']for k in ['points','minutes'])or any(not math.isfinite(x)for k in ['points','minutes']for x in scenario[k]):raise ValueError('Invalid PM draws')
            if abs(np.mean(scenario['points'])-r['xp'])>1e-9:raise ValueError('Draw means differ from archived PM')
            if (r['player_id'],r['gw'])in self.weeks:raise ValueError('Double GW aggregation not implemented in private replay')
            self.weeks[r['player_id'],r['gw']]=dict(xpts=r['xp'],scenarios=scenario)


@contextmanager
def ts_scoring(scorer):
    import fpl_xpts.optimize as optimize
    import fpl_xpts.transfer_planner as planner
    original=planner._fast_manager_score;original_plan=planner.plan_squad
    planner._fast_manager_score=lambda ctx,ids,gw:scorer.decision(int(gw),tuple(sorted(map(int,ids))))[-1];planner.plan_squad=scorer.plan
    try:yield
    finally:planner._fast_manager_score=original;planner.plan_squad=original_plan


def build(folder,capsules,out,*,history_source,markets,review_gws=None,progress=None):
    folder,capsules,out=map(Path,[folder,capsules,out]);history=json.loads((folder/'history-import.json').read_text());initial=json.loads((folder/'initial-bootstrap.json').read_text());transfers=json.loads((folder/'transfers.json').read_text());targets=set(review_gws if review_gws is not None else [w['gw']for w in history['weeks']if w['gw']>=6]);start=states(dict(history,weeks=[w for w in history['weeks']if w['gw']<=max(targets)]),transfers,initial)if targets else {};completed=0
    history_source=Path(history_source);markets=Path(markets);raw=history_source.read_bytes();index=json.loads((history_source.parent/'index.json').read_text());
    if hashlib.sha256(raw).hexdigest()!=index['files'][history_source.name]:raise ValueError('Unverified actual history')
    hist=json.loads(raw);actual_gw={}
    for w in hist['gw_rows']:
        s=w['stats']
        if w['gw_complete']:actual_gw.setdefault(w['gw'],{})[w['player_id']]=dict(points=s['total_points'],played=s['minutes']>0 or s.get('starts',0)>0 or s.get('yellow_cards',0)>0 or s.get('red_cards',0)>0)
    for w in history['weeks']:
        gw=w['gw']
        if gw not in targets:continue
        if progress:progress(gw,completed,len(targets))
        archive=capsules/f'gw{gw}';doc=json.loads((archive/'forecast.json').read_text());samples=json.loads(gzip.decompress((archive/'scenarios.json.gz').read_bytes()));boot_path=markets/f'gw{gw}/inputs/bootstrap.json'
        if hashlib.sha256(boot_path.read_bytes()).hexdigest()!=doc['source_hashes']['bootstrap.json']:raise ValueError('Historical market differs from archived forecast inputs')
        boot=json.loads(boot_path.read_text());market=[dict(id=p['id'],name=p['web_name'],position=p['element_type'],team_id=p['team'],price_tenths=p['now_cost'],status=p['status'],code=p['code'])for p in boot['elements']if p['element_type']in POSITIONS];state=start[gw];actual=actual_gw[gw]
        if set(state.squad)-{p['id']for p in market}:raise ValueError('Owned player absent from historical market')
        frozen=json.loads(gzip.decompress((Path(__file__).resolve().parents[1]/f'analysis/results/current-season-b-backtest-20261027/gw{gw}.json.gz').read_bytes()))
        if doc['players']!=frozen['players']or doc['source_hashes']!=frozen['source_hashes']:raise ValueError('Replay differs from frozen numerical backtest')
        scorer=HistoricalScorer(doc,samples,market)
        meta=pd.DataFrame([dict(p,web_name=p['name'],team=p['team_id'],position=POSITIONS[p['position']])for p in market if p['status']!='u'or p['id']in state.squad]);origin=pd.DataFrame([dict(id=r['player_id'],gw=gw,origin_gw=gw-1,xpts_mean=r['xp'],p_play=r['p_play'])for r in doc['players']]);config=replace(cfg(),weights=(1.,))
        with ts_scoring(scorer):
            path=plan_transfer_path(state,meta,origin,gw,config);action=path.first_action;after=clone_state(state);execute_first_action(after,path,meta);plan=scorer.plan(origin.merge(meta[['id','position','web_name','team']],on='id'),list(after.squad),gw)
        rows=[]
        for r in plan.rows.to_dict('records'):
            role=r['role'];role='BGK'if role=='GK bench'else'B'+role.split()[-1]if role.startswith('Bench ')else role;rows.append(dict(id=int(r['id']),name=r['web_name'],position=next(k for k,v in POSITIONS.items()if v==r['position']),role=role,bench_order=int(role[1:])if role.startswith('B')and role!='BGK'else 9))
        actual_net=actual_score(rows,actual,action.official_hit_points);best=hindsight(state,market,actual)
        chip_options=[hindsight(state,market,actual,chip=chip)for chip,used in state.chips_used.items()if not any((old<=19)==(gw<=19)for old in used)]
        # Reconstruct user's nominated XI; official picks positions retain order.
        own=[]
        nominated=[dict(p)for p in w['picks']]
        for move in reversed(w.get('automatic_subs',[])):
            incoming=next(p for p in nominated if p['element']==move['element_in']);outgoing=next(p for p in nominated if p['element']==move['element_out'])
            if incoming['position']<=11 and outgoing['position']>11:incoming['position'],outgoing['position']=outgoing['position'],incoming['position']
        w['nominated_picks']=nominated
        for p in sorted(nominated,key=lambda p:p['position']):
            person=next(r for r in market if r['id']==p['element']);role='C'if p['is_captain']else'VC'if p['is_vice_captain']else'XI'if p['position']<=11 else'BGK'if person['position']==1 else'B'+str(p['position']-11);own.append(dict(person,role=role,bench_order=p['position']))
        own_score=actual_score(own,actual,w['entry_history']['event_transfers_cost'])
        if abs(own_score-(w['entry_history']['points']-w['entry_history']['event_transfers_cost']))>1e-8:raise ValueError('Official own lineup/actual scoring mismatch')
        ids=[r['id']for r in own];pts=np.array([scorer.weeks[pid,gw]['scenarios']['points']for pid in ids],float).T;plays=np.array([scorer.weeks[pid,gw]['scenarios']['minutes']for pid in ids],float).T>0;xi=[i for i,r in enumerate(own)if r['role']in ['XI','C','VC']];bench=[i for i,r in enumerate(own)if r['role']not in ['XI','C','VC']];bench.sort(key=lambda i:(own[i]['position']==1,own[i]['bench_order']));cap=next(i for i,r in enumerate(own)if r['role']=='C');vice=next(i for i,r in enumerate(own)if r['role']=='VC');own_xp=float((autosub_points(pts,plays,[POSITIONS[r['position']]for r in own],xi,bench)+pts[:,cap]+np.where(~plays[:,cap],pts[:,vice],0)).mean()-w['entry_history']['event_transfers_cost'])
        w['transfer_review']=dict(schema='fpl-private-transfer-round-v1',gw=gw,previous_gw=gw-1,cutoff=doc['cutoff'],deadline=doc['origin_deadline'],generated_at=pd.Timestamp.now(tz='UTC').isoformat(),model_scope=doc['scope'],manager_state_reconstructed_now=True,state_before=dict(squad=[dict(id=pid,purchase_price_tenths=p.purchase_price)for pid,p in state.squad.items()],bank_tenths=state.bank,free_transfers=state.free_transfers,chips_used=state.chips_used),bank_before=state.bank,free_transfers_before=state.free_transfers,chips_used=state.chips_used,own_expected_score=own_xp,own_actual_score=own_score,model=dict(rows=rows,expected_score=plan.expected_score-action.official_hit_points,points=actual_net,outgoing=list(action.outgoing),incoming=list(action.incoming),hits=action.official_hit_points,bank_after=after.bank,scope='Retrospective B, original TS candidate search, one GW only, shared PM draws, autosubs and captain fallback. No chip; heuristic best found, not a global stochastic optimum. Original hit uncertainty buffer retained.'),hindsight=best,chip_hindsight=chip_options,source_hashes={n:hashlib.sha256((folder/n).read_bytes()).hexdigest()for n in ['history-import.json','transfers.json','initial-bootstrap.json']})
        completed+=1
        scorer.decision.cache_clear()
        if progress:progress(gw,completed,len(targets))
        print('GW',gw,'own',round(own_xp,2),own_score,'model',round(plan.expected_score-action.official_hit_points,2),actual_net,'hindsight',best['points'],best['globally_optimal'],flush=True)
    out.write_text(json.dumps(history,ensure_ascii=False,allow_nan=False,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--capsules',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--history-source',type=Path,required=True);p.add_argument('--markets',type=Path,required=True);a=p.parse_args();build(a.folder,a.capsules,a.out,history_source=a.history_source,markets=a.markets)
