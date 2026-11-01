"""Summaries only; no parameter fitting or model activation."""
import argparse,itertools,json,math,sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr,chi2
from precision_audit.dataset import load,ROOT
from b_physical_workload import historical_ledger
from fpl_v1_1_model.role_event_priors import QCOLS


def metrics(g):
    e=g.points-g.total_points
    return dict(rows=len(g),fixtures=int(g.fixture_uuid.nunique()),xp_MAE=float(abs(e).mean()),xp_RMSE=float(np.sqrt((e**2).mean())),xp_bias=float(e.mean()),goal_MAE=float(abs(g.goals-g.actual_goals).mean()),goal_bias=float((g.goals-g.actual_goals).mean()),assist_MAE=float(abs(g.assists-g.actual_assists).mean()),assist_bias=float((g.assists-g.actual_assists).mean()),CS_Brier=float(((g.clean_sheet-g.actual_cs)**2).mean()),CS_bias=float((g.clean_sheet-g.actual_cs).mean()),goal_Brier=float(((g.p_goal-g.actual_goals.ge(1))**2).mean()),assist_Brier=float(((g.p_assist-g.actual_assists.ge(1))**2).mean()))


def labels(records):
    rows=[]
    for r in records:
        for pid,a in r.get('actual',{}).items():
            if pid not in r['meta']:continue
            if a.get('goals_conceded_on_pitch')is None:cs=None
            else:cs=int(a['minutes']>=60 and a['goals_conceded_on_pitch']==0)
            rows.append(dict(season=r['season'],fixture_uuid=r['fixture_uuid'],player_uuid=pid,actual_minutes=a['minutes'],actual_start=a['started'],total_points=a['total_points'],actual_goals=a['goals'],actual_assists=a['fpl_assists'],actual_cs=cs,actual_bonus=a['bonus'],actual_xg=a['xg'],canonical_name=a['canonical_name'],gw=r['gw'],cutoff=r['cutoff']))
    return pd.DataFrame(rows)


def event_calibration(f):
    rows=[]
    for (s,group,value),g in grouped(f):
        for event,pred,target in [('goal','p_goal','actual_goals'),('assist','p_assist','actual_assists'),('clean_sheet','clean_sheet','actual_cs')]:
            actual=g[target].ge(1).astype(float)
            for lo,hi in [(0,.01),(.01,.05),(.05,.1),(.1,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.00001)]:
                ix=g[pred].ge(lo)&g[pred].lt(hi)
                if not ix.any():continue
                rows.append(dict(season=s,group=group,value=str(value),event=event,lower=lo,upper=hi,rows=int(ix.sum()),predicted=float(g.loc[ix,pred].mean()),observed=float(actual[ix].mean()),Brier=float(((g.loc[ix,pred]-actual[ix])**2).mean()),sparse=ix.sum()<50))
    return pd.DataFrame(rows)


def grouped(frame):
    for season,g in frame.groupby('season'):
        yield(season,'all','all'),g
        for column in ['position','playing_role','tactical_role']:
            for value,part in g.groupby(column,dropna=False):yield(season,column,value),part


