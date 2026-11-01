"""Independent uncertainty, conservation and component summaries."""
import argparse,copy,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from precision_audit.dataset import load
from precision_audit.report import metrics,labels
from precision_audit.runner import run
from gk_joint_bridge import marginals

def bootstrap(frame,columns,seed=20261101):
    rng=np.random.default_rng(seed);blocks=frame.groupby('fixture_uuid')[columns].agg(['sum','count']);result={}
    for c in columns:
        b=blocks[c].to_numpy();s=b[rng.integers(len(b),size=(4000,len(b)))].sum(axis=1);values=s[:,0]/s[:,1]
        result[c]=dict(mean=float(frame[c].mean()),fixture_bootstrap95=np.quantile(values,[.025,.975]).tolist())
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();w=a.work;o=a.out
    current=load(w/'current-inputs.json.gz');forecast=json.loads((w/'current-forecast.json').read_text());r=current[0];replay,receipt,_=run(r,400,r['seed']);by={int(p['id']):p for p in forecast['players']};max_error=0
    for x in replay:
        if 'id'not in x:continue
        pub=next(v for v in by[x['id']]['weeks']if v['gw']==r['gw']);max_error=max(max_error,abs(pub['xpts']-x['points']))
    assert max_error<1e-12
    checks=[]
    for record in load(w/'historical-inputs.json.gz'):
        assert pd.Timestamp(record['gk_training_latest'])<pd.Timestamp(record['cutoff'])
        ps=record['input']['players']
        for team in [record['input']['home_team'],record['input']['away_team']]:
            keepers=[q for q in ps if q['team']==team and q['is_keeper']];from test_separated_goal_head import decode
            inp=decode(copy.deepcopy(record['input']));ks=[q for q in inp.players if q.team==team and q.is_keeper];mass=marginals(ks)
            starts=sum(q['p_start']for q in keepers);minutes=sum(float(mass[q.player_id]@np.arange(91))for q in ks)
            assert abs(starts-1)<1e-9 and abs(minutes-90)<1e-9
            checks.append(dict(season=record['season'],fixture_uuid=record['fixture_uuid'],team_id=team,keeper_start_sum=starts,keeper_minute_sum=minutes,gk_training_latest=record['gk_training_latest'],cutoff=record['cutoff']))
    pd.DataFrame(checks).to_csv(o/'structural-time-checks.csv',index=False)
    (o/'current-replay-identity.json').write_text(json.dumps(dict(forecast_sha256=forecast['forecast_sha256'],fixture_uuid=r['fixture_uuid'],seed=r['seed'],draws=400,maximum_absolute_published_xP_difference=max_error,scope='Same immutable origin evidence and original B simulator, not a new forecast'),indent=2)+'\n')
    mc=pd.read_csv(w/'mc/predictions.csv.gz',low_memory=False);components=['appearance_pts','goal_pts','assist_pts','cs_pts','save_pts','penalty_save_pts','dc_pts','negative_pts','gc_pts','bonus'];cases=mc[mc.season.eq('2026-27')&mc.name.isin(['Penders','E.Le Fée'])&mc.draws.eq(10000)].groupby('name').mean(numeric_only=True)
    assert np.max(abs(cases[components].sum(axis=1)-cases.points))<1e-12
    for x in replay:
        if x.get('name')in cases.index:
            for field in ['analytic_minutes','analytic_start','analytic_p60','analytic_p90']:cases.loc[x['name'],field]=x[field]
    cases[['analytic_minutes','analytic_start','analytic_p60','analytic_p90','points','minutes','started','p60','p90','goals','assists','clean_sheet',*components]].to_csv(o/'current-control-components.csv')
    details=[]
    for record in current:
        for q in record['input']['players']:
            m=record['meta'].get(q['player_id'],{})
            if m.get('name')not in ['Penders','E.Le Fée']:continue
            details.append(dict(name=m['name'],team_lambda=record['input']['lambda_home_goals']if q['team']==record['input']['home_team']else record['input']['lambda_away_goals'],team_penalty_attempt_lambda=record['input']['lambda_home_penalties']if q['team']==record['input']['home_team']else record['input']['lambda_away_penalties'],ordinary_goal_weight=q['goal_weight'],assist_weight=q['assist_weight'],penalty_order=q['penalty_order'],penalty_conversion=q['penalty_conversion'],published_xP=next(t for t in by[m['id']]['weeks']if t['gw']==record['gw'])['xpts']))
    (o/'current-control-inputs.json').write_text(json.dumps(details,indent=2)+'\n')
    f=pd.read_csv(o/'baseline-player-diagnostics.csv.gz',low_memory=False);intervals=[]
    f.groupby(['season','position'])[['goals','actual_goals','assists','actual_assists','minutes','actual_minutes']].sum().to_csv(o/'position-event-totals.csv')
    team=f.groupby(['season','fixture_uuid','team_id']).agg(expected_credited_goals=('goals','sum'),expected_FPL_assists=('assists','sum'),actual_FPL_assists=('actual_assists','sum')).reset_index();budgets=[]
    for record in load(w/'historical-inputs.json.gz'):
        for side in ['home','away']:
            tid=record['input'][side+'_team'];budgets.append(dict(season=record['season'],fixture_uuid=record['fixture_uuid'],team_id=int(tid),expected_inclusive_goal_budget=record['input']['lambda_'+side+'_goals'],actual_team_goals=record['goals'][str(tid)]if str(tid)in record['goals']else record['goals'][tid]))
    team=team.merge(pd.DataFrame(budgets),on=['season','fixture_uuid','team_id'],validate='one_to_one');team.to_csv(o/'team-goal-assist-budgets.csv',index=False)

    for (season,group),g in f.assign(group='all').groupby(['season','group']):
        for cohort,p in [('all',g),('pregame_start_at_least_20pct',g[g.analytic_start.ge(.2)])]:
            e=p.points-p.total_points;z=p.assign(xp_abs_error=abs(e),xp_squared_error=e**2,xp_error=e,minute_abs_error=abs(p.analytic_minutes-p.actual_minutes),minute_error=p.analytic_minutes-p.actual_minutes,start_squared_error=(p.analytic_start-p.actual_start)**2)
            intervals.append(dict(season=season,cohort=cohort,rows=len(p),fixtures=int(p.fixture_uuid.nunique()),intervals=bootstrap(z,['xp_abs_error','xp_squared_error','xp_error','minute_abs_error','minute_error','start_squared_error'])))
    (o/'fixture-sampling-uncertainty.json').write_text(json.dumps(intervals,indent=2)+'\n')
    raw=pd.read_csv(w/'baseline/predictions.csv.gz',low_memory=False);keys=['season','fixture_uuid','player_uuid'];raw['rep']=raw.groupby(keys).seed.rank(method='dense').astype(int);raw=raw.merge(labels(load(w/'historical-inputs.json.gz')),on=keys,validate='many_to_one');rows=[]
    for (season,rep),g in raw.groupby(['season','rep']):rows.append(dict(season=season,rep=int(rep),xp_MAE=float(abs(g.points-g.total_points).mean()),xp_bias=float((g.points-g.total_points).mean())))
    pd.DataFrame(rows).to_csv(o/'baseline-MC-metric-repetitions.csv',index=False)
    oracle=pd.read_csv(w/'oracle/predictions.csv.gz',low_memory=False);n=['points','goals','assists','clean_sheet','p_goal','p_assist'];oracle=oracle.groupby(keys+['mask'])[n].mean().reset_index().merge(labels(load(w/'historical-inputs.json.gz')),on=keys);meta=f[keys+['position','playing_role','analytic_start']];oracle=oracle.merge(meta,on=keys,validate='many_to_one');rows=[]
    for(season,mask),g in oracle.groupby(['season','mask']):
        groups=[('pregame_start_at_least_20pct',g[g.analytic_start.ge(.2)])]
        for col in ['position','playing_role']:groups.extend((col+'='+str(v),p)for v,p in g.groupby(col))
        for name,p in groups:
            if len(p):rows.append(dict(season=season,mask=int(mask),group=name,**metrics(p)))
    pd.DataFrame(rows).to_csv(o/'oracle-group-metrics.csv',index=False)
    # Within-fixture seeds differ numerically; align the repetition index, not seed IDs.
    raw=pd.read_csv(w/'oracle/predictions.csv.gz',low_memory=False);raw['rep']=raw.groupby(keys+['mask']).seed.rank(method='dense').astype(int);raw=raw.merge(labels(load(w/'historical-inputs.json.gz')),on=keys);rows=[]
    for(season,rep,mask),g in raw.groupby(['season','rep','mask']):rows.append(dict(season=season,rep=int(rep),mask=int(mask),xp_MAE=float(abs(g.points-g.total_points).mean())))
    pd.DataFrame(rows).to_csv(o/'oracle-MC-metric-repetitions.csv',index=False)
    provenance=[]
    for path in sorted(o.rglob('*')):
        if path.is_file()and path.name!='SHA256SUMS':provenance.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(o)))
    (o/'SHA256SUMS').write_text('\n'.join(provenance)+'\n')
    print('Supplemental conservation, replay identity, components, sample and MC uncertainty completed')
if __name__=='__main__':main()
