#!/usr/bin/env python3
"""Execute the real frozen MM -> common contract -> historical app preview.

No PM/TS code, no source collection and no alteration of production forecasts.
Only the already selected PR9 B and PR13 sigma30 are used. No evaluation tuning.
"""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame
from archive_role_injury_mm import restore
from mm_candidate import KEY, VERSION, CONTRACT, FormationSelector, build_contract, minute_masses, intervals
from validate_mm_all_clubs import temporal_ci
from research_mm_predictive_distribution import score

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'analysis/results/individual-mm-refinement-20261016'
OUT=ROOT/'analysis/results/mm-integration-preview-20261017'
APP=ROOT/'app/mm-preview'
HISTORY=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(obj),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')


def summary(g):
    ae=(g.x-g.minutes).abs();prob=np.clip(g.p,1e-12,1-1e-12)
    return dict(n=len(g),mae=ae.mean(),rmse=np.sqrt(np.mean((g.x-g.minutes)**2)),bias=(g.x-g.minutes).mean(),start_brier=np.mean((g.p-g.y)**2),start_logloss=np.mean(-g.y*np.log(prob)-(1-g.y)*np.log1p(-prob)),median=ae.median(),p90=ae.quantile(.9),p95=ae.quantile(.95),p99=ae.quantile(.99),over60=int(ae.gt(60).sum()),top5_error_share=ae.nlargest(int(np.ceil(.05*len(g)))).sum()/ae.sum(),top10_error_share=ae.nlargest(int(np.ceil(.1*len(g)))).sum()/ae.sum())


