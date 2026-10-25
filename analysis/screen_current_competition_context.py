"""Run existing B MM twice with frozen vs observed all-competition physical inputs.

Upstream MM diagnostic only: not the final role/GK projection or a new xP file.
"""
import argparse,json
from pathlib import Path
import pandas as pd
from competition_context import apply_physical_context
from mm_candidate_forecast import infer_B


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--history-context',type=Path,required=True);ap.add_argument('--current-context',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    h=pd.read_csv(a.inputs/'history.csv.gz',low_memory=False,float_precision='round_trip');t=pd.read_csv(a.inputs/'target.csv.gz',low_memory=False,float_precision='round_trip');prov=json.loads((a.inputs/'provenance.json').read_text())
    hc=pd.read_csv(a.history_context,low_memory=False);tc=pd.read_csv(a.current_context,low_memory=False)
    candidate_h=apply_physical_context(h,hc);candidate_t=apply_physical_context(t,tc)
    base,bfit=infer_B(h,t,prov);candidate,cfit=infer_B(candidate_h,candidate_t,prov);keys=['season','fixture_uuid','player_uuid']
    pair=base[keys+['p','q','s','c','x']].merge(candidate[keys+['p','q','s','c','x']],on=keys,validate='one_to_one',suffixes=('_baseline','_candidate'))
    catalogue=pd.read_csv(a.inputs/'pm.csv.gz',usecols=keys+['fpl_element','player','team']);pair=pair.merge(catalogue,on=keys,validate='one_to_one');pair.to_csv(a.out/'upstream-MM-comparison.csv',index=False)
    result=dict(scope='upstream B MM before shared role/GK allocation; not displayed final probabilities or xP',rows=len(pair),players=int(pair.player_uuid.nunique()),mean_absolute_xM_change=float(abs(pair.x_candidate-pair.x_baseline).mean()),maximum_absolute_xM_change=float(abs(pair.x_candidate-pair.x_baseline).max()),baseline_fit=bfit,candidate_fit=cfit,activated=False,production_changed=False)
    (a.out/'upstream-MM-comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
