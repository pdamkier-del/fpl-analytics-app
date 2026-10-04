"""Paired technical sensitivity on the reused GW22–38 complete-fixture cohort."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.paired_joint import build_pair,read_frozen_table,run_pair


def metrics(pred, actual):
    error=np.asarray(pred)-np.asarray(actual)
    return dict(n=len(error),mae=float(np.abs(error).mean()),rmse=float(np.sqrt((error**2).mean())),bias=float(error.mean()))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs',type=Path,default=ROOT/'analysis/results/joint-paired-inputs-v1')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/joint-paired-diagnostic-v1')
    ap.add_argument('--simulations',type=int,default=80)
    ap.add_argument('--seed',type=int,default=26092501)
    a=ap.parse_args()
    if a.simulations<=0:raise ValueError('Positive simulation count required')
    if a.out.exists():raise FileExistsError('Use a new output folder')
    inputs=read_frozen_table(a.inputs,'inputs')
    rows=[]
    for i,(_,g) in enumerate(inputs.groupby('fixture_uuid',sort=True)):
        control,candidate=build_pair(g)
        cs,vs=run_pair(control,candidate,n=a.simulations,seed=a.seed+i)
        for r in g.itertuples(index=False):
            row=dict(fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,gw=r.gw,team_id=r.team_id)
            for arm,values in [('control',cs[r.player_uuid]),('v4',vs[r.player_uuid])]:
                for key,val in values.items():row[arm+'_'+key]=val
            rows.append(row)
        if (i+1)%10==0:print('Completed paired fixtures:',i+1,flush=True)
    result=pd.DataFrame(rows).sort_values(['gw','fixture_uuid','team_id','player_uuid'])
    a.out.mkdir(parents=True)
    # Save predictions before reading evaluation outcomes.
    raw=result.to_csv(index=False,lineterminator='\n').encode()
    compressed=gzip.compress(raw,mtime=0)
    parts=[]
    for i,start in enumerate(range(0,len(compressed),32768)):
        data=compressed[start:start+32768];name=f'predictions.csv.gz.part-{i:04d}'
        (a.out/name).write_bytes(data);parts.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    target=read_frozen_table(a.inputs,'targets')
    evaluated=result.merge(target,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    summary=dict(classification='reused_diagnostic_not_new_holdout',season='2025-26',gw_range=[22,38],
        paired_fixtures=int(result.fixture_uuid.nunique()),paired_player_fixture_rows=len(result),
        simulations_per_fixture_per_arm=a.simulations,seed_base=a.seed,
        inputs_manifest_sha256=hashlib.sha256((a.inputs/'manifest.json').read_bytes()).hexdigest(),
        primary='bonus-neutral paired sensitivity; inherited direct-event model limitations remain',
        fixed=['fixture roster','team goals','on-pitch attack/assist/DC rates','discipline','keeper saves','original simulator','scoring','transfer/chip policy'],
        changed=['candidate P(start) and selected v4 conditional minutes'],
        randomness='Same fixture seed and budget; not event-aligned common random numbers; 80 draws is inherited technical budget, not precise xP ranking',
        full_season_replay_ready=False,outputs=[dict(name='predictions',rows=len(result),
            compressed_sha256=hashlib.sha256(compressed).hexdigest(),uncompressed_sha256=hashlib.sha256(raw).hexdigest(),parts=parts)])
    for scoring,pcol,actual in [('nonbonus','xPts_nonbonus',evaluated.total_points-evaluated.bonus),
                                ('full_2026_27_bps_on_2025_26_diagnostic','xPts',evaluated.total_points)]:
        summary[scoring]={arm:metrics(evaluated[arm+'_'+pcol],actual) for arm in ['control','v4']}
        summary[scoring]['v4_minus_control']={key:summary[scoring]['v4'][key]-summary[scoring]['control'][key] for key in ['mae','rmse','bias']}
    summary['mean_simulated_minutes']={arm:float(result[arm+'_expected_minutes'].mean()) for arm in ['control','v4']}
    summary['code']=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [Path(__file__),ROOT/'src/fpl_v1_1_model/paired_joint.py',ROOT/'src/fpl_v1_1_model/phase4b.py',ROOT/'src/fpl_v1_1_model/joint_simulator.py']]
    (a.out/'manifest.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['outputs','code']},indent=2))


if __name__=='__main__':main()
