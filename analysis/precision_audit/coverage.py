"""Declare oracle coverage and MC cases before inspecting prediction losses."""
import argparse,copy
from pathlib import Path
import pandas as pd
from precision_audit.dataset import load,dump
from precision_audit.oracles import reconcile_timeline,actual_timeline
from test_separated_goal_head import decode

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);args=p.parse_args()
    records=load(args.work/'historical-inputs.json.gz');coverage=[]
    for r in records:
        inp=decode(copy.deepcopy(r['input']));strict=False
        try:actual_timeline(inp,r['actual']);strict=True
        except ValueError:pass
        try:
            if any((a.get('fpl_red_cards') or 0)>0 for a in r['actual'].values()):raise ValueError('Actual red-card removal outside normal timeline')
            _,difference=reconcile_timeline(inp,r['actual'],True)
            reconcile_timeline(inp,r['actual'],False)
            r['oracle_eligible']=True;r['oracle_exclusion']=None;error=max(abs(x)for x in difference.values())
        except ValueError as e:
            r['oracle_eligible']=False;r['oracle_exclusion']=str(e);error=None
        coverage.append(dict(season=r['season'],fixture_uuid=r['fixture_uuid'],oracle_eligible=r['oracle_eligible'],reason=r['oracle_exclusion'],raw_FPL_clock_exact_physical=strict,max_FPL_physical_clock_difference=error))
    dump(args.work/'historical-inputs.json.gz',records)
    frame=pd.DataFrame(coverage);frame.to_csv(args.work/'oracle-coverage.csv',index=False)
    print(frame.groupby('season').oracle_eligible.agg(['sum','count']).to_string());print(frame.reason.value_counts().to_string())
    current=load(args.work/'current-inputs.json.gz');chosen=[]
    for season in ['2024-25','2025-26']:
        for gw in [24,32]:chosen.append(sorted([r for r in records if r['season']==season and r['gw']==gw],key=lambda r:r['fixture_uuid'])[0])
    dump(args.work/'mc-inputs.json.gz',current+chosen)
if __name__=='__main__':main()
