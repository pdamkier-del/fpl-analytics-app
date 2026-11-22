"""Bounded decision regret, on historical prices and model-managed states.

Never stitches future-origin forecasts into an earlier six-GW decision.
"""
import argparse,gzip,itertools,json,lzma,time
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
from b_preview_ts import ScenarioScorer,POSITIONS,autosub_points
from fpl_xpts.optimize import optimize_squad_milp
from fpl_xpts.transfer_planner import _fast_local_candidate_squads,selling_price
from fpl_xpts.season_replay import ReplayState,OwnedPlayer
from precision_audit.dataset import ROOT,load


def scorer(meta,points,minutes,gw):
    s=object.__new__(ScenarioScorer);s.players={int(r.id):dict(position=int(r.element_type))for r in meta.itertuples()};s.weeks={}
    for j,r in enumerate(meta.itertuples()):s.weeks[int(r.id),gw]=dict(xpts=float(points[:,j].mean()),scenarios=dict(points=points[:,j].tolist(),minutes=minutes[:,j].tolist()))
    return s


def exact_lineup(s,gw,ids):
    ids=tuple(sorted(ids));ix={pid:i for i,pid in enumerate(ids)};position=np.array([POSITIONS[s.players[p]['position']]for p in ids]);points=np.array([s.weeks[p,gw]['scenarios']['points']for p in ids]).T;plays=np.array([s.weeks[p,gw]['scenarios']['minutes']for p in ids]).T>0;cp=points.mean(0)[:,None]+(~plays).T@points/len(points);np.fill_diagonal(cp,-np.inf)
    by={p:np.flatnonzero(position==p).tolist()for p in ['GKP','DEF','MID','FWD']};best=(-np.inf,None);count=0;start=time.perf_counter()
    for keeper in by['GKP']:
        for d in range(3,6):
            for m in range(2,6):
                f=10-d-m
                if not 1<=f<=3:continue
                for dd in itertools.combinations(by['DEF'],d):
                    for mm in itertools.combinations(by['MID'],m):
                        for ff in itertools.combinations(by['FWD'],f):
                            xi=[keeper,*dd,*mm,*ff];b=[i for i in range(len(ids))if i not in xi and position[i]!='GKP'];reserve=next(i for i in by['GKP']if i!=keeper);sub=cp[np.ix_(xi,xi)];c,v=np.unravel_index(np.argmax(sub),sub.shape)
                            for order in itertools.permutations(b):
                                bench=[*order,reserve];value=float(autosub_points(points,plays,position,xi,bench).mean()+sub[c,v]);count+=1
                                if value>best[0]:best=(value,dict(xi=[ids[i]for i in xi],bench=[ids[i]for i in bench],captain=ids[xi[c]],vice=ids[xi[v]]))
    return dict(score=best[0],policy=best[1],policies=count,seconds=time.perf_counter()-start)


def exact_candidates(state,meta,limit=2):
    owned=set(state.squad);by=meta.set_index('id');outside=set(meta.id)-owned;out=[]
    for n in range(limit+1):
        for removed in itertools.combinations(sorted(owned),n):
            counts=Counter(by.loc[list(removed)].position)if removed else Counter();sale=sum(selling_price(state.squad[p].purchase_price,int(by.loc[p,'price_tenths']))for p in removed)
            for added in itertools.combinations(sorted(outside),n):
                if Counter(by.loc[list(added)].position)!=counts:continue
                if sum(int(by.loc[p,'price_tenths'])for p in added)>state.bank+sale:continue
                ids=(owned-set(removed))|set(added)
                if by.loc[list(ids)].team.value_counts().max()>3:continue
                out.append(ids)
    return out


def best_bundle(candidates,state,s,gw,buffer=1.5):
    best=None
    for ids in candidates:
        moves=len(set(ids)-set(state.squad));hits=4*max(0,moves-state.free_transfers);score=s.decision(gw,tuple(sorted(ids)))[-1];net=score-hits;utility=net-buffer*max(0,moves-state.free_transfers)
        row=dict(ids=sorted(ids),transfers=moves,official_hits=hits,uncertainty_buffer=buffer*max(0,moves-state.free_transfers),expected_net_points=net,utility=utility)
        if best is None or utility>best['utility']+1e-10:best=row
    return best


