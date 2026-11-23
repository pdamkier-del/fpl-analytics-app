"""Single budgeted first attempt; inputs and implementation must be registered."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
START=time.monotonic();ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'research/tools'),str(ROOT/'research/mm_pm_live'),str(ROOT/'research/ts_search/code')]
import registry
from archive_link import load_runtime,recover_verified
from run_experiment import load_frozen,write
from adapter import adapt,TAG,RAW
from generate import generate
ID='EXP-TS-FUNDING-REALPOOL-001'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive-root',type=Path,required=True);parser.add_argument('--frozen-root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--input-cache',type=Path,required=True);a=parser.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((HERE/'implementation.json').read_text())
    for p,h in manifest['files'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Frozen implementation changed: '+p)
    reg=registry.read()[ID]
    if reg['state']!='running'or reg['implementation']['harness_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('Register immutable running implementation first')
    receipt=dict(status='running',budget_seconds=3600,states_generated=0,arms=[],future_outcomes_used=False,host=dict(platform=platform.platform(),cpu=platform.processor(),python=sys.version,threads={k:os.environ.get(k)for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']}))
    write(a.out/'result.json',receipt)
    stage='original_recovery'
    try:
        runtime=load_runtime(a.archive_root);backend=runtime[0].Github('pdamkier-del/fpl-analytics-app')
        folder,m,proof,docs=recover_verified(runtime,backend,TAG,a.input_cache)
        raw=gzip.decompress((folder/'forecast.json.gz').read_bytes())
        if hashlib.sha256(raw).hexdigest()!=RAW:raise ValueError('Original forecast raw hash changed')
        receipt['archive']=dict(revision_id=m['revision_id'],forecast_sha256=m['forecast_sha256'],raw_sha256=RAW,proof=proof,players=len(docs['forecast.json']['players']))
        stage='lossless_adapter'
        modules=load_frozen(a.frozen_root);scoring=modules[2];live=modules[3]
        f,eligible=adapt(docs['forecast.json'],docs['mm.json'],scoring.validate_forecast)
        if f is not docs['forecast.json']:raise ValueError('Identity adapter mutated input')
        meta,origin=live.project(f)
        if len(meta)!=len(f['players'])or len(origin)!=6*len(meta):raise ValueError('Worker projection lost rows')
        receipt['adapter']=dict(status='passed_identity',eligible_owned=len(eligible),original_draws=f['scenario_contract']['draws'],gws=f['gws'],projected_rows=len(origin))
        stage='state_generation'
        cases=generate(f,eligible);a.out.joinpath('states').mkdir()
        for case in cases:write(a.out/'states'/f'{case["id"]:02}.json',case)
        receipt['states_generated']=len(cases);receipt['states_sha256']={f'{c["id"]:02}.json':hashlib.sha256((a.out/'states'/f'{c["id"]:02}.json').read_bytes()).hexdigest()for c in cases}
        # The protocol requires a retained batch commit BEFORE any arm runs.
        subprocess.run(['git','-C',str(ROOT),'add',str((a.out/'states').resolve())],check=True,capture_output=True)
        subprocess.run(['git','-C',str(ROOT),'commit','-m','Freeze all 12 protocol states before any real-pool arm'],check=True,capture_output=True)
        receipt['states_commit']=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip();write(a.out/'result.json',receipt)
        stage='arms'
        for case in cases:
            for arm in ((['baseline','candidate']if case['id']%2 else['candidate','baseline'])+['keep']):
                output=a.out/f'{case["id"]:02}-{arm}.json';remaining=3600-(time.monotonic()-START)
                row=dict(id=case['id'],stratum=case['stratum'],arm=arm,status='not_run')
                if case['status']!='generated':row['status']='state_generation_failed'
                elif remaining>0:
                    command=[sys.executable,str(HERE/'worker.py'),'--input',str(folder/'forecast.json.gz'),'--case',str(a.out/'states'/f'{case["id"]:02}.json'),'--frozen-root',str(a.frozen_root),'--arm',arm,'--out',str(output)]
                    t=time.monotonic()
                    try:
                        completed=subprocess.run(command,capture_output=True,timeout=min(120,remaining),env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
                        row['end_to_end_seconds']=time.monotonic()-t
                        if completed.returncode==0:row.update(json.loads(output.read_text()))
                        else:
                            row.update(status='failed',exit_code=completed.returncode,error=completed.stderr.decode(errors='replace')[-3000:])
                    except subprocess.TimeoutExpired:row.update(status='timeout',end_to_end_seconds=time.monotonic()-t)
                receipt['arms'].append(row);write(a.out/'result.json',receipt)
                print(f'{case["id"]:02} {arm}: {row["status"]}',flush=True)
        receipt['status']='evaluated'if all(r['status']=='completed'for r in receipt['arms'])else'incomplete'
    except Exception as error:
        receipt.update(status='blocked',stage=stage,error_type=type(error).__name__,error=str(error),states_generated=receipt['states_generated'])
    receipt['elapsed_seconds']=time.monotonic()-START
    write(a.out/'result.json',receipt)
    print(json.dumps({k:receipt.get(k)for k in ['status','stage','error','states_generated','elapsed_seconds']}),flush=True)
    return 0 if receipt['status']=='evaluated'else 2
if __name__=='__main__':sys.exit(main())
