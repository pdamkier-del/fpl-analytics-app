#!/usr/bin/env python3
"""Rebuild original PM components after each MM candidate, not just MC minutes."""
import argparse,inspect,json,runpy,sys
from dataclasses import asdict,replace
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records,write_records
from fpl_v1_1_model.joint_simulator import simulate_many

def minute_fields(frame,state):
    x=frame.copy();state=state.set_index('player_uuid')
    if not x.player_uuid.isin(state.index).all():raise ValueError('Missing candidate player-state')
    vals=state.loc[x.player_uuid,['p','s','q','c','x']]
    for col,key in [('new_p_start','p'),('new_start_minutes','s'),('new_q_sub','q'),('new_sub_minutes','c'),('new_xmins','x'),('expected_minutes','x'),('control_p_start','p'),('control_xmins','x'),('p_cameo_given_bench','q'),('start_minutes_mean','s'),('cameo_minutes_mean','c'),('v4_workload_start_p_start','p'),('v4_workload_start_xmins','x'),('v4_p_cameo_given_bench','q'),('v4_start_minutes_mean','s'),('v4_cameo_minutes_mean','c')]:x[col]=vals[key].to_numpy()
    return x

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--season',required=True);ap.add_argument('--source-root',required=True);ap.add_argument('--archive');ap.add_argument('--baseline-inputs');ap.add_argument('--candidates',required=True);ap.add_argument('--selection',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    source=Path(a.source_root).resolve();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    selection=json.loads(Path(a.selection).read_text());modes=[selection['selected_start'],selection['selected_duration'],'combined']
    candidates=pd.read_csv(a.candidates);states={}
    for origin in range(6,39):
        for mode in modes:
            states[origin,mode]=candidates[candidates['mode'].eq(mode)&candidates.gw.le(origin)].sort_values('gw',kind='stable').drop_duplicates('player_uuid',keep='last')
    baseline={}
    if a.baseline_inputs:
        baseline={(r['origin'],r['fixture']):r for r in checked_records(a.baseline_inputs)}
    if a.season=='2025-26':
        path=source/'scripts/run_rolling_vfinal_gw6_38.py';namespace=runpy.run_path(str(path),run_name='mm_component_capture')
        archive=Path(a.archive).resolve();argv=[str(path),'--db',str(source/'work/core.sqlite3'),'--source',str(source/'analysis/results/workload-final-gw1/all_features.csv.gz'),'--mm',str(archive/'locked-mm-final-gw6-38/locked_mm_predictions.csv.gz'),'--out',str(out/'reference')]
    else:
        path=source/'scripts/run_2024_25_conditional_pm.py';code=path.read_text();needle="fx=sched[sched.gameweek.between(origin,min(38,origin+5)) & (sched.kickoff>=cutoff)]"
        if code.count(needle)!=1:raise ValueError('Original adapter scope changed')
        code=code.replace(needle,"fx=sched[sched.gameweek.eq(origin) & (sched.kickoff>=cutoff)]")
        namespace={'__file__':str(path),'__name__':'mm_component_capture'};exec(compile(code,str(path),'exec'),namespace)
        argv=[str(path),'--db',str(source/'work/core.sqlite3'),'--derived',str(source/'data_v1_1/derived/season_2024_25_v1'),'--source',str(source/'analysis/results/conditional-2024-25-mm/conditional_feature_frame.csv.gz'),'--mm',str(source/'analysis/results/conditional-2024-25-mm/locked_mm_predictions.csv.gz'),'--out',str(out/'reference')]
    original_builder=namespace['build_fixture_components'];pending=[];records=[]
    def builder(*args,**kwargs):
        pending[:]=[(args,kwargs)]
        return original_builder(*args,**kwargs)
    def capture(inp,n,seed):
        caller=inspect.currentframe().f_back.f_locals;fr=caller['fr'];origin=int(caller['origin']);rg=caller['rg'];key=(origin,str(fr.match_id))
        if int(fr.gameweek)!=origin:raise ValueError('Only current-GW cells permitted')
        args,kwargs=pending[0];alternatives={}
        for mode in modes:
            raw=minute_fields(args[0],states[origin,mode]);built=original_builder(raw,*args[1:],**kwargs)
            if not built.player_uuid.equals(rg.player_uuid):raise ValueError('Component rebuild reordered roster')
            final=rg.copy()
            for col in built.columns:final[col]=built[col].to_numpy()
            final=minute_fields(final,states[origin,mode]);alt,_=namespace['make_vfinal_input'](final);alt=replace(alt,bps_rules=inp.bps_rules)
            if alt.lambda_home_goals!=inp.lambda_home_goals or alt.lambda_away_goals!=inp.lambda_away_goals:raise ValueError('MM candidate changed team-goal model')
            alternatives[mode]=asdict(alt)
        if key in baseline:
            b=baseline[key]
            if b['seed']!=seed or b['input']!=json.loads(json.dumps(asdict(inp))):raise ValueError('Archived PM capture no longer identical')
            ref=b['reference']
        else:
            refsim=simulate_many(inp,n=n,seed=seed);ref={pid:r['xPts'] for pid,r in refsim.items()}
        record=dict(origin=origin,fixture=str(fr.match_id),seed=int(seed),input=asdict(inp),candidate_inputs=alternatives,reference=ref,home=int(fr.home_team_id),away=int(fr.away_team_id),players=[dict(player_uuid=str(r.player_uuid),pos=str(r.pos),player=str(r.player)) for r in rg.itertuples()]);records.append(record)
        write_records(out/'inputs.jsonl.gz',records)
        return refsim if key not in baseline else {pid:dict(xPts=v) for pid,v in ref.items()}
    namespace['main'].__globals__['build_fixture_components']=builder;namespace['main'].__globals__['simulate_many']=capture
    previous=sys.argv
    try:sys.argv=argv;namespace['main']()
    finally:sys.argv=previous
    print('Captured MM→full original PM',a.season,len(records),modes,flush=True)
if __name__=='__main__':main()
