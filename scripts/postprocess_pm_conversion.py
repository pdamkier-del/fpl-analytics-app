#!/usr/bin/env python3
"""Additional calibration and pre-cutoff subgroup scores; never reruns/tunes models."""
import argparse,json,sqlite3,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records
from replay_pm_conversion import metrics
from fpl_v1_1_model.experimental_pm_conversion import poisson_deviance


def team_summary(p,truth):
    t=p.groupby(['mode','fixture_uuid','team_id'],as_index=False).team_lambda.first().merge(truth,on=['fixture_uuid','team_id'],validate='many_to_one')
    t['mae']=abs(t.team_lambda-t.gf);t['deviance']=poisson_deviance(t.gf,t.team_lambda);ref=t[t['mode'].eq('original')][['fixture_uuid','team_id','mae','deviance']]
    result={};rng=np.random.default_rng(20261015)
    for mode,g in t.groupby('mode'):
        pair=g.merge(ref,on=['fixture_uuid','team_id'],validate='one_to_one',suffixes=('','_base'));r={}
        for key in ['mae','deviance']:
            b=pair.assign(delta=pair[key]-pair[key+'_base']).groupby('fixture_uuid').delta.agg(['sum','size']).to_numpy();draw=b[rng.integers(len(b),size=(2000,len(b)))].sum(1)
            r[key]=dict(value=float(g[key].mean()),delta=float((pair[key]-pair[key+'_base']).mean()),fixture_bootstrap_95_ci=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist())
        bins=pd.cut(g.team_lambda,[0,.5,1,1.5,2,3,np.inf]);r['calibration']=[dict(bin=str(k),sides=len(v),pred=float(v.team_lambda.mean()),actual=float(v.gf.mean())) for k,v in g.groupby(bins,observed=True)];result[mode]=r
    return result


def labels(records,obs,season):
    rows=[];cache={}
    for r in records:
        cut=pd.Timestamp(r['cutoff']);origin=r['origin']
        if origin not in cache:
            h=obs[obs.season.eq(season)&obs.known.lt(cut)].sort_values(['known','fixture_uuid']);by={}
            for pid,g in h.groupby('player_uuid'):
                last=g.tail(6);role='regular' if len(last)>=6 and last.started.eq(1).all() else ('reserve' if len(last)>=3 and last.started.mean()<=.2 else 'rotation_or_short_history')
                high=bool(role=='regular' and g.minutes.sum()>0 and 90*(g.goals.sum()+g.fpl_assists.sum())/g.minutes.sum()>=.5)
                by[str(pid)]=(role,high)
            team=h.groupby('team_id')[['goals','xg']].sum();cache[origin]=(by,team)
        by,team=cache[origin]
        for player in r['input']['players']:
            pid=player['player_id'];role,high=by.get(pid,('rotation_or_short_history',False));tid=int(player['team']);ratio=float(team.loc[tid,'goals']/team.loc[tid,'xg']) if tid in team.index and team.loc[tid,'xg']>0 else None
            rows.append(dict(fixture_uuid=r['core_fixture'],player_uuid=pid,role=role,high_prior_production=high,team_type='unknown' if ratio is None else ('credited_goals_above_xg' if ratio>1 else 'credited_goals_at_or_below_xg')))
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='work/results');ap.add_argument('--db',default='work/core.sqlite3');a=ap.parse_args();root=Path(a.root)
    with sqlite3.connect(a.db) as c:
        obs=pd.read_sql_query('SELECT * FROM player_fixture_observations WHERE is_final=1',c);truth=pd.read_sql_query("SELECT season,fixture_uuid,team_id,gf FROM team_fixture_observations WHERE source_name='football_data_co_uk'",c)
    obs['known']=pd.to_datetime(obs.kickoff_at,utc=True)+pd.to_timedelta(np.where(obs.season.eq('2025-26'),3,4),unit='h');result={}
    for season in ['2024-25','2025-26']:
        prediction=list(root.rglob(f'{season}_locked_predictions.csv.gz'));inputs=list(root.rglob(f'{season}_locked_inputs.jsonl.gz'))
        if len(prediction)!=1 or len(inputs)!=1:raise ValueError('Ambiguous/incomplete evidence paths')
        p=pd.read_csv(prediction[0]);label=labels(checked_records(inputs[0]),obs,season);p=p.merge(label,on=['fixture_uuid','player_uuid'],validate='many_to_one')
        if p.role.isna().any():raise ValueError('Missing cutoff-safe labels')
        test=p[p.gw.ge(22)] if season=='2024-25' else p
        groups={}
        for key in ['role','team_type','high_prior_production']:
            groups[key]={}
            for (mode,name),g in test.groupby(['mode',key]):
                m=metrics(g);groups[key].setdefault(mode,{})[str(name)]={k:m[k] for k in ['rows','mae','rmse','bias','goals','fpl_assists','bonus_mae','bps_mae']}
        result[season]=dict(team_goals=team_summary(test,truth[truth.season.eq(season)]),groups=groups)
    report=dict(classification='POSTPROCESS_COMPLETED_PM_REPLAYS_NO_RETUNING',source_run=38717540912,results=result,group_rule='Before target cutoff only; regular last six registered fixtures all started; high prior G+A90>=.5 within regular; team type uses prior credited goals/xG, not future outcomes',locked_model_active=False,promotion_allowed=False)
    path=root/'additional_calibration_report.json';path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(file=path.name,report=report),indent=2))
if __name__=='__main__':main()
