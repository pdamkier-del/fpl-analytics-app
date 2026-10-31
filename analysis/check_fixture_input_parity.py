"""Real flat source tables must produce identical mathematical inputs and draws."""
import argparse,hashlib,json
from dataclasses import asdict
from pathlib import Path
import pandas as pd
from run_vfinal_integrated import make_vfinal_input,build_final_frame
from pm_preview_distributions import simulate_with_distributions


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--current-pm',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reference',type=Path);a=ap.parse_args()
    current=pd.read_csv(a.current_pm,low_memory=False,float_precision='round_trip')
    history=build_final_frame();cases=[('current',k,g)for k,g in list(current.groupby('fixture_uuid',sort=True))[:50]]
    cases += [('historical',k,g)for k,g in list(history.groupby('fixture_uuid',sort=True))[::3][:50]]
    rows=[]
    for scope,fx,g in cases:
        inp,own=make_vfinal_input(g)
        result=simulate_with_distributions(inp,n=10,seed=20261025,include_samples=True)
        digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        rows.append(dict(scope=scope,fixture=str(fx),players=len(inp.players),own_goal_input_present=own,input_sha256=digest(asdict(inp)),output_sha256=digest(result)))
    r=dict(fixtures=len(rows),draws_per_fixture=10,receipts=rows)
    if a.reference and json.loads(a.reference.read_text())!=r:raise ValueError('Common input refactor changed mathematical inputs or forecast outputs')
    a.out.write_text(json.dumps(r,indent=2)+'\n');print('Fixture-input parity',len(rows),'fixtures',bool(a.reference),flush=True)

if __name__=='__main__':main()