def financing_bundles(candidates,state,meta,origin):
    by=meta.set_index('id');value=origin.set_index('id').xpts_mean;owned=set(state.squad);found=[]
    for ids in candidates:
        removed=sorted(owned-set(ids));added=sorted(set(ids)-owned)
        if len(removed)!=2:continue
        for incoming in itertools.permutations(added):
            if any(by.loc[o,'position']!=by.loc[i,'position']for o,i in zip(removed,incoming)):continue
            legs=[dict(outgoing=o,incoming=i,value_gain=float(value[i]-value[o]),cash_freed=selling_price(state.squad[o].purchase_price,int(by.loc[o,'price_tenths']))-int(by.loc[i,'price_tenths']))for o,i in zip(removed,incoming)]
            if any(a['value_gain']<0 and a['cash_freed']>0 and b['cash_freed'] < -state.bank and sum(x['value_gain']for x in legs)>0 for a,b in [legs,legs[::-1]]):
                found.append(set(ids));break
    return found


def historical(work,out):
    # The archived whole-chain horizon audit found 33/183 origin-target cells.
    # Therefore this is a one-GW bounded search test, not a six-GW TS backtest.
    identity=pd.read_csv(ROOT/'data_v1_1/derived/season_2024_25_v1/player_identity.csv');uuid_to_id=identity.set_index('player_uuid').fpl_element.to_dict();records=load(work/'historical-inputs.json.gz');byrecord={(r['season'],r['fixture_uuid']):r for r in records}
    receipts=json.loads((work/'baseline/receipts.json').read_text());results=[];contexts=[]
    import sqlite3
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:past=pd.read_sql_query("SELECT * FROM player_fixture_observations WHERE is_final=1 AND season='2024-25'",db)
    past['known']=pd.to_datetime(past.kickoff_at,utc=True)+pd.Timedelta(hours=4)
    for gw in [24,28,32]:
        prior=json.loads(lzma.decompress((ROOT/f'data_v1_1/raw/season_2024_25_v1/bootstrap/gw{gw-1:02d}.json.xz').read_bytes()));current=json.loads(lzma.decompress((ROOT/f'data_v1_1/raw/season_2024_25_v1/bootstrap/gw{gw:02d}.json.xz').read_bytes()));old={p['id']:p for p in prior['elements']};now={p['id']:p for p in current['elements']};selected=[r for r in receipts if r['season']=='2024-25'and byrecord[r['season'],r['fixture_uuid']]['gw']==gw];chosen=[]
        for fx in sorted({r['fixture_uuid']for r in selected}):chosen.append(min([r for r in selected if r['fixture_uuid']==fx],key=lambda r:r['seed']))
        columns={};minutes={}
        for r in chosen:
            z=np.load(r['samples_file']);array=z['points_minutes']
            for j,pid in enumerate(z['players']):
                fid=uuid_to_id.get(pid)
                if pd.notna(fid)and int(fid)in now:columns[int(fid)]=array[:,j,0];minutes[int(fid)]=array[:,j,1]
        ids=sorted(columns);meta=pd.DataFrame([dict(id=i,web_name=now[i]['web_name'],element_type=now[i]['element_type'],position=POSITIONS[now[i]['element_type']],team=now[i]['team'],price_tenths=now[i]['now_cost'],price=now[i]['now_cost']/10,status=now[i]['status'])for i in ids]);pts=np.array([columns[i]for i in ids]).T;mins=np.array([minutes[i]for i in ids]).T;s=scorer(meta,pts,mins,gw)
        previous_event=prior['events'][gw-2];cut=pd.Timestamp(previous_event['deadline_time']);known=past[past.known.lt(cut)].sort_values('known');rating=known.groupby('player_uuid').tail(3).groupby('player_uuid').total_points.mean();oldmeta=meta[meta.id.isin(old)].copy();oldmeta['price']=[old[i]['now_cost']/10 for i in oldmeta.id];oldmeta['status']=[old[i]['status']for i in oldmeta.id]
        id_to_uuid={int(v):k for k,v in uuid_to_id.items()if pd.notna(v)};initial_projection=pd.DataFrame([dict(id=i,gw=gw-1,xpts_mean=float(rating.get(id_to_uuid.get(i),0)))for i in oldmeta.id]);seed=optimize_squad_milp(initial_projection,oldmeta,[gw-1],budget=100,candidate_limit_per_position=30)
        if not seed['success']:raise ValueError('Historical legal initial squad unavailable')
        owned=set(seed['squad_ids']);purchase={i:old[i]['now_cost']for i in owned};bank=1000-sum(purchase.values());origin=pd.DataFrame([dict(id=i,gw=gw,xpts_mean=s.weeks[i,gw]['xpts'],p_play=float(np.mean(minutes[i]>0)))for i in ids]);pool=set(owned)
        for pos,g in meta.groupby('position'):
            eligible=g[g.status.ne('u')];rank=origin.set_index('id').xpts_mean;pool.update(eligible.id.iloc[np.argsort([-rank[i]for i in eligible.id])[:2]]);pool.update(eligible.nsmallest(2,'price_tenths').id)
        bounded=meta[meta.id.isin(pool)].copy();original_ids=tuple(sorted(owned));lineup=exact_lineup(s,gw,original_ids);heuristic=s.decision(gw,original_ids)
        contexts.append(dict(gw=gw,meta=meta.to_dict('records'),origin=origin.to_dict('records'),points=pts.tolist(),minutes=mins.tolist(),owned=sorted(owned),purchase=purchase,bank=bank))
        for ft in [1,2]:
            state=ReplayState({i:OwnedPlayer(i,purchase[i])for i in owned},bank,ft);start=time.perf_counter();fast=_fast_local_candidate_squads(state,bounded,origin,[gw],[1.],2,100,60,12);fast_choice=best_bundle(fast,state,s,gw);fast_seconds=time.perf_counter()-start;start=time.perf_counter();exact=exact_candidates(state,bounded);exact_choice=best_bundle(exact,state,s,gw);exact_seconds=time.perf_counter()-start;finance=financing_bundles(exact,state,bounded,origin);finance_choice=best_bundle(finance,state,s,gw)if finance else None
            results.append(dict(season='2024-25',gw=gw,FT=ft,bank_tenths=bank,state_source='Model-managed scenario selected from previous-deadline prices and preceding three observed FPL matches; not human manager history',price_clock='Archived predeadline source commit clock; server publication timing not independently verified',horizon=1,universe=len(bounded),exact_squads=len(exact),fast_squads=len(fast),fast_seconds=fast_seconds,exact_seconds=exact_seconds,fast=fast_choice,exact=exact_choice,negative_financing_bundles=len(finance),best_negative_financing=finance_choice,utility_regret=exact_choice['utility']-fast_choice['utility'],expected_net_points_difference=exact_choice['expected_net_points']-fast_choice['expected_net_points'],heuristic_XI_score=heuristic[-1],exact_XI=lineup,XI_gain=lineup['score']-heuristic[-1],parameter_scope='Conditional retrospective 2024: NP head trained later; not OOT policy performance',owned=sorted(owned),purchase_prices=purchase))
        print('Historical bounded TS case GW',gw,flush=True)
    (work/'ts-historical-contexts.json.gz').write_bytes(gzip.compress(json.dumps(contexts).encode(),mtime=0))
    (out/'historical-TS-cases.json').write_text(json.dumps(results,indent=2)+'\n')
    return results


