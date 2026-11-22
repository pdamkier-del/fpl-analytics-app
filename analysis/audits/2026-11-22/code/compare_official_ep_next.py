"""Match archived official FPL ep_next against our original forecasts at the same stored cutoff."""
from pathlib import Path
import json,gzip
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];d=pd.read_csv(R/'results/enriched-player-evaluation.csv');rows=[];sources=[]
for gw in [8,9,10]:
 read=lambda n:json.loads(gzip.decompress((R/'inputs/archive'/n).read_bytes()))
 doc=read(f'gw{gw}-existing-app-data.json.gz')['documents']['current-players.json'];f=read(f'gw{gw}-forecast.json.gz')
 assert doc['next_gw']==gw and [e['id']for e in doc['events']if e.get('is_next')]==[gw]
 assert pd.Timestamp(doc['fetched_at'])<=pd.Timestamp(f['data_asof'])<pd.Timestamp(f['origin_deadline'])
 lookup={p['id']:p for p in doc['players']};sources.append({'gw':gw,'official_fetched_at':doc['fetched_at'],'model_cutoff':f['data_asof'],'deadline':f['origin_deadline'],'field':'ep_next','next_gw_confirmed':True})
 for r in d[d.gw==gw].itertuples():
  value=lookup[r.id].get('ep_next');v=pd.to_numeric(value,errors='coerce');assert np.isfinite(v)
  rows.append({'gw':gw,'fixture':r.fixture,'id':r.id,'pstart':r.pstart,'xp':r.xp,'official_ep_next':v,'actual':r.points})
z=pd.DataFrame(rows);assert len(z)==2007;rng=np.random.default_rng(20261122);summaries=[]
for name,g in [('all',z),('active',z[z.pstart>=.2]),('rotation',z[z.pstart.between(.2,.9,inclusive='left')]),('regular',z[z.pstart>=.9]),*[(f'GW{gw}',g)for gw,g in z.groupby('gw')]]:
 e=g.xp-g.actual;other=g.official_ep_next-g.actual;out={'group':name,'rows':len(g),'matches':g.fixture.nunique(),'model_mae':float(abs(e).mean()),'official_mae':float(abs(other).mean()),'model_rmse':float(np.sqrt((e**2).mean())),'official_rmse':float(np.sqrt((other**2).mean())),'model_bias':float(e.mean()),'official_bias':float(other.mean())}
 for metric,delta in [('mae',abs(e)-abs(other)),('mse',e**2-other**2)]:
  blocks=g.assign(delta=delta).groupby('fixture').delta.agg(['sum','count']).to_numpy();ix=rng.integers(0,len(blocks),size=(5000,len(blocks)));b=blocks[ix].sum(axis=1);out[metric+'_delta_CI95']=np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist()
 summaries.append(out)
(R/'results/official-ep-next-benchmark.json').write_text(json.dumps({'source':'Official FPL ep_next captured in each original player catalogue','scope':'Same players and target rounds, same stored source pack; no claim this is each service final predeadline update','sources':sources,'results':summaries,'limits':['Official ep_next is an external simple baseline, not LazyFPL/FPL Review','Point means only; no external point distributions available','Model policy changes across rounds; only three GWs','Fixture bootstrap is exploratory and excludes temporal and policy selection uncertainty'],'production_changed':False},indent=2));z.to_csv(R/'results/official-ep-next-rows.csv',index=False);print(json.dumps(summaries[:4],indent=2))
