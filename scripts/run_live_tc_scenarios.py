#!/usr/bin/env python3
"""Extend original inference targets to the chip-half end; use original TC draws.

The ordinary six-GW checkpoint is restored in finally. No model formula,
fit parameter, original TC seed, sample count or candidate limit is changed.
"""
import hashlib,json,subprocess,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from restore_live_vfinal_checkpoint import restore
from verify_canonical_raw_rebuild import STEPS,execute
from audit_live_raw_reproduction import numeric_diff
from run_vfinal_integrated import make_vfinal_input
from fpl_v1_1_model.joint_simulator import simulate_many_samples
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'
OUT=ROOT/'work/live-manager-validation'

def samples(frame,origin):
    end=19 if origin<=19 else 38
    if set(frame.target_gw.astype(int))!=set(range(origin,end+1)):
        raise ValueError('TC requires the complete current chip half')
    if frame.cutoff.nunique()!=1 or frame.duplicated(['fixture_uuid','player_uuid']).any():
        raise ValueError('Mixed cutoff or duplicate TC fixture identity')
    cutoff=pd.Timestamp(frame.cutoff.iloc[0])
    if (pd.to_datetime(frame.target_kickoff,utc=True)<=cutoff).any():
        raise ValueError('TC target fixture is not future at the source cutoff')
    sums={};meta={}
    order=frame[['fixture_uuid','fpl_fixture_id']].drop_duplicates().sort_values('fpl_fixture_id')
    for counter,fx in enumerate(order.fixture_uuid):
        g=frame[frame.fixture_uuid.eq(fx)].copy()
        inp,_=make_vfinal_input(g)
        inp=replace(inp,bps_rules='2026-27')
        sim=simulate_many_samples(inp,n=400,seed=96000000+origin*1000+counter)
        for r in g.itertuples(index=False):
            key=(int(r.target_gw),int(r.fpl_element))
            arr=np.asarray(sim[str(r.player_uuid)],dtype=np.float32)
            if key in sums:sums[key]+=arr
            else:sums[key]=arr.copy()
            meta[key]=dict(gw=key[0],candidate_id=key[1],candidate_name=str(r.player),
                           player_uuid=str(r.player_uuid),team=int(r.team_id),position=str(r.pos))
    means=pd.DataFrame([{**meta[k],'mean_points':float(np.mean(v))} for k,v in sums.items()])
    selected=pd.concat([g.sort_values('mean_points',ascending=False).head(20) for _,g in means.groupby('gw',sort=True)],ignore_index=True)
    keep={(int(r.gw),int(r.candidate_id)) for r in selected.itertuples(index=False)}
    rows=[{**meta[key],'simulation':i,'points':float(v)} for key,arr in sums.items() if key in keep for i,v in enumerate(arr)]
    return pd.DataFrame(rows),selected

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    forecast=json.loads((ROOT/'app/vfinal-diagnostic.json').read_text())
    origin=min(forecast['gws']);end=19 if origin<=19 else 38
    receipt=json.loads((WORK/'publication_provenance.json').read_text())
    reference=pd.read_csv(BASE/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
    original={p:hashlib.sha256((BASE/p).read_bytes()).hexdigest() for p in receipt['checksums']}
    try:
        execute('audit_current_locked_inputs',['--horizon-end',end])
        for step in STEPS:
            if step=='restore_original_bps_bounds':continue  # immutable development parameters already restored and verified
            execute(step,['--horizon-end',end] if step in ('run_live_vfinal_team_latent','run_live_vfinal_player_components') else [])
        execute('run_live_vfinal_penalty_state',['--origin',origin,'--roster',BASE/'vfinal_live_full_event_inputs.csv.gz',
            '--attempts',BASE/'verified_penalty_attempts.csv.gz','--sides',BASE/'verified_penalty_team_sides.csv.gz','--teams',BASE/'verified_penalty_team_ids.csv.gz'])
        execute('run_live_vfinal_bps',['--target',BASE/'vfinal_live_full_event_inputs.csv.gz','--ledger',BASE/'verified_bps_action_ledger.csv.gz'])
        execute('assemble_live_vfinal_inputs',['--base',BASE/'vfinal_live_full_event_inputs.csv.gz','--horizon-end',end])
        source=BASE/'vfinal_live_full_simulator_input.csv.gz'
        frame=pd.read_csv(source,low_memory=False)
        if str(frame.cutoff.iloc[0])!=forecast['data_asof']:raise ValueError('TC and TS cutoff differ')
        keys=['fixture_uuid','player_uuid']
        subset=frame[frame.target_gw.isin(reference.target_gw.unique())][reference.columns].sort_values(keys).reset_index(drop=True)
        old=reference.sort_values(keys).reset_index(drop=True)
        drift=numeric_diff(old,subset)
        for col in old:
            x,y=old[col],subset[col]
            if x.equals(y):continue
            if not pd.api.types.is_float_dtype(x):
                raise ValueError('TC extension changed nonfloating current source field '+col)
            xv,yv=x.to_numpy(float),y.to_numpy(float)
            both=np.isnan(xv)&np.isnan(yv)
            exact=(xv==yv)|both
            changed=~exact
            if not np.all(np.isfinite(xv[changed])&np.isfinite(yv[changed])) or not np.all(np.abs(xv[changed]-yv[changed])<=4*np.abs(np.spacing(xv[changed]))):
                raise ValueError('TC extension differs materially from immutable current forecast '+col+'; max_abs='+str(float(np.max(np.abs(xv[changed]-yv[changed]))))+'; max_ulp='+str(float(np.max(np.abs(xv[changed]-yv[changed])/np.abs(np.spacing(xv[changed])))))+'; evidence='+json.dumps(drift))
        # Current forecast rows are the approved immutable source for current
        # TC scenarios. No float is rounded and no reconstructed equality is claimed.
        frame=pd.concat([reference,frame[~frame.target_gw.isin(reference.target_gw.unique())][reference.columns]],ignore_index=True)
        frame.to_csv(source,index=False,compression={'method':'gzip','mtime':0})
        out,selected=samples(frame,origin)
        repeated,_=samples(frame,origin)
        if not out.equals(repeated):raise ValueError('TC scenarios are not reproducible')
        out.to_csv(OUT/'tc_samples.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        selected.to_csv(OUT/'tc_candidates.csv',index=False)
        (OUT/'tc_simulator_inputs.csv.gz').write_bytes(source.read_bytes())
        fixture_source=WORK/'fixtures.json'
        audit={'classification':'ORIGINAL_TC_V2_CURRENT_SNAPSHOT_DIAGNOSTIC_MANUAL',
            'cutoff':forecast['data_asof'],'origin_gw':origin,'period_end_gw':end,
            'future_schedule_source':'OFFICIAL_FPL_SNAPSHOT_AT_ORIGIN_CUTOFF',
            'fixtures_snapshot_sha256':hashlib.sha256(fixture_source.read_bytes()).hexdigest(),
            'source_checkpoint':'model/checkpoints/live_gw7_sources_20261010_v1',
            'ordinary_six_gw_checksums':original,'fixtures':int(frame.fixture_uuid.nunique()),'input_rows':len(frame),'samples':len(out),
            'same_six_gw_inputs_exact':True,'raw_extension_six_gw_numeric_differences':drift,'current_forecast_source':'IMMUTABLE_APPROVED_SIX_GW_INPUT_ROWS_NO_ROUNDING','draws':400,'top_k_per_gw':20,'two_sample_replays_exact':True,
            'samples_sha256':hashlib.sha256((OUT/'tc_samples.csv.gz').read_bytes()).hexdigest(),
            'simulator_inputs_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'model_math_changed':False,'manual_decision_required':True,'locked_model_active':False,
            'limitations':[b for b in forecast['blockers'] if not b.startswith('Locked TC future-option')]}
        (OUT/'tc_scenarios.json').write_text(json.dumps(audit,indent=2)+'\n')
        print(json.dumps(audit),flush=True)
    finally:
        restore(ROOT/'model/checkpoints/live_vfinal_gw7_20261010_v2')
        for p,digest in original.items():
            if hashlib.sha256((BASE/p).read_bytes()).hexdigest()!=digest:
                raise ValueError('Ordinary six-GW checkpoint was not restored')
if __name__=='__main__':main()