def mc_decisions(work,out):
    inputs=load(work/'current-inputs.json.gz');status_file=work/'decision-player-status.json';status=json.loads(status_file.read_text())if status_file.exists()else{str(p['id']):p['status']for p in json.loads((work/'current-origin/work/current-B-inputs/bootstrap.json').read_text())['elements']};status_file.write_text(json.dumps(status,sort_keys=True)+'\n');meta=pd.DataFrame([dict(id=m['id'],web_name=m['name'],element_type={'GK':1,'DEF':2,'MID':3,'FWD':4}[m['position']],position='GKP'if m['position']=='GK'else m['position'],team=m['team_id'],price_tenths=m['price_tenths'],price=m['price_tenths']/10,status=status[str(m['id'])],uuid=pid)for r in inputs for pid,m in r['meta'].items()]).drop_duplicates('id').sort_values('id').reset_index(drop=True);uuid_to_id=meta.set_index('uuid').id.to_dict();receipts=json.loads((work/'mc/receipts.json').read_text());receipts=[r for r in receipts if r['season']=='2026-27'];gw=inputs[0]['gw'];groups={}
    for fx in sorted({r['fixture_uuid']for r in receipts}):
        group=sorted([r for r in receipts if r['fixture_uuid']==fx],key=lambda r:r['seed'])
        for rep,r in enumerate(group):groups.setdefault(rep,[]).append(r)
    means=pd.read_csv(work/'mc/predictions.csv.gz');means=means[means.season.eq('2026-27')&means.draws.eq(10000)];ratings=means.groupby('id').points.mean();origin=pd.DataFrame([dict(id=i,gw=gw,xpts_mean=float(ratings[i]),p_play=1.)for i in meta.id]);init=optimize_squad_milp(origin,meta,[gw],budget=100,candidate_limit_per_position=30)
    if not init['success']:raise ValueError('MC legal decision-state construction failed')
    owned=set(init['squad_ids']);by=meta.set_index('id');state=ReplayState({i:OwnedPlayer(i,int(by.loc[i,'price_tenths']))for i in owned},1000-int(by.loc[list(owned),'price_tenths'].sum()),1);pool=set(owned)
    for pos,g in meta[meta.status.ne('u')].groupby('position'):pool.update(g.id.iloc[np.argsort([-ratings[i]for i in g.id])[:5]])
    bounded=meta[meta.id.isin(pool)];candidates=exact_candidates(state,bounded,limit=1);rows=[]
    for rep,files in groups.items():
        columns={};mins={}
        for r in files:
            z=np.load(r['samples_file']);data=z['points_minutes']
            for j,pid in enumerate(z['players']):
                if pid in uuid_to_id:columns[uuid_to_id[pid]]=data[:,j,0];mins[uuid_to_id[pid]]=data[:,j,1]
        for n in [400,2000,10000]:
            pts=np.array([columns[i][:n]for i in meta.id]).T;minutes=np.array([mins[i][:n]for i in meta.id]).T;s=scorer(meta,pts,minutes,gw);start=time.perf_counter();choice=best_bundle(candidates,state,s,gw);line=s.decision(gw,tuple(sorted(owned)));rows.append(dict(rep=rep,draws=n,chosen_incoming=sorted(set(choice['ids'])-owned),chosen_outgoing=sorted(owned-set(choice['ids'])),XI=list(line[0]),bench=list(line[1]),captain=line[2],vice=line[3],score=line[-1],transfer_net=choice['expected_net_points'],decision_seconds=time.perf_counter()-start))
        ScenarioScorer.decision.cache_clear();print('MC decision repetition',rep,flush=True)
    (out/'mc-decision-stability.json').write_text(json.dumps(dict(scope='One fixed model-managed current squad; bounded one-transfer pool; 1GW objective, not full six-GW TS policy',state_reference='Mean of six 10000-draw replicates, fixed across all lower-N decisions; not observed player outcomes',candidate_squads=len(candidates),candidate_players=len(bounded),rows=rows),indent=2)+'\n')

