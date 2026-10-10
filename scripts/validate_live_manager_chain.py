#!/usr/bin/env python3
"""Actual forecast integration on a labelled synthetic legal validation squad."""
import copy,hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_live_locked_ts import run,CHIPS
OUT=ROOT/'work/live-manager-validation'

def main():
    payload=json.loads((ROOT/'app/vfinal-diagnostic.json').read_text())
    people=payload['players'];clubs={};picked=[]
    for pos,count in [(1,2),(2,5),(3,5),(4,3)]:
        for p in sorted([p for p in people if p['position']==pos],key=lambda p:(p['price_tenths'],p['id'])):
            if clubs.get(p['team_id'],0)>=3:continue
            picked.append(p);clubs[p['team_id']]=clubs.get(p['team_id'],0)+1
            count-=1
            if count==0:break
        if count:raise ValueError('Cannot construct legal regression fixture')
    cost=sum(p['price_tenths'] for p in picked)
    raw={'season':payload['season'],'gw':min(payload['gws']),
        'source':'SYNTHETIC_VALIDATION_SQUAD_NOT_USER_TEAM_CURRENT_VERIFIED_PRICES',
        'observed_at':payload['data_asof'],'bank_tenths':1000-cost,'free_transfers':2,
        'squad':[{'id':p['id'],'purchase_price_tenths':p['price_tenths']} for p in picked],
        'chips_used':{c:[] for c in CHIPS}}
    before=copy.deepcopy(raw)
    receipt=json.loads((OUT/'tc_scenarios.json').read_text())
    path=OUT/'tc_samples.csv.gz'
    if receipt['cutoff']!=payload['data_asof'] or receipt['samples_sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('TC scenario source mismatch')
    result=run(payload,raw,include_chips=True,tc_samples=pd.read_csv(path))
    if raw!=before:raise ValueError('Manager state mutated')
    if not result['ts_ran'] or not result['chips_ran']:raise ValueError('Original TS/chip chain failed: '+str(result.get('chip_error')))
    if result['chip_assessment']['tc_status']=='Not Available':raise ValueError('TC adapter did not run')
    result['validation_only']=True
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'validation-state.json').write_text(json.dumps(raw,indent=2)+'\n')
    (OUT/'validation-plan.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    # The public example is synthetic and must belong to this exact forecast.
    (ROOT/'app/integration-validation.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'validation_only':True,'gw':raw['gw'],'path_gws':len(result['plan']['path']),
        'first_action':result['plan']['path'][0],'chips':result['chip_assessment'],'comparison':result['comparison']},default=str),flush=True)
if __name__=='__main__':main()
