#!/usr/bin/env python3
"""Completed-replay diagnostics. No gate selection or retuning on evaluation."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from research_dynamic_pm_v2 import OUT,records,evaluate
from research_player_pm_v2 import save
from replay_pm_conversion import paired_ci
from postprocess_player_pm_v2 import error_attribution
from experiment_mm_pm import POINT_COMPONENTS
from fpl_v1_1_model.experimental_pm_conversion import poisson_deviance


def load(season,mm,layout,kind):
    paths=[OUT/f'{season}_{mm}_{layout}_{i}_{kind}.csv.gz'for i in range(6)]
    p=pd.concat([pd.read_csv(x)for x in paths],ignore_index=True)
    if season=='2024-25':p=p[p.gw.ge(22)].copy()
    return p


def point_losses(p):
    q=p.copy();q['point_abs_error']=abs(q.xp-q.total_points);q['point_squared_error']=(q.xp-q.total_points)**2
    q['bonus_abs_error']=abs(q.expected_bonus-q.bonus);q['goal_abs_error']=abs(q.goal_mu-q.goals);q['assist_abs_error']=abs(q.assist_mu-q.fpl_assists)
    return q


def compare_teams(t,reference='fixed'):
    result={};rng=np.random.default_rng(20261015)
    ref=t[t['mode'].eq(reference)]
    for mode,g in t.groupby('mode'):
        pair=g.merge(ref,on=['fixture_uuid','team_id'],validate='one_to_one',suffixes=('','_base'));v={}
        for outcome,pred in [('xg','xg_pred'),('goals','goal_pred')]:
            y=pair[outcome].to_numpy();a=pair[pred].to_numpy();b=pair[pred+'_base'].to_numpy()
            arrays=dict(mae=np.c_[abs(a-y),abs(b-y)],rmse=np.c_[(a-y)**2,(b-y)**2],poisson_deviance=np.c_[poisson_deviance(y,np.maximum(a,1e-12)),poisson_deviance(y,np.maximum(b,1e-12))])
            v[outcome]={}
            for key,loss in arrays.items():
                f=pd.DataFrame(dict(fixture=pair.fixture_uuid,a=loss[:,0],b=loss[:,1],n=1)).groupby('fixture').sum().to_numpy();boot=f[rng.integers(len(f),size=(2000,len(f)))].sum(1);aa=boot[:,0]/boot[:,2];bb=boot[:,1]/boot[:,2]
                estimate=loss.mean(0)
                if key=='rmse':aa=np.sqrt(aa);bb=np.sqrt(bb);estimate=np.sqrt(estimate)
                v[outcome][key]=dict(value=float(estimate[0]),delta=float(estimate[0]-estimate[1]),fixture_bootstrap_95_ci=np.quantile(aa-bb,[.025,.975]).tolist())
        result[mode]=dict(sides=len(pair),**v)
    return result


def diagnose():
    protocol=json.loads((OUT/'selection.json').read_text());chosen=protocol['selected'];result={};hashes={}
    for mm in ['locked','mm']:
        features=pd.read_csv(OUT/f'{mm}_features.csv.gz');w=pd.read_csv(OUT/f'{mm}_weights.csv.gz')
        dev=features[features.season.eq('2024-25')&features.gw.le(21)]
        thresholds={k:float(dev[k].median())for k in ['log_minutes','relative_variance','lineup_change','stability','disagreement']}
        for season in ['2024-25','2025-26']:
            f=features[features.season.eq(season)&(features.gw.ge(22)if season=='2024-25'else True)].copy();groups={}
            for name,k in [('history','log_minutes'),('uncertainty','relative_variance'),('lineup_change','lineup_change'),('team_instability','stability'),('endpoint_disagreement','disagreement')]:f[name]=np.where(f[k]>thresholds[k],'high','low')
            for name,k in [('new_players','new_fraction'),('club_moves','club_fraction'),('role_moves','role_fraction'),('absence_return_proxy','return_proxy')]:f[name]=np.where(f[k]>0,'present','absent')
            groupcols=['history','uncertainty','lineup_change','team_instability','endpoint_disagreement','new_players','club_moves','role_moves','absence_return_proxy']
            endpoint={}
            for name in ['all']+groupcols:
                endpoint[name]={}
                for label,g in [('all',f)]if name=='all'else f.groupby(name):
                    ep=g.player_xg-g.xg;et=g.team_xg-g.xg;d=g.player_xg-g.team_xg;den=float((d*d).mean());cross=float((ep*et).mean())
                    endpoint[name][str(label)]=dict(sides=len(g),player_mae=float(abs(ep).mean()),team_endpoint_mae=float(abs(et).mean()),original_anchor_mae=float(abs(g.original_team_xg-g.xg).mean()),player_mse=float((ep*ep).mean()),team_mse=float((et*et).mean()),error_cross=cross,residual_correlation=float(np.corrcoef(ep,et)[0,1])if len(g)>1 else None,conditional_profile_variance=float(g.profile_variance.mean()),residual_to_profile_variance=float((ep*ep).mean()/g.profile_variance.mean())if g.profile_variance.mean()>0 else None,hindsight_diagnostic_weight=float(np.clip(-(et*d).mean()/den,0,1))if den>1e-12 else None,warning='Hindsight weight is diagnostic ONLY, never used to predict; conditional profile variance is not total predictive variance')
            layouts=['independent','legal']if mm=='locked'else ['legal'];arms={}
            for layout in layouts:
                p=point_losses(load(season,mm,layout,'predictions'));t=load(season,mm,layout,'teams');joined=p.merge(f[['fixture_uuid','team_id']+groupcols],on=['fixture_uuid','team_id'],validate='many_to_one');tg=t.merge(f[['fixture_uuid','team_id']+groupcols],on=['fixture_uuid','team_id'],validate='many_to_one')
                for col in groupcols:
                    groups[col]={str(k):dict(sides=int(tg[tg[col].eq(k)][['fixture_uuid','team_id']].drop_duplicates().shape[0]),points={mode:dict(rows=len(g),mae=float(g.point_abs_error.mean()),rmse=float(np.sqrt(g.point_squared_error.mean())),cs_brier=float(g.cs_brier.mean()),bonus_mae=float(g.bonus_abs_error.mean()))for mode,g in v.groupby('mode')},delta_mae_vs_fixed=paired_ci(v,'point_abs_error','fixed'),teams=compare_teams(tg[tg[col].eq(k)]))for k,v in joined.groupby(col)}
                ref=p[p['mode'].eq('fixed')];v=p[p['mode'].eq(chosen)].merge(ref,on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_base'));d=v[POINT_COMPONENTS].to_numpy()-v[[k+'_base'for k in POINT_COMPONENTS]].to_numpy()
                if not np.allclose(d.sum(1),v.xp-v.xp_base,atol=1e-10):raise ValueError('Attribution component mismatch')
                ww=w[w.fixture_uuid.isin(f.fixture_uuid)]
                arms[layout]=dict(team_comparisons_vs_fixed=compare_teams(t),paired_vs_fixed={k:paired_ci(p,k,'fixed')for k in ['point_abs_error','point_squared_error','bonus_abs_error','goal_abs_error','assist_abs_error','cs_brier','gc_abs_error']},groups=copy.deepcopy(groups),selected_error_attribution_vs_fixed=error_attribution(v.xp_base-v.total_points,d),weight_distribution={m:dict(sides=len(g),mean=float(g.w.mean()),quantiles=g.w.quantile([0,.1,.5,.9,1]).to_dict(),fallbacks=int(g.get('fallback',pd.Series(index=g.index,dtype=str)).notna().sum()))for m,g in ww.groupby('mode')})
            if mm=='locked':
                a=point_losses(load(season,mm,'independent','predictions'));b=point_losses(load(season,mm,'legal','predictions'));a['mode']='independent_'+a['mode'];b['mode']='legal_'+b['mode'];ab=pd.concat([a,b]);xi={}
                for ref in ['independent_original','independent_fixed']:
                    xi[ref]={k:paired_ci(ab,k,ref)for k in ['point_abs_error','point_squared_error','cs_brier','bonus_abs_error']}
            else:xi=None
            result[season+'_'+mm]=dict(development_median_thresholds=thresholds,endpoint_errors=endpoint,arms=arms,xi_only=xi)
    for p in sorted(OUT.glob('*.csv.gz')):hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    save(OUT/'reliability_report.json',dict(classification='COMPLETED_DYNAMIC_PM_V2_DIAGNOSIS_NOT_RETUNED',results=result,source_sha256=hashes,limitations=protocol['limitations'],locked_model_active=False,promotion_allowed=False))
    print('Reliability/error decomposition saved',flush=True)


def monte_carlo():
    """First two later fixtures per season/MM; seeds NOT selected by errors."""
    protocol=json.loads((OUT/'selection.json').read_text());chosen=protocol['selected'];rows=[]
    for season in ['2024-25','2025-26']:
        for mm in ['locked','mm']:
            rs=[r for r in records(season,mm)if season!='2024-25'or r['origin']>=22][:2];weights=pd.read_csv(OUT/f'{mm}_weights.csv.gz').set_index(['fixture_uuid','mode','team_id']).w
            for r in rs:
                ww={m:{str(t):float(weights.loc[(r['core_fixture'],m,int(t))])for t in [r['candidates']['original']['input']['home_team'],r['candidates']['original']['input']['away_team']]}for m in protocol['chosen']}
                for seed in range(6):
                    rr=copy.deepcopy(r);rr['seed']=202610150+seed
                    # mm flag only controls mode count and hazards in evaluate. Keep
                    # all locked legal families: identical mechanism, not retuned.
                    value=evaluate((rr,ww,'legal',mm,chosen,str(OUT/'mc-cache'),{'mc_seed':seed}))
                    for row in value['rows']:rows.append(dict(season=season,mm=mm,seed=seed,**row))
                    print('MC',season,mm,r['core_fixture'],seed,flush=True)
    p=pd.DataFrame(rows);truth=pd.concat([load(s,m,'legal','predictions')[['fixture_uuid','player_uuid','total_points']].drop_duplicates()for s in ['2024-25','2025-26']for m in ['locked','mm']]).drop_duplicates();p=p.merge(truth,on=['fixture_uuid','player_uuid'],validate='many_to_one');p['loss']=abs(p.xp-p.total_points);values={}
    for (s,m),f in p.groupby(['season','mm']):
        ref=f[f['mode'].eq('fixed')];v={}
        for mode,g in f.groupby('mode'):
            pairs=g.merge(ref,on=['fixture_uuid','player_uuid','seed'],validate='one_to_one',suffixes=('','_ref'));d=pairs.assign(delta=pairs.loss-pairs.loss_ref).groupby('seed').delta.mean();v[mode]=dict(mean_mae_delta=float(d.mean()),seed_sd=float(d.std(ddof=1)),seed_range=[float(d.min()),float(d.max())],seeds=len(d))
        values[s+'_'+m]=v
    save(OUT/'monte_carlo_report.json',dict(results=values,design='First two evaluation fixtures/season/MM, six independent common seeds,400 draws per arm; seed dispersion conditional on selected fixtures, NOT a sampling CI or whole-season robustness test',locked_model_active=False))


def export():
    for p in sorted(OUT.glob('*.json')):
        if p.name.endswith('_completion.json'):continue
        print(json.dumps(dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),report=json.loads(p.read_text())),indent=2))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--stage',choices=['diagnose','mc','export'],required=True);args=a.parse_args()
    {'diagnose':diagnose,'mc':monte_carlo,'export':export}[args.stage]()