def replay_historical(work,out):
    contexts=json.loads(gzip.decompress((work/'ts-historical-contexts.json.gz').read_bytes()));reference=json.loads((out/'historical-TS-cases.json').read_text())
    for c in contexts:
        meta=pd.DataFrame(c['meta']);origin=pd.DataFrame(c['origin']);gw=c['gw'];s=scorer(meta,np.array(c['points']),np.array(c['minutes']),gw);owned=set(c['owned']);pool=set(owned);rank=origin.set_index('id').xpts_mean
        for _,g in meta.groupby('position'):
            g=g[g.status.ne('u')];pool.update(g.id.iloc[np.argsort([-rank[i]for i in g.id])[:2]]);pool.update(g.nsmallest(2,'price_tenths').id)
        bounded=meta[meta.id.isin(pool)];lineup=exact_lineup(s,gw,tuple(sorted(owned)))
        for ft in [1,2]:
            state=ReplayState({i:OwnedPlayer(i,c['purchase'][str(i)])for i in owned},c['bank'],ft);fast=_fast_local_candidate_squads(state,bounded,origin,[gw],[1.],2,100,60,12);exact=exact_candidates(state,bounded);f=best_bundle(fast,state,s,gw);e=best_bundle(exact,state,s,gw);r=next(r for r in reference if r['gw']==gw and r['FT']==ft)
            assert abs(f['utility']-r['fast']['utility'])<1e-12
            assert abs(e['utility']-r['exact']['utility'])<1e-12
            assert abs(lineup['score']-r['exact_XI']['score'])<1e-12
            print('Frozen historical decision replay matches GW',gw,'FT',ft,flush=True)
        ScenarioScorer.decision.cache_clear()


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['historical','historical-frozen','mc'],required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.mode=='historical':historical(a.work,a.out)
    elif a.mode=='historical-frozen':replay_historical(a.work,a.out)
    else:mc_decisions(a.work,a.out)
if __name__=='__main__':main()
