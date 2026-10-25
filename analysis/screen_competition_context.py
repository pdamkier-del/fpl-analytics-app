"""Fixed, prior-label-only physical-context ablation of existing B MM."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from build_current_b_inputs import historical_B_training
from research_europe_rotation import source_frames
from mm_candidate_forecast import infer_B
from research_individual_mm_refinement import NUM,project
from competition_context import context_features,apply_physical_context
from b_chain_contract import duration_pmf

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/competition-context-20261025';KEY=['season','fixture_uuid','player_uuid']


def probability_report(frame):
    bins=[];metrics=[]
    for(season,arm),g in frame.groupby(['season','arm']):
        for cohort,v in {'all':g,'rotation':g[g.baseline_p.between(.2,.85)],'nonpl_context':g[g.context_nonpl_minutes_7d.gt(0)]}.items():
            if not len(v):continue
            for name,pc,yc in [('start','p','y'),('0','p0','zero'),('60','p60','sixty'),('90','p90','full')]:
                p=v[pc].to_numpy();y=v[yc].to_numpy();bucket=np.minimum((p*10).astype(int),9);ece=0.
                for i in range(10):
                    m=bucket==i
                    if m.any():
                        pred=float(p[m].mean());obs=float(y[m].mean());ece+=m.mean()*abs(pred-obs)
                        bins.append(dict(season=season,arm=arm,cohort=cohort,event=name,bin=i,rows=int(m.sum()),predicted=pred,observed=obs))
                clipped=np.clip(p,1e-12,1-1e-12)
                metrics.append(dict(season=season,arm=arm,cohort=cohort,event=name,rows=len(v),brier=float(((p-y)**2).mean()),bias=float((p-y).mean()),log_loss=float(-(y*np.log(clipped)+(1-y)*np.log1p(-clipped)).mean()),ece=ece))
    pd.DataFrame(bins).to_csv(OUT/'reliability.csv',index=False);pd.DataFrame(metrics).to_csv(OUT/'probability-metrics.csv',index=False)


def main():
    protocol=json.loads((OUT/'protocol.json').read_text());h=historical_B_training();saved,core,events=source_frames()
    for c in ['cutoff','known_at']:h[c]=pd.to_datetime(h[c],utc=True,format='mixed')
    pl=core[core.season.isin(h.season.unique())][['season','fixture_uuid','player_uuid','club','kickoff_at','known_at','minutes','started']].rename(columns={'fixture_uuid':'match_id','kickoff_at':'kickoff'});pl['competition']='Premier League'
    cups=events[events.competition.ne('Premier League')&events.season.isin(h.season.unique())].reindex(columns=pl.columns)
    all_events=pd.concat([pl,cups],ignore_index=True)
    names=core[['season','team_id','club']].drop_duplicates();target=h[KEY+['team_id','cutoff']].merge(names,on=['season','team_id'],validate='many_to_one')
    context=context_features(target,all_events);context.to_csv(OUT/'context.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    candidate=apply_physical_context(h,context);rows=[];fits=[];maxerror=0.
    expected=saved.set_index(KEY)
    for n,(cut,index)in enumerate(h.groupby('cutoff',sort=True).groups.items()):
        ix=list(index);past=h.known_at.lt(cut);train=h[past];provenance=dict(upstream_variant='role_chance_return_duration',source_manifest_sha256='fixed-reused-research-inputs',features=NUM)
        for arm,data in [('baseline',h),('candidate',candidate)]:
            eligible=data.loc[past,'p'].between(1e-12,1-1e-12)
            if eligible.sum()<200 or data.loc[past].loc[eligible,'y'].nunique()<2:pred=project(data.loc[ix].copy());fit={'training_rows':int(eligible.sum())}
            else:pred,fit=infer_B(data[past],data.loc[ix].drop(columns=['y','minutes']),provenance)
            if arm=='baseline':
                ref=expected.reindex(pd.MultiIndex.from_frame(pred[KEY]));error=float(abs(pred.p.to_numpy()-ref.p.to_numpy()).max());maxerror=max(maxerror,error)
                if error>1e-6:raise ValueError(f'Baseline reproduction failed at {cut}: {error}')
            fits.append(dict(cutoff=cut.isoformat(),arm=arm,training_rows=fit['training_rows'],max_label_known_at=str(train.known_at.max())if len(train)else None))
            scored=pred.copy();scored['arm']=arm;scored['y']=h.loc[ix,'y'].to_numpy();scored['minutes']=h.loc[ix,'minutes'].to_numpy()
            if len(scored):rows.append(scored)
        print('MM context origin',n+1,str(cut),flush=True)
    scored=pd.concat(rows,ignore_index=True).merge(context[KEY+['context_nonpl_minutes_7d','context_missing_minutes_14d','context_role_start_share_change']],on=KEY,validate='many_to_one')
    scored=scored[scored.gw.between(22,38)].copy()
    scored['baseline_p']=expected.reindex(pd.MultiIndex.from_frame(scored[KEY])).p.to_numpy()
    metrics=[];pmfs={}
    for r in scored.itertuples():
        for mu,sigma in [(r.s,10.),(r.c,7.)]:
            if(mu,sigma)not in pmfs:pmfs[mu,sigma]=duration_pmf(mu,sigma)
    masses=np.asarray([r.p*pmfs[r.s,10.]+(1-r.p)*r.q*pmfs[r.c,7.] for r in scored.itertuples()]);scored['p0']=1-masses[:,1:].sum(axis=1);scored['p60']=masses[:,60:].sum(axis=1);scored['p90']=masses[:,90];scored['zero']=scored.minutes.eq(0).astype(int);scored['sixty']=scored.minutes.ge(60).astype(int);scored['full']=scored.minutes.eq(90).astype(int)
    for(season,arm),g in scored.groupby(['season','arm']):
        for cohort,v in {'all':g,'rotation':g[g.baseline_p.between(.2,.85)],'nonpl_context':g[g.context_nonpl_minutes_7d.gt(0)]}.items():
            if len(v):metrics.append(dict(season=season,arm=arm,cohort=cohort,rows=len(v),start_brier=float(((v.p-v.y)**2).mean()),minute_mae=float(abs(v.x-v.minutes).mean()),minute_bias=float((v.x-v.minutes).mean())))
    metric=pd.DataFrame(metrics);metric.to_csv(OUT/'metrics.csv',index=False);probability_report(scored)
    scored.to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.DataFrame(fits).to_csv(OUT/'fit-clocks.csv',index=False)
    checks=[];gates=protocol['gates']
    for season in sorted(scored.season.unique()):
        g=metric[metric.season.eq(season)&metric.cohort.eq('all')].set_index('arm');b,c=g.loc['baseline'],g.loc['candidate']
        check=dict(season=season,start_brier_delta=float(c.start_brier-b.start_brier),minute_mae_delta=float(c.minute_mae-b.minute_mae),absolute_minute_bias_delta=float(abs(c.minute_bias)-abs(b.minute_bias)))
        # Rotation must use the SAME baseline-defined cohort in both arms.
        a=scored[scored.season.eq(season)&scored.arm.eq('baseline')];crows=scored[scored.season.eq(season)&scored.arm.eq('candidate')];ids=a.loc[a.p.between(.2,.85),KEY];br=a.merge(ids,on=KEY,validate='one_to_one');cr=crows.merge(ids,on=KEY,validate='one_to_one')
        check['rotation_minute_mae_delta']=float(abs(cr.x-cr.minutes).mean()-abs(br.x-br.minutes).mean())
        check['passed']=bool(check['start_brier_delta']<=gates['max_start_brier_increase_each_season'] and check['minute_mae_delta']<=gates['max_minute_mae_increase_each_season'] and check['absolute_minute_bias_delta']<=gates['max_absolute_minute_bias_increase_each_season'] and check['rotation_minute_mae_delta']<=gates['max_rotation_minute_mae_increase_each_season']);checks.append(check)
    decision=dict(numerical_MM_gate_passed=all(c['passed']for c in checks),baseline_max_p_error=maxerror,checks=checks,activated=False,production_changed=False,independent_certification=False,coverage_complete=False,source_clock_type='historical kickoff+3/4h and audited recovered availability proxies; not observed historical ingestion',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),protocol_sha256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest())
    (OUT/'decision.json').write_text(json.dumps(decision,indent=2)+'\n');print(metric.to_string(index=False));print(json.dumps(decision,indent=2))

if __name__=='__main__':main()
