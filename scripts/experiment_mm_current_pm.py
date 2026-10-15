#!/usr/bin/env python3
"""Read-only GW7 focus replay: selected MM candidates through original components."""
import argparse,json,sys
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_mm_components import prefix_features,load_obs
from audit_capture_io import write_records
from capture_mm_pm_inputs import minute_fields
from fpl_v1_1_model.experimental_mm_research import fit_start,survival_prediction
from fpl_v1_1_model.experimental_survival_sampler import shadow_survival_sampler
from fpl_v1_1_model.joint_simulator import simulate_many
from run_vfinal_integrated import make_vfinal_input
from run_live_vfinal_joint_simulation import POINT_COMPONENTS
from run_rolling_vfinal_gw6_38 import load_models
from vfinal_replay_components import build_fixture_components
from fpl_v1_1_model.role_event_priors import QCOLS
from run_v4_performance_rating_experiment import RECENT_FEATURES


def candidates(base,out):
    full=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
    origin=int(full.target_gw.min());f=full[full.target_gw.eq(origin)].copy()
    for to,fr in [('new_p_start','p_start'),('new_start_minutes','start_minutes_mean'),('new_q_sub','mm_q_sub'),('new_sub_minutes','mm_sub_minutes')]:f[to]=f[fr]
    hist=pd.read_csv(base/'player_fixture_observations.csv.gz');hist['known']=pd.to_datetime(hist.available_at,utc=True)
    cut=pd.to_datetime(f.cutoff,utc=True).min()
    if not (hist.known<cut).all():raise ValueError('Current history after cutoff')
    f=prefix_features(f,hist)
    train=pd.concat([pd.read_csv(out/f'{s}_features.csv.gz') for s in ['2024-25','2025-26']],ignore_index=True)
    sel=json.loads((out/'selection.json').read_text());name=sel['selected_start']
    pp=fit_start(train,f,C=float(name.rsplit('_',1)[1]),hierarchical=name.startswith('hierarchical'))
    pool=[load_obs(ROOT/'work/core.sqlite3',s,h).rename(columns={'fpl_position':'pos'}) for s,h in [('2024-25',4),('2025-26',3)]]
    pool.append(hist.rename(columns={'fpl_position':'pos'}));pool=pd.concat(pool,ignore_index=True);pool['pos']=pool.pos.replace({'GKP':'GK'})
    _,half,strength=sel['selected_duration'].split('_')
    ss,hazards=survival_prediction(f,hist,pool[pool.started.eq(1)],half_days=float(half),strength=float(strength),return_hazards=True)
    states={}
    for mode,p,s in [('start_only',pp,f.new_start_minutes.to_numpy()),('survival_mean',f.new_p_start.to_numpy(),ss),('combined_mean',pp,ss)]:
        a=f.copy();a['p']=p;a['s']=s;a['q']=a.new_q_sub;a['c']=a.new_sub_minutes;a['x']=a.p*a.s+(1-a.p)*a.q*a.c;states[mode]=a
    hazard={str(pid):h for pid,h in zip(f.player_uuid,hazards) if h is not None}
    return full,f,states,hazard,sel


