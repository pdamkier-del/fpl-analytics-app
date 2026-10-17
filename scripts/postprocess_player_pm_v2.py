#!/usr/bin/env python3
"""Completed replay attribution and predeclared mechanism checks, no retuning."""
import copy,hashlib,json,math,sys,sqlite3
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records
from audit_correctness_historical import decode
from experiment_mm_pm import POINT_COMPONENTS
from fpl_v1_1_model.experimental_player_pm import lineup_rates,expected_exposure
from fpl_v1_1_model.experimental_pm_conversion import poisson_deviance
from fpl_v1_1_model import joint_simulator


def error_attribution(base_error,deltas):
    """Exact Shapley change in mean absolute prediction error, not causality."""
    base_error=np.asarray(base_error,float);deltas=np.asarray(deltas,float)
    n=deltas.shape[1];v=np.empty(1<<n);v[0]=abs(base_error).mean();err=base_error.copy();previous=0
    for i in range(1,1<<n):
        mask=i^(i>>1);change=mask^previous;j=change.bit_length()-1
        err+=deltas[:,j]*(1 if mask & change else -1);v[mask]=abs(err).mean();previous=mask
    result=[]
    for j in range(n):
        result.append(sum((v[m|(1<<j)]-v[m])/(n*math.comb(n-1,m.bit_count())) for m in range(1<<n) if not m & (1<<j)))
    if not np.isclose(sum(result),v[-1]-v[0],atol=1e-10):raise ValueError('Attribution sum failed')
    return dict(base_mae=float(v[0]),candidate_mae=float(v[-1]),delta=float(v[-1]-v[0]),components={k:float(x) for k,x in zip(POINT_COMPONENTS,result)},warning='Algebraic prediction-error attribution, not causal effect; includes changed RNG realization of unchanged components')


def one(root,name):
    matches=list(root.rglob(name))
    if len(matches)!=1:raise ValueError('Missing/ambiguous artifact '+name)
    return matches[0]


def main():
    source=ROOT/'work/pmv2-replays';out=ROOT/'analysis/results/player-pm-v2-20261015';out.mkdir(parents=True,exist_ok=True);attribution={};finishing={};jensen=[];hashes={}
    with sqlite3.connect(ROOT/'work/core.sqlite3') as c:truth=pd.read_sql_query("SELECT fixture_uuid,team_id,gf FROM team_fixture_observations WHERE source_name='football_data_co_uk'",c).set_index(['fixture_uuid','team_id'])
    for season in ['2024-25','2025-26']:
        attribution[season]={}
        for arm in ['locked','mm']:
            paths=[one(source,f'{season}_{arm}_{i}_predictions.csv.gz') for i in range(4)]
            p=pd.concat([pd.read_csv(x) for x in paths],ignore_index=True)
            for path in paths:hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            if season=='2024-25':p=p[p.gw.ge(22)]
            ref=p[p['mode'].eq('original')];values={}
            for mode,g in p.groupby('mode'):
                if mode=='original':continue
                pair=g.merge(ref,on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_base'))
                deltas=pair[POINT_COMPONENTS].to_numpy()-pair[[k+'_base' for k in POINT_COMPONENTS]].to_numpy()
                if not np.allclose(deltas.sum(1),pair.xp-pair.xp_base,atol=1e-10):raise ValueError('Point deltas do not sum')
                values[mode]=error_attribution(pair.xp_base-pair.total_points,deltas)
            attribution[season][arm]=values
        records=[]
        for i in range(4):
            path=one(source,f'{season}_locked_{i}_inputs.jsonl.gz');hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();records.extend(checked_records(path))
        if len(records)!=330:raise ValueError('Incomplete original prepared input set')
        records=sorted(records,key=lambda r:(r['origin'],r['core_fixture']));records=[r for r in records if season!='2024-25' or r['origin']>=22]
        rows=[]
        for ri,r in enumerate(records):
            item=r['candidates']['hybrid'];inp=decode(copy.deepcopy(item['input']));s=item['spec'];off=copy.deepcopy(s);off['finishing']=False;e={p.player_id:expected_exposure(p) for p in inp.players}
            on_rates,_=lineup_rates(inp,s,e);off_rates,_=lineup_rates(inp,off,e)
            for team,v in on_rates.items():rows.append(dict(fixture=r['core_fixture'],team=int(team),on=v['total'],off=off_rates[team]['total'],actual=float(truth.loc[(r['core_fixture'],int(team)),'gf'])))
            if ri<2:
                rng=np.random.default_rng(20261015+ri);draws={str(t):[] for t in [inp.home_team,inp.away_team]};starts={str(t):[] for t in [inp.home_team,inp.away_team]}
                for _ in range(1000):
                    intervals={p.player_id:joint_simulator._sample_minutes(rng,p) for p in inp.players};exposure={pid:((np.arange(90)+.5>=v[1]) & (np.arange(90)+.5<v[2]) & (v[0]>0)).astype(float) for pid,v in intervals.items()};rates,_=lineup_rates(inp,s,exposure)
                    for team,v in rates.items():
                        draws[team].append(v['total']);starts[team].append(sum(intervals[p.player_id][0]>0 and intervals[p.player_id][1]==0 for p in inp.players if str(p.team)==team))
                for team,vs in draws.items():
                    z=np.array(vs);ss=np.array(starts[team]);jensen.append(dict(season=season,fixture=r['core_fixture'],gw=r['origin'],team=int(team),draws=len(z),mean_goal_intensity=float(z.mean()),sd_goal_intensity=float(z.std(ddof=1)),mean_exp_minus_intensity=float(np.exp(-z).mean()),exp_minus_mean_intensity=float(np.exp(-z.mean())),jensen_difference=float(np.exp(-z).mean()-np.exp(-z.mean())),p_exact_11=float((ss==11).mean()),p_over_11=float((ss>11).mean())))
        f=pd.DataFrame(rows);finishing[season]={mode:dict(sides=len(f),mae=float(abs(f[mode]-f.actual).mean()),poisson_deviance=float(poisson_deviance(f.actual,np.maximum(f[mode],1e-12)).mean()))for mode in ['on','off']}
    report=dict(classification='COMPLETED_PLAYER_PM_V2_MECHANISM_ABLATIONS_NOT_PRODUCTION',source_run=38729720330,source_commit='852f23790ebb4769272b5c8e02b8b30a1794551a',point_error_attribution=attribution,finishing_on_off_analytic=finishing,lineup_intensity_jensen=jensen,source_sha256=hashes,limitations=['No hyperparameters retuned from evaluation','Shapley is exact error attribution, not causal explanation','Finishing on/off uses analytic expected-MM exposures, not full point-model replay; not a claim of xP gain','Jensen mechanism uses first two evaluation fixtures per season, not a representative selected-error cohort','Exp(-intensity) is a Poisson no-goal diagnostic, not a full player clean-sheet probability including minutes, correlated on-pitch status and original penalty mechanics','Original independent XI physics retained; illegal starting counts expose a limitation, not newly certified lineups'],locked_model_active=False,promotion_allowed=False)
    (out/'mechanism_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(file='mechanism_report.json',sha256=hashlib.sha256((out/'mechanism_report.json').read_bytes()).hexdigest(),report=report),indent=2))
if __name__=='__main__':main()
