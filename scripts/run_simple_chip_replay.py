#!/usr/bin/env python3
"""Run one cutoff-aware 2025/26 FH/WC threshold pair with locked TS."""
import argparse,json
from pathlib import Path
import pandas as pd
import run_joint_fh_wc_stopping_replay as replay

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vfinal',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--lambda-fh',type=float,required=True)
    ap.add_argument('--lambda-wc',type=float,required=True)
    a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    gws,names,forecast=replay.load(a.vfinal)
    wc_original=replay.compare_wc_as_ts_action
    fh_original=replay.optimize_free_hit_squad
    events=[]
    def audit_wc(state,meta,origin,gw,config,**kwargs):
        candidate=wc_original(state,meta,origin,gw,config,**kwargs)
        previous=set(state.squad); following=set(candidate.state.squad)
        events.append({'gw':gw,'chip':'wc','out':[names.get(i,str(i)) for i in sorted(previous-following)],'in':[names.get(i,str(i)) for i in sorted(following-previous)],'squad':[names.get(i,str(i)) for i in sorted(following)]})
        return candidate
    def audit_fh(**kwargs):
        candidate=fh_original(**kwargs)
        previous=set(kwargs['state'].squad);following=set(candidate['plan_rows'].id)
        events.append({'gw':kwargs['gw'],'chip':'fh','out':[names.get(i,str(i)) for i in sorted(previous-following)],'in':[names.get(i,str(i)) for i in sorted(following-previous)],'squad':[names.get(i,str(i)) for i in sorted(following)]})
        return candidate
    replay.compare_wc_as_ts_action=audit_wc
    replay.optimize_free_hit_squad=audit_fh
    result=replay.run('simple_wc_fh',gws,names,forecast,
        use_chips=True,simple_thresholds=(a.lambda_fh,a.lambda_wc))
    chosen=[e for e in events if (e['chip']=='wc' and e['gw'] in result['wc_gws']) or (e['chip']=='fh' and e['gw'] in result['fh_gws'])]
    (out/'squads.json').write_text(json.dumps(chosen,indent=2))
    print('CHIP_SQUAD_DETAILS',json.dumps(chosen),flush=True)
    pd.DataFrame(result.pop('logs')).to_csv(out/'gameweeks.csv',index=False)
    result.update(lambda_fh=a.lambda_fh,lambda_wc=a.lambda_wc,
                  delta_from_locked=result['total_points']-2125)
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print('FINAL_SIMPLE_CHIPS',json.dumps(result),flush=True)
if __name__=='__main__':main()