def context(base):
    """Same source context as build_live_vfinal_full_event_components.build."""
    hist=pd.read_csv(base/'player_fixture_observations.csv.gz');hist['available_at']=pd.to_datetime(hist.available_at,utc=True);hist['kickoff_at']=pd.to_datetime(hist.kickoff_at,utc=True)
    training=pd.read_csv(base/'reconstructed_training_features.csv.gz',low_memory=False)
    classified=pd.read_csv(base/'classified_starters.csv.gz');classified['available_at']=pd.to_datetime(classified.available_at,utc=True)
    if 'max_history_known_at' not in training:
        by={int(t):g.available_at.drop_duplicates().sort_values() for t,g in classified.groupby('team_id')}
        training['max_history_known_at']=[next(iter(reversed(by.get(int(r.team_id),pd.Series([],dtype='datetime64[ns, UTC]'))[by.get(int(r.team_id),pd.Series([],dtype='datetime64[ns, UTC]'))<pd.Timestamp(r.cutoff)].tolist())),None) for r in training.itertuples()]
    role=training[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()
    perf=pd.read_csv(ROOT/'work/live-final-model/current_performance_ledger.csv.gz');perf['available_at']=pd.to_datetime(perf.available_at,utc=True)
    return hist,role,perf,load_models()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='analysis/results/mm-research-20261014');a=ap.parse_args();out=Path(a.out)
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    full,f,states,hazards,selection=candidates(base,out);hist,role,perf,m=context(base)
    joined=pd.read_csv(base/'vfinal_live_joined_inputs.csv.gz',low_memory=False)
    cols=pd.read_csv(base/'vfinal_player_event_components_6gw.csv.gz',nrows=0).columns
    remove=[c for c in cols if c not in ['fixture_uuid','player_uuid','fpl_element','target_gw','team_id','expected_minutes','p_start','live_eligibility_applied','cutoff']]
    selected=set(f[f.fpl_element.isin([411,12])|f.team_id.eq(6)].fixture_uuid)
    saved=pd.read_csv(base/'live_vfinal_fixture_xp.csv.gz');seed_offsets={fx:i for i,fx in enumerate(sorted(full.fixture_uuid.unique()))}
    records=[];result=[];checks=[]
    for fx,g in f[f.fixture_uuid.isin(selected)].groupby('fixture_uuid',sort=True):
        cut=pd.Timestamp(g.cutoff.iloc[0]);h=int(g.home_team_id.iloc[0]);away=int(g.away_team_id.iloc[0])
        source=joined[joined.fixture_uuid.eq(fx)].drop(columns=remove+RECENT_FEATURES,errors='ignore').copy();source['expected_minutes']=source.xmins;source['evidence_at']=cut
        source_hist=hist[hist.available_at<cut]
        def rebuild(frame):return build_fixture_components(frame,source_hist,role,cut,m['attack'],m['dc'],m['neg'],m['ga'],m['dc_model'],m['dc_cal'],perf,h,away,float(g.lambda_home_goals.iloc[0]),float(g.lambda_away_goals.iloc[0]),float(g.assist_probability_per_goal.iloc[0]),season='2026-27')
        baseline=rebuild(source);original,_=make_vfinal_input(g);original=replace(original,bps_rules='2026-27')
        # Prove that the context rebuild recovers every original component used by PM.
        verified=g.copy()
        b=baseline.set_index('player_uuid').loc[g.player_uuid]
        for col in baseline.columns:verified[col]=b[col].to_numpy()
        check,_=make_vfinal_input(verified);check=replace(check,bps_rules='2026-27')
        def close(left,right):
            if isinstance(left,dict):return left.keys()==right.keys() and all(close(left[k],right[k]) for k in left)
            if isinstance(left,list):return len(left)==len(right) and all(close(x,y) for x,y in zip(left,right))
            if isinstance(left,(float,int)) and not isinstance(left,bool):return bool(np.isclose(left,right,rtol=0,atol=1e-10))
            return left==right
        if not close(asdict(check),asdict(original)):raise ValueError('Current original component rebuild differs')
        inputs={'original':original}
        for mode,state in states.items():
            rebuilt=rebuild(minute_fields(source,state));alt=g.copy();r=rebuilt.set_index('player_uuid').loc[g.player_uuid]
            for col in rebuilt.columns:alt[col]=r[col].to_numpy()
            alt=minute_fields(alt,state);inp,_=make_vfinal_input(alt);inp=replace(inp,bps_rules='2026-27')
            if (inp.lambda_home_goals,inp.lambda_away_goals)!=(original.lambda_home_goals,original.lambda_away_goals):raise ValueError('Changed team-goal model')
            inputs[mode]=inp
        inputs['combined_distribution']=inputs['combined_mean'];inputs['survival_distribution']=inputs['survival_mean']
        records.append(dict(fixture=fx,cutoff=str(cut),inputs={k:asdict(v) for k,v in inputs.items()},starter_hazards=hazards))
        for rep in range(8):
            seed=93000000+seed_offsets[fx]+rep*100000
            for mode,inp in inputs.items():
                if mode.endswith('_distribution'):
                    with shadow_survival_sampler(hazards):sim=simulate_many(inp,n=400,seed=seed)
                else:sim=simulate_many(inp,n=400,seed=seed)
                if mode=='original' and rep==0:
                    ref=saved[saved.fixture_uuid.eq(fx)].set_index('player_uuid').xpts_fixture
                    if any(v['xPts']!=float(ref.loc[pid]) for pid,v in sim.items()):raise ValueError('Current original forecast not exact')
                for row in g[g.fpl_element.isin([411,12])].itertuples():
                    value=sim[str(row.player_uuid)]
                    if not np.isclose(sum(value[k] for k in POINT_COMPONENTS),value['xPts'],atol=1e-10):raise ValueError('Point components do not sum')
                    result.append(dict(player=row.player,mode=mode,repeat=rep,seed=seed,xp=value['xPts'],minutes=value['expected_minutes'],p_start=next(p.p_start for p in inp.players if p.player_id==str(row.player_uuid)),point_components={k:value[k] for k in POINT_COMPONENTS}))
        checks.append(dict(fixture=fx,original_components_match=True,original_seed_exact=True,lambda_home_goals=original.lambda_home_goals,lambda_away_goals=original.lambda_away_goals,chelsea_goal_intensity=(original.lambda_home_goals if h==6 else original.lambda_away_goals) if 6 in [h,away] else None))
    write_records(out/'current_pm_focus_inputs.jsonl.gz',records)
    summary={}
    for (player,mode),g in pd.DataFrame(result).groupby(['player','mode']):
        v=g.xp.to_numpy();summary.setdefault(player,{})[mode]=dict(xp=float(v.mean()),sim_minutes=float(g.minutes.mean()),p_start=float(g.p_start.mean()),seed_xp_sd=float(v.std(ddof=1)),point_components={key:float(np.mean([r[key] for r in g.point_components])) for key in POINT_COMPONENTS})
    report=dict(classification='FROZEN_SNAPSHOT_SHADOW_CURRENT_PM_NOT_LIVE',cutoff=str(f.cutoff.iloc[0]),selection=selection['selected_start']+' + '+selection['selected_duration'],draws=400,repeats=8,results=summary,fixture_checks=checks,rows=result,locked_model_active=False,promotion_allowed=False,limitations=['Frozen 12 October snapshot; not a new current forecast','Repeated-seed variation is Monte Carlo uncertainty, not predictive accuracy','Original simulator, not combined with own-goal/exact-XI candidate','No personal manager state or candidate TS/chip calculation'])
    (out/'current_pm_focus_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['classification','cutoff','results','fixture_checks']},indent=2))
if __name__=='__main__':main()