def annotate(frame,records):
    f=frame.copy();f['playing_role']=np.where(f.analytic_start.ge(.9),'regular',np.where(f.analytic_start.ge(.2),'rotation','reserve'))
    from build_current_b_inputs import historical_B_training
    clinical=historical_B_training()[['season','fixture_uuid','player_uuid','news_medical_out']].drop_duplicates(['season','fixture_uuid','player_uuid'])
    f=f.merge(clinical,on=['season','fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    source={}
    for season,path in [('2024-25','analysis/results/penalty-neutral-sources-20261023/predeadline-roles-2024.csv.gz'),('2025-26','analysis/results/workload-recovered-v4/all_features.csv.gz')]:
        q=pd.read_csv(ROOT/path,low_memory=False)
        for r in q.itertuples():
            values=np.array([getattr(r,c)for c in QCOLS],float)
            source[season,r.fixture_uuid,r.player_uuid]=QCOLS[int(np.nanargmax(values))]if np.isfinite(values).all()and values.sum()>0 else'Not Available'
    f['tactical_role']=[source.get((r.season,r.fixture_uuid,r.player_uuid),'Not Available')for r in f.itertuples()]
    ledger,coverage=historical_ledger(ROOT);past={(s,p):g for(s,p),g in ledger.groupby(['season','player_uuid'])};nonpl=[];uefa=[];cup=[]
    for r in f.itertuples():
        h=past.get((r.season,r.player_uuid));cut=pd.Timestamp(r.cutoff)
        if h is None:nonpl.append(np.nan);uefa.append(np.nan);cup.append(np.nan);continue
        h=h[h.known_at.lt(cut)&h.kickoff.gt(cut-pd.Timedelta(days=7))];nonpl.append(float(h.loc[h.competition.ne('prem'),'minutes'].sum()));uefa.append(float(h.loc[h.competition.isin(['cl','el','conf','conf_qual','champions-league','europa-league','conference-league']),'minutes'].sum()))
    f['observed_nonPL_minutes_7d']=nonpl;f['observed_UEFA_minutes_7d']=uefa;f['observed_domestic_cup_minutes_7d']=np.maximum(0,np.array(nonpl)-np.array(uefa))
    return f,coverage


def baseline(work,out,records):
    raw=pd.read_csv(work/'baseline/predictions.csv.gz');keys=['season','fixture_uuid','player_uuid'];numeric=raw.select_dtypes(include=[np.number]).columns.difference(['gw','team_id','seed','mask','draws','minutes_7d']);mean=raw.groupby(keys)[numeric].mean().reset_index();meta=raw.drop_duplicates(keys)[keys+['position','team_id','prior_type','news_state','return_active','minutes_7d']];f=mean.merge(meta,on=keys,validate='one_to_one').merge(labels(records),on=keys,validate='one_to_one');groups_path=work/'player-predeadline-groups.csv.gz'
    if groups_path.exists():
        f=f.merge(pd.read_csv(groups_path),on=keys,validate='one_to_one');coverage=json.loads((work/'predeadline-group-coverage.json').read_text())
    else:
        f,coverage=annotate(f,records)
        f[keys+['news_medical_out','tactical_role','playing_role','observed_nonPL_minutes_7d','observed_UEFA_minutes_7d','observed_domestic_cup_minutes_7d']].to_csv(groups_path,index=False,compression={'method':'gzip','mtime':0})
        (work/'predeadline-group-coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    f.to_csv(out/'baseline-player-diagnostics.csv.gz',index=False,compression={'method':'gzip','mtime':0});metric=[]
    for(s,kind,value),g in grouped(f):metric.append(dict(season=s,group=kind,value=str(value),**metrics(g)))
    pd.DataFrame(metric).to_csv(out/'baseline-metrics.csv',index=False);event_calibration(f).to_csv(out/'event-calibration.csv',index=False)
    mm=[]
    for season,g in f.groupby('season'):
        groups=[('all',g)]
        for c in ['position','team_id','playing_role','tactical_role']:
            groups.extend((c+'='+str(v),p)for v,p in g.groupby(c))
        groups.extend([('unavailable_all_causes',g[g.news_state.eq('OUT')]),('medical_out',g[g.news_medical_out.eq(True)]),('returning',g[g.return_active.eq(True)]),('high_load_180plus',g[g.minutes_7d.ge(180)]),('nonPL_7d_sourced_subset',g[g.observed_nonPL_minutes_7d.gt(0)]),('UEFA_7d_sourced_subset',g[g.observed_UEFA_minutes_7d.gt(0)]),('domestic_cup_7d_sourced_subset',g[g.observed_domestic_cup_minutes_7d.gt(0)])])
        for name,p in groups:
            if p.empty:continue
            e=p.analytic_minutes-p.actual_minutes
            mm.append(dict(season=season,group=name,rows=len(p),minute_MAE=float(abs(e).mean()),minute_RMSE=float(np.sqrt((e**2).mean())),minute_bias=float(e.mean()),start_Brier=float(((p.analytic_start-p.actual_start)**2).mean()),start_bias=float((p.analytic_start-p.actual_start).mean()),p60_Brier=float(((p.analytic_p60-p.actual_minutes.ge(60))**2).mean()),p60_bias=float((p.analytic_p60-p.actual_minutes.ge(60)).mean()),p90_Brier=float(((p.analytic_p90-p.actual_minutes.eq(90))**2).mean()),p90_bias=float((p.analytic_p90-p.actual_minutes.eq(90)).mean()),sparse=len(p)<100))
    pd.DataFrame(mm).to_csv(out/'minute-error-structure.csv',index=False)
    perplayer=f.groupby(['season','player_uuid','canonical_name','position']).agg(actual_minutes=('actual_minutes','sum'),expected_minutes=('analytic_minutes','sum'),pred_goals=('goals','sum'),actual_goals=('actual_goals','sum'),actual_xg=('actual_xg','sum'),pred_assists=('assists','sum'),actual_assists=('actual_assists','sum'),xp=('points','sum'),points=('total_points','sum'),matches=('fixture_uuid','size')).reset_index();perplayer['pred_G90_per_expected_minute']=90*perplayer.pred_goals/perplayer.expected_minutes.replace(0,np.nan);perplayer['pred_A90_per_expected_minute']=90*perplayer.pred_assists/perplayer.expected_minutes.replace(0,np.nan);perplayer['G90']=90*perplayer.actual_goals/perplayer.actual_minutes.replace(0,np.nan);perplayer['xG90']=90*perplayer.actual_xg/perplayer.actual_minutes.replace(0,np.nan);perplayer.to_csv(out/'individual-season-calibration.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    return f,dict(physical_coverage=coverage,National_team_workload='Not Available: no verified national-team match/player-minute source',medical_out_group='OUT includes possible nonmedical absences; medical_out is separately joined from predeadline clinical flags; no future diagnosis')


def oracle(work,out,records):
    raw=pd.read_csv(work/'oracle/predictions.csv.gz');keys=['season','fixture_uuid','player_uuid','mask'];numbers=['points','goals','assists','clean_sheet','p_goal','p_assist','p60','p90','minutes','bonus'];f=raw.groupby(keys)[numbers].mean().reset_index().merge(labels(records),on=['season','fixture_uuid','player_uuid'],validate='many_to_one');meta=raw.drop_duplicates(keys)[keys+['position','prior_type']];f=f.merge(meta,on=keys,validate='one_to_one');f['playing_role']=f.prior_type;f['tactical_role']='See baseline';results=[];attribution=[];rng=np.random.default_rng(20261101)
    for(season,mask),g in f.groupby(['season','mask']):results.append(dict(season=season,mask=int(mask),**metrics(g)))
    for season,g in f.groupby('season'):
        reference=g[g['mask'].eq(0)].set_index(['fixture_uuid','player_uuid']);err={}
        for mask in range(8):
            p=g[g['mask'].eq(mask)].set_index(['fixture_uuid','player_uuid']).reindex(reference.index);err[mask]=abs(p.points-p.total_points).to_numpy()
        delta={m:err[0]-err[m]for m in range(8)}
        for flag,label in [(1,'M'),(2,'S'),(4,'G')]:
            shap=np.zeros(len(reference))
            others=[x for x in [1,2,4]if x!=flag]
            for bits in itertools.product([0,1],repeat=2):
                mask=sum(x for x,b in zip(others,bits)if b);k=sum(bits);weight=math.factorial(k)*math.factorial(2-k)/math.factorial(3);shap+=weight*(delta[mask|flag]-delta[mask])
            temp=reference.reset_index()[['fixture_uuid']];temp['gain']=shap;blocks=temp.groupby('fixture_uuid').gain.agg(['sum','size']).to_numpy();draw=blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1);attribution.append(dict(season=season,factor=label,Shapley_MAE_reduction=float(shap.mean()),fixture_bootstrap95=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()))
        interaction=float((delta[7]-delta[1]-delta[2]-delta[4]).mean());attribution.append(dict(season=season,factor='joint_minus_sum_singletons',value=interaction,total_MAE_reduction=float(delta[7].mean()),sum_singleton_reductions=float((delta[1]+delta[2]+delta[4]).mean())))
    pd.DataFrame(results).to_csv(out/'oracle-metrics.csv',index=False);(out/'oracle-interactions.json').write_text(json.dumps(attribution,indent=2)+'\n')
    # Seed variation in each intervention is distinct from fixture sampling.
    seed_metrics=[]
    for(s,mask,seed),g in raw.merge(labels(records),on=['season','fixture_uuid','player_uuid'],validate='many_to_one').groupby(['season','mask','seed']):
        seed_metrics.append(dict(season=s,mask=int(mask),seed=int(seed),fixture_uuid=g.fixture_uuid.iloc[0],xp_MAE=float(abs(g.points-g.total_points).mean())))
    pd.DataFrame(seed_metrics).to_csv(out/'oracle-seed-metrics.csv',index=False)
    return results,attribution


def mc(work,out):
    f=pd.read_csv(work/'mc/predictions.csv.gz');keys=['season','fixture_uuid','player_uuid','draws'];g=f.groupby(keys).agg(xp_mean=('points','mean'),xp_SD=('points','std'),within_MCSE=('mcse_points','mean'),goal_SD=('goals','std'),assist_SD=('assists','std'),CS_SD=('clean_sheet','std'),bonus_SD=('bonus','std'),repetitions=('seed','size')).reset_index();g['SD_low95']=g.xp_SD*np.sqrt((g.repetitions-1)/chi2.ppf(.975,g.repetitions-1));g['SD_high95']=g.xp_SD*np.sqrt((g.repetitions-1)/chi2.ppf(.025,g.repetitions-1));g.to_csv(out/'mc-individual-noise.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    cases=f[f.season.eq('2026-27')&f.name.isin(['Penders','E.Le Fée'])].merge(g,on=keys,validate='many_to_one');cases.drop_duplicates(keys)[keys+['name','xp_mean','xp_SD','SD_low95','SD_high95','within_MCSE','goal_SD','assist_SD','CS_SD','bonus_SD']].to_csv(out/'mc-control-cases.csv',index=False)
    ranks=[]
    for n,p in f[f.season.eq('2026-27')].groupby('draws'):
        matrix=p.pivot(index='player_uuid',columns='seed',values='points')
        # Seeds differ by fixture, so map sorted per-fixture repetition order.
        p=p.copy();p['rep']=p.groupby('fixture_uuid').seed.rank(method='dense').astype(int);matrix=p.pivot(index='player_uuid',columns='rep',values='points')
        for a,b in itertools.combinations(matrix.columns,2):
            x=matrix[a];y=matrix[b];ranks.append(dict(draws=int(n),rep_a=int(a),rep_b=int(b),Spearman_all=float(spearmanr(x,y).statistic),top20_overlap=len(set(x.nlargest(20).index)&set(y.nlargest(20).index)),top5_overlap=len(set(x.nlargest(5).index)&set(y.nlargest(5).index)),top_captain_changed=x.idxmax()!=y.idxmax()))
    pd.DataFrame(ranks).to_csv(out/'mc-ranking-stability.csv',index=False)
    receipts=json.loads((work/'mc/receipts.json').read_text());runtime=[]
    for r in receipts:
        for n,t in r['prefix_simulation_seconds'].items():runtime.append(dict(fixture_uuid=r['fixture_uuid'],season=r['season'],seed=r['seed'],draws=int(n),kernel_seconds=r['kernel_seconds'],simulation_seconds=t,process_peak_RSS_KiB=r['process_peak_rss_KiB'],full_10000_observer_array_bytes=r['stored_array_bytes'],memory_scope='Worker total peak with 10000 preallocated observer; not isolated app memory for prefix N'))
    pd.DataFrame(runtime).to_csv(out/'mc-runtime.csv',index=False)
    return g


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--part',choices=['baseline','oracle','mc','all'],default='all');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);r=load(a.work/'historical-inputs.json.gz')
    if a.part in ['baseline','all']:f,scope=baseline(a.work,a.out,r);(a.out/'data-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
    if a.part in ['oracle','all']:oracle(a.work,a.out,r)
    if a.part in ['mc','all']:mc(a.work,a.out)
if __name__=='__main__':main()
