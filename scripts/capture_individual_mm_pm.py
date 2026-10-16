#!/usr/bin/env python3
"""Rebuild original PM components after each MM candidate, not just MC minutes."""
import argparse,inspect,json,runpy,sys
import numpy as np
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

def incremental_builder(original):
    """Reuse only exposure-independent prior rates/history; retain exact original math."""
    text=inspect.getsource(original)
    needle="    rg['mu_dc']=rg.expected_minutes/90*rg.role_dc_rate90*rg.dc_opponent_factor"
    if text.count(needle)!=1 or text.count('    rg=add_perf_features(rg,perf_ledger)')!=1:
        raise ValueError('Original component-builder contract changed')
    header=text[:text.index('    rg=rg.copy()')]
    tail=text[text.index(needle):].replace('    rg=add_perf_features(rg,perf_ledger)','    # Cached prefix performance features do not depend on candidate minutes.')
    cards="    from fpl_v1_1_model.negative_events import competing_card_probabilities\n    rg=rg.copy()\n    cards=[competing_card_probabilities(r.expected_minutes,r.yellow_rate90,r.red_rate90) for r in rg.itertuples()]\n    rg['p_yellow']=[c.yellow for c in cards];rg['p_red']=[c.red for c in cards]\n"
    scope={};exec(compile(header+cards+tail,'<isolated-incremental-MM-components>','exec'),original.__globals__,scope)
    return scope[original.__name__]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--season',required=True);ap.add_argument('--source-root',required=True);ap.add_argument('--archive');ap.add_argument('--baseline-inputs');ap.add_argument('--candidates',required=True);ap.add_argument('--selection',required=True);ap.add_argument('--out',required=True);ap.add_argument('--smoke',action='store_true');ap.add_argument('--start-origin',type=int,default=6);ap.add_argument('--end-origin',type=int,default=38);a=ap.parse_args()
    source=Path(a.source_root).resolve();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    selection=json.loads(Path(a.selection).read_text());modes=[selection['selected_arm'],'same_logistic_without_role','partition_only']
    candidates=pd.read_csv(a.candidates);states={}
    for origin in range(6,39):
        for mode in modes:
            states[origin,mode]=candidates[candidates['mode'].eq(mode)&candidates.gw.le(origin)].sort_values('gw',kind='stable').drop_duplicates('player_uuid',keep='last')
    baseline={}
    if a.baseline_inputs:
        baseline={(r['origin'],r['fixture']):r for r in checked_records(a.baseline_inputs)}
    if a.season=='2025-26':
        path=source/'scripts/run_rolling_vfinal_gw6_38.py';code=path.read_text();code=code.replace(".between(origin,min(38,origin+5))",".eq(origin)");namespace={'__file__':str(path),'__name__':'mm_component_capture'};exec(compile(code,str(path),'exec'),namespace)
        archive=Path(a.archive).resolve();argv=[str(path),'--start-origin',str(a.start_origin),'--end-origin',str(a.end_origin),'--db',str(source/'work/core.sqlite3'),'--source',str(source/'analysis/results/workload-final-gw1/all_features.csv.gz'),'--mm',str(archive/'locked-mm-final-gw6-38/locked_mm_predictions.csv.gz'),'--out',str(out/'reference')]
    else:
        path=source/'scripts/run_2024_25_conditional_pm.py';code=path.read_text();code=code.replace('for origin in range(6,39):',f'for origin in range({a.start_origin},{a.end_origin+1}):');needle="fx=sched[sched.gameweek.between(origin,min(38,origin+5)) & (sched.kickoff>=cutoff)]"
        if code.count(needle)!=1:raise ValueError('Original adapter scope changed')
        code=code.replace(needle,"fx=sched[sched.gameweek.eq(origin) & (sched.kickoff>=cutoff)]")
        namespace={'__file__':str(path),'__name__':'mm_component_capture'};exec(compile(code,str(path),'exec'),namespace)
        argv=[str(path),'--start-origin',str(a.start_origin),'--end-origin',str(a.end_origin),'--db',str(source/'work/core.sqlite3'),'--derived',str(source/'data_v1_1/derived/season_2024_25_v1'),'--source',str(source/'analysis/results/conditional-2024-25-mm/conditional_feature_frame.csv.gz'),'--mm',str(source/'analysis/results/conditional-2024-25-mm/locked_mm_predictions.csv.gz'),'--out',str(out/'reference')]
    original_builder=namespace['build_fixture_components'];pending=[];records=[]
    fast=incremental_builder(original_builder)
    prior=checked_records(out/'inputs.jsonl.gz') if (out/'inputs.jsonl.gz').exists() else []
    recovered={(r['origin'],r['fixture']):r for r in prior if 'baseline_sim' in r}
    verified_origins=set()
    def builder(*args,**kwargs):
        built=original_builder(*args,**kwargs)
        pending[:]=[(args,kwargs,built)]
        return built
    def capture(inp,n,seed):
        caller=inspect.currentframe().f_back.f_locals;fr=caller['fr'];origin=int(caller['origin']);rg=caller['rg'];key=(origin,str(fr.match_id))
        if int(fr.gameweek)!=origin:raise ValueError('Only current-GW cells permitted')
        args,kwargs,base=pending[0];alternatives={}
        if key in recovered:
            old=recovered[key]
            if key not in baseline or old['input']!=baseline[key]['input']:raise ValueError('Recovered baseline changed')
            for mode,data in old['candidate_inputs'].items():
                from audit_correctness_historical import decode
                state=states[origin,mode].set_index('player_uuid')
                for p in decode(data).players:
                    r=state.loc[p.player_id]
                    if not np.allclose([p.p_start,p.start_minutes_mean,p.p_cameo_given_bench,p.cameo_minutes_mean],[r.p,r.s,r.q,r.c],atol=1e-9,rtol=0):raise ValueError('Recovered MM state changed')
            records.append(old)
            return old['baseline_sim']
        for mode in modes:
            raw=minute_fields(base,states[origin,mode]);built=fast(raw,*args[1:],**kwargs)
            if origin not in verified_origins:
                slow=original_builder(minute_fields(args[0],states[origin,mode]),*args[1:],**kwargs)
                numeric=slow.select_dtypes(include='number').columns
                if not np.allclose(slow[numeric],built[numeric],rtol=0,atol=1e-10,equal_nan=True):raise ValueError('Incremental rebuild differs from full original builder')
            if not built.player_uuid.equals(rg.player_uuid):raise ValueError('Component rebuild reordered roster')
            final=rg.copy()
            for col in built.columns:final[col]=built[col].to_numpy()
            final=minute_fields(final,states[origin,mode]);alt,_=namespace['make_vfinal_input'](final);alt=replace(alt,bps_rules=inp.bps_rules)
            if alt.lambda_home_goals!=inp.lambda_home_goals or alt.lambda_away_goals!=inp.lambda_away_goals:raise ValueError('MM candidate changed team-goal model')
            alternatives[mode]=asdict(alt)
        verified_origins.add(origin)
        if key in baseline:
            b=baseline[key]
            seed=b['seed']  # Preserve the archived fixture's seed, independent of traversal order.
            from audit_correctness_historical import decode
            frozen=decode(b['input'])
            # Check the baseline MM-dependent rebuild against the exact archived input.
            fields=['p_start','p_cameo_given_bench','start_minutes_mean','cameo_minutes_mean','goal_weight','assist_weight','dc_mu_90','p_own_goal','discipline']
            for oldp,newp in zip(frozen.players,inp.players):
                if oldp.player_id!=newp.player_id:raise ValueError('Frozen roster identity/order mismatch')
                for name in fields:
                    if not (all(np.isclose(getattr(getattr(oldp,name),v),getattr(getattr(newp,name),v),rtol=0,atol=1e-9) for v in ['none','yellow','red']) if name=='discipline' else np.isclose(getattr(oldp,name),getattr(newp,name),rtol=0,atol=1e-9)):raise ValueError('Frozen component mismatch '+name+' '+oldp.player_id)
            # Keep captured penalties, BPS and every other non-MM input fixed.
            for mode,data in alternatives.items():
                alt=decode(data);by={p.player_id:p for p in alt.players}
                data=replace(frozen,players=tuple(replace(p,**{name:getattr(by[p.player_id],name) for name in fields}) for p in frozen.players))
                alternatives[mode]=asdict(data)
            inp=frozen
            ref=b['reference'];refsim=simulate_many(inp,n=n,seed=seed)
            if any(refsim[pid]['xPts']!=v for pid,v in ref.items()):raise ValueError('Frozen baseline simulation mismatch')
        else:
            refsim=simulate_many(inp,n=n,seed=seed);ref={pid:r['xPts'] for pid,r in refsim.items()}
        record=dict(baseline_sim=refsim,origin=origin,fixture=str(fr.match_id),seed=int(seed),input=asdict(inp),candidate_inputs=alternatives,reference=ref,home=int(fr.home_team_id),away=int(fr.away_team_id),players=[dict(player_uuid=str(r.player_uuid),pos=str(r.pos),player=str(r.player)) for r in rg.itertuples()]);records.append(record)
        
        if len(records)%10==0 or len(records)==330 or a.smoke:write_records(out/'inputs.jsonl.gz',records)
        if a.smoke:raise SystemExit(0)
        print('Candidate components rebuilt',a.season,origin,str(fr.match_id),flush=True)
        return refsim
    namespace['main'].__globals__['build_fixture_components']=builder;namespace['main'].__globals__['simulate_many']=capture
    previous=sys.argv
    try:sys.argv=argv;namespace['main']()
    finally:sys.argv=previous
    write_records(out/'inputs.jsonl.gz',records)
    print('Captured MM→full original PM',a.season,len(records),modes,flush=True)
if __name__=='__main__':main()