def main():
    OUT.mkdir(parents=True,exist_ok=True);(APP/'data').mkdir(parents=True,exist_ok=True)
    f=load_frame(SOURCE/'predictions.npz')
    mask=((f.season=='2024-25')&f.gw.between(22,38))|((f.season=='2025-26')&f.gw.between(6,38))
    f=f[mask & f['mode'].isin(['original','best_existing','B'])].copy()
    keys=f[f['mode']=='B'][KEY].sort_values(KEY).reset_index(drop=True)
    for mode,g in f.groupby('mode'):
        pd.testing.assert_frame_equal(keys,g[KEY].sort_values(KEY).reset_index(drop=True))
    if len(keys)!=39264:raise ValueError('Frozen cohort changed')
    cap=ROOT/'work/mm-integration-source'
    if not (cap/'mm-source/2025-26_candidates.npz').exists():restore(cap)
    coarse=pd.concat([load_frame(cap/'mm-source'/(s+'_candidates.npz')) for s in ['2024-25','2025-26']])
    coarse=coarse[coarse['mode']=='original'][KEY+['pos']]
    if coarse.duplicated(KEY).any():raise ValueError('Ambiguous historical position')
    f=f.merge(coarse,on=KEY,validate='many_to_one')
    features=pd.read_csv(SOURCE/'prior_only_features.csv.gz',float_precision='round_trip')
    add=[c for c in features if c not in f or c in KEY]
    f=f.merge(features[add],on=KEY,validate='many_to_one')
    ledger=pd.read_csv(HISTORY,low_memory=False);ledger['season']='2025-26'
    selector=FormationSelector(ledger)
    named=ledger[['player_uuid','player']].drop_duplicates('player_uuid').set_index('player_uuid').player.to_dict()
    clubs=pd.read_csv(SOURCE/'club_metrics.csv')[['season','team_id','club']].drop_duplicates()
    clubnames={(r.season,int(r.team_id)):r.club for r in clubs.itertuples()}
    b=f[f['mode']=='B'].sort_values(KEY).reset_index(drop=True)
    for col in ['p','q','s','c','x']:
        if not np.isfinite(b[col]).all():raise ValueError('Nonfinite B')
    # All common-pipeline arms go through build_contract, including mean check.
    snapshots=[];contract_rows=[];xi=[];assignment_rows=[];uncertainty=[];bands=[]
    source_hash=sha(SOURCE/'predictions.npz');all_expected=0
    for (season,gw),g in b.groupby(['season','gw'],sort=True):
        # Preview timestamps are historical model cutoffs, never current time.
        doc=build_contract(g,selector,scope='historical_replay',source_hash=source_hash,model_data_at=str(g.cutoff.iloc[0]))
        if not np.array_equal(np.array([r['p_start'] for r in sorted(doc['players'],key=lambda r:(r['fixture_id'],r['player_id']))]),g.sort_values(['fixture_uuid','player_uuid']).p.to_numpy()):
            raise ValueError('Contract changed B marginal probability')
        truth=g.set_index(['fixture_uuid','player_uuid'])
        for r in doc['players']:
            r['name']=named.get(r['player_id'],r['player_id'])
            r['club']=clubnames[(season,r['club_id'])]
            observed=truth.loc[(r['fixture_id'],r['player_id'])]
            r['observed_minutes']=float(observed.minutes)
            r['observed_start']=bool(observed.y)
            contract_rows.append({k:v for k,v in r.items() if k not in ['minute_pmf','role_probabilities']})
        for team in doc['teams']:
            gg=g[g.fixture_uuid.eq(team['fixture_id'])&g.team_id.eq(team['club_id'])]
            rr=[r for r in doc['players'] if r['fixture_id']==team['fixture_id'] and r['club_id']==team['club_id']]
            chosen=[r for r in rr if r['expected_xi']]
            if chosen:
                if len(chosen)!=11 or sum(r['slot']=='GK' for r in chosen)!=1:raise ValueError('Illegal XI')
                if any(r['p_start']==0 for r in chosen):raise ValueError('Hard-zero selected')
                all_expected+=1
                for r in chosen:assignment_rows.append(dict(season=season,gw=int(gw),fixture_uuid=team['fixture_id'],team_id=team['club_id'],player_uuid=r['player_id'],slot=r['slot'],formation=r['formation']))
                target=ledger[ledger.fixture_uuid.eq(team['fixture_id'])&ledger.team_id.eq(team['club_id'])]
                actual_formation=str(target.formation.iloc[0]) if len(target)==11 and target.formation.nunique()==1 else None
                # Actual formation/slot is evaluation only; it never enters selector.
                actual_roles=target.set_index('player_uuid').final_role.to_dict()
                hit=sum(r['observed_start'] for r in chosen)
                xi.append(dict(season=season,gw=int(gw),fixture_uuid=team['fixture_id'],team_id=team['club_id'],mode='combined',correct=hit,formation=team['formation'],actual_formation=actual_formation,formation_correct=(team['formation']==actual_formation) if actual_formation else None,exact_role_hits=sum(actual_roles.get(r['player_id'])==r['slot'] for r in chosen)))
                for mode in ['original','best_existing','B']:
                    old=f[f['mode'].eq(mode)&f.season.eq(season)&f.fixture_uuid.eq(team['fixture_id'])&f.team_id.eq(team['club_id'])]
                    raw=old.sort_values(['p','player_uuid'],ascending=[False,True]).head(11)
                    xi.append(dict(season=season,gw=int(gw),fixture_uuid=team['fixture_id'],team_id=team['club_id'],mode=mode,correct=int(raw.y.sum()),formation=None,actual_formation=actual_formation,formation_correct=None,exact_role_hits=None))
        # Content hash after presentation-only names/truth are added.
        doc['content_sha256']=hashlib.sha256(json.dumps({k:v for k,v in doc.items() if k!='content_sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        blob=json.dumps(doc,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        packed=gzip.compress(blob,mtime=0)
        name=f'{season}-gw{int(gw):02d}.json.gz';(APP/'data'/name).write_bytes(packed)
        snapshots.append(dict(season=season,gw=int(gw),cutoff=str(g.cutoff.iloc[0]),rows=len(g),url='data/'+name,sha256=hashlib.sha256(packed).hexdigest()))
        for start in range(0,len(g),512):
            chunk=g.iloc[start:start+512];mass=minute_masses(chunk)
            crps,ll,*_=score(mass,chunk.minutes.to_numpy())
            vals=chunk[KEY+['gw','team_id','prior_type','history_n','news_state','return_active','return_prior_games']].copy().reset_index(drop=True)
            vals['crps']=crps;vals['logloss']=ll;vals['mean_residual']=mass@np.arange(91)-chunk.x.to_numpy()
            vals['p0']=mass[:,0];vals['observed0']=chunk.minutes.eq(0).to_numpy()
            for level in [.5,.8,.9]:
                for method in ['central','shortest']:
                    lo,hi=intervals(mass,level,method);y=chunk.minutes.to_numpy();label=f'{method}{int(level*100)}'
                    vals[label+'_inside']=(y>=lo)&(y<=hi);vals[label+'_width']=hi-lo
                    vals[label+'_model_mass']=np.array([mass[i,l:h+1].sum() for i,(l,h) in enumerate(zip(lo,hi))])
            uncertainty.append(vals)
            for label,probs,actual in [('0',mass[:,0],chunk.minutes.eq(0)),('1-15',mass[:,1:16].sum(axis=1),chunk.minutes.between(1,15)),('16-60',mass[:,16:61].sum(axis=1),chunk.minutes.between(16,60)),('61-90',mass[:,61:].sum(axis=1),chunk.minutes.between(61,90))]:
                bands.append(pd.DataFrame(dict(season=season,gw=int(gw),role=chunk.prior_type.to_numpy(),band=label,probability=probs,actual=np.asarray(actual,int))))
        print('Executed common MM contract',season,int(gw),len(g),flush=True)
    pd.DataFrame(contract_rows).to_csv(OUT/'contract_rows.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    xx=pd.DataFrame(xi);xx.to_csv(OUT/'xi_comparison.csv',index=False)
    pd.DataFrame(assignment_rows).to_csv(OUT/'xi_assignments.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    xx.groupby(['mode','correct']).size().rename('count').reset_index().to_csv(OUT/'xi_hit_distribution.csv',index=False)
    uu=pd.concat(uncertainty,ignore_index=True);uu.to_csv(OUT/'uncertainty_rows.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    numeric=['crps','logloss','p0','observed0']+[c for c in uu if c.endswith(('_inside','_width','_model_mass'))]
    us=[]
    for season,sub in [('ALL',uu)]+list(uu.groupby('season')):
        for role,gg in [('ALL',sub)]+list(sub.groupby('prior_type')):
            us.append(dict(season=season,role=role,n=len(gg),**gg[numeric].mean().to_dict()))
    pd.DataFrame(us).to_csv(OUT/'uncertainty_summary.csv',index=False)
    bb=pd.concat(bands,ignore_index=True)
    bb.groupby(['season','role','band']).agg(n=('actual','size'),predicted=('probability','mean'),observed=('actual','mean'),brier=('probability',lambda x:0.)).drop(columns='brier').reset_index().to_csv(OUT/'minute_band_calibration.csv',index=False)
    metrics=[];errors=[];cal=[];interval_rows=[]
    allarms={k:g.copy() for k,g in f.groupby('mode')}
    for k in ['B_XI','B_PMF','combined']:allarms[k]=b.copy()
    for mode,g in allarms.items():
        g['abs_error']=(g.x-g.minutes).abs()
        for season,sg in [('ALL',g)]+list(g.groupby('season')):
            metrics.append(dict(mode=mode,season=season,club='ALL',group='ALL',**summary(sg)))
            if season!='ALL':
                for team,tg in sg.groupby('team_id'):metrics.append(dict(mode=mode,season=season,club=clubnames[(season,int(team))],group='ALL',**summary(tg)))
            groups={role:sg.prior_type.eq(role) for role in sg.prior_type.unique()}
            groups['limited_history']=sg.history_n.lt(3)
            groups['documented_return']=sg.return_active.eq(True)
            groups['OUT']=sg.news_state.eq('OUT');groups['SUSPENDED']=sg.news_state.eq('SUSPENDED')
            for label,mask in groups.items():
                if mask.any():metrics.append(dict(mode=mode,season=season,club='ALL',group=label,**summary(sg[mask])))
        for low,high,label in [(-1,5,'0-5'),(5,15,'5-15'),(15,30,'15-30'),(30,60,'30-60'),(60,91,'over60')]:
            mask=g.abs_error.gt(low)&g.abs_error.le(high);errors.append(dict(mode=mode,band=label,n=int(mask.sum()),share=mask.mean(),error_share=g.loc[mask,'abs_error'].sum()/g.abs_error.sum()))
        for role,sg in [('ALL',g)]+list(g.groupby('prior_type')):
            for bin in range(10):
                h=sg[np.minimum((sg.p*10).astype(int),9)==bin]
                if len(h):cal.append(dict(mode=mode,role=role,bin=bin,n=len(h),predicted=h.p.mean(),observed=h.y.mean()))
        if mode in ['original','best_existing','B']:
            g.sort_values('abs_error',ascending=False).head(100).to_csv(OUT/(mode+'_top100.csv'),index=False)
    pd.DataFrame(metrics).to_csv(OUT/'metrics.csv',index=False)
    pd.DataFrame(errors).to_csv(OUT/'error_bands.csv',index=False)
    pd.DataFrame(cal).to_csv(OUT/'start_calibration.csv',index=False)
    for season,sg in b.groupby('season'):
        reference=f[f['mode'].eq('best_existing')&f.season.eq(season)].sort_values(KEY).reset_index(drop=True)
        ci=temporal_ci(sg.reset_index(drop=True),reference,range(22 if season=='2024-25' else 6,39))
        interval_rows.append(dict(season=season,comparison='combined - best_existing',result=ci))
    save(OUT/'paired_intervals.json',interval_rows)
    old=pd.read_csv(ROOT/'analysis/results/mm-predictive-distribution-20261017/distributions.csv.gz')
    old=old[old['mode']=='role_dependent']
    comparable=uu.merge(old[KEY+['crps','logloss']],on=KEY,validate='one_to_one',suffixes=('_new','_old'))
    overall_u=uu[numeric].mean().to_dict()
    decision=dict(status='PREVIEW READY – NOT YET CERTIFIED',model_version=VERSION,contract=CONTRACT,evaluation_rows=len(b),club_seasons=int(b[['season','team_id']].drop_duplicates().shape[0]),legal_xi_team_fixtures=all_expected,mean_max_abs_residual=float(uu.mean_residual.abs().max()),crps_vs_pr13_delta=float((comparable.crps_new-comparable.crps_old).mean()),logloss_vs_pr13_delta=float((comparable.logloss_new-comparable.logloss_old).mean()),uncertainty=overall_u,production_changed=False,locked_model_active=False,independent_holdout_available=False,live_B_forecast_available=False,forecast_arms=['original','best_existing','B','B_XI','B_PMF','combined'],point_forecast_invariance='B == B_XI == B_PMF == combined for every p/q/s/c/x',blockers=['No untouched independently validated MM evaluation period','Historical label/role availability uses kickoff+3/4h proxies','35 historical applicable hard-source contradictions retained, never softened','Three prior B club-risk flags remain; no posthoc per-club switch','Distribution remains experimental; interval mass/discreteness explicitly reported','Equivalent classified formation ledger for 2024/25 unavailable','Fresh current-season B feature/provenance bridge is not verified; current recommendations Not Available'],references={str(n):'https://github.com/pdamkier-del/fpl-analytics-app/pull/'+str(n) for n in [4,8,9,10,11,12,13,14]})
    save(OUT/'decision.json',decision)
    save(APP/'index.json',dict(**decision,snapshots=snapshots,generated_from=source_hash,clubs=[dict(season=k[0],id=k[1],name=v) for k,v in sorted(clubnames.items())]))
    save(OUT/'manifest.json',dict(model_version=VERSION,inputs={str(p.relative_to(ROOT)):sha(p) for p in [SOURCE/'predictions.npz',SOURCE/'prior_only_features.csv.gz',HISTORY]},outputs={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json'},app_payloads={str(p.relative_to(APP)):sha(p) for p in sorted((APP/'data').glob('*.gz'))}))
    print(json.dumps(clean(decision),indent=2))


if __name__=='__main__':main()
