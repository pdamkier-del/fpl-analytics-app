"""Fixed-finalist precision check: three predetermined seeds, 400 draws each."""
import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/role-event-confirmation-20261005-v1'
SOURCE=ROOT/'analysis/results/role-event-priors-20261005-v1'

def score(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(abs(e).mean()),rmse=float(np.sqrt((e**2).mean())),bias=float(e.mean()))

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol=dict(draws_per_seed=400,seed_bases=[26092501,26192501,26292501],
        selection='same previously frozen development-selected role candidate; no reselection',
        primary='nonbonus MAE/RMSE of forecasts averaged across all three seeds',
        cohort='same 144 fixtures and 11794 players; GW22-38 reused diagnostic',
        uncertainty='seed variation assesses simulation noise, not independent predictive validation')
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    baseline=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','inputs')
    candidate=read_frozen_table(SOURCE,'candidate_inputs')
    keys=['fixture_uuid','player_uuid']
    candidate=candidate.set_index(keys).loc[baseline.set_index(keys).index].reset_index()
    # CSV round trips can shift a float by one ULP. Keep authoritative common
    # inputs exactly identical; only persisted event forecasts may differ.
    for col in baseline:
        if col in ['goal_rate90','assist_rate90','goal_mu','assist_mu','mu_dc']:continue
        if pd.api.types.is_numeric_dtype(baseline[col]):
            assert np.allclose(baseline[col],candidate[col],rtol=0,atol=1e-12)
        else:assert baseline[col].equals(candidate[col])
        candidate[col]=baseline[col].to_numpy()
    records=[]
    for i,(fixture,g) in enumerate(baseline.groupby('fixture_uuid',sort=True)):
        _,control=build_pair(g);_,treatment=build_pair(candidate[candidate.fixture_uuid==fixture])
        a=asdict(control);b=asdict(treatment);ap=a.pop('players');bp=b.pop('players');assert a==b
        for x,y in zip(ap,bp):
            assert {k:v for k,v in x.items() if k not in ['goal_weight','assist_weight','dc_mu_90']}=={k:v for k,v in y.items() if k not in ['goal_weight','assist_weight','dc_mu_90']}
        for seed in protocol['seed_bases']:
            cs,vs=run_pair(control,treatment,n=400,seed=seed+i)
            for r in g.itertuples():
                row=dict(fixture_uuid=fixture,player_uuid=r.player_uuid,gw=r.gw,seed=seed)
                for arm,values in [('current_v4',cs[r.player_uuid]),('role_candidate',vs[r.player_uuid])]:
                    for k in ['xPts_nonbonus','xPts','expected_minutes']:row[arm+'_'+k]=values[k]
                records.append(row)
        if (i+1)%10==0:print('Precision fixtures:',i+1,flush=True)
    frame=pd.DataFrame(records);raw=frame.to_csv(index=False).encode();blob=gzip.compress(raw,mtime=0);parts=[]
    for i,start in enumerate(range(0,len(blob),32768)):
        path=f'predictions.csv.gz.part-{i:04d}';chunk=blob[start:start+32768];(OUT/path).write_bytes(chunk)
        parts.append(dict(path=path,bytes=len(chunk),sha256=hashlib.sha256(chunk).hexdigest()))
    manifest=dict(classification='fixed_role_candidate_precision_check_reused_diagnostic',
        outputs=[dict(name='predictions',rows=len(frame),parts=parts,compressed_sha256=hashlib.sha256(blob).hexdigest(),uncompressed_sha256=hashlib.sha256(raw).hexdigest())],
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [SOURCE/'manifest.json',Path(__file__)]])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    truth=read_frozen_table(ROOT/'analysis/results/deadline-joint-inputs-v1','targets')
    keys=['fixture_uuid','player_uuid'];pooled=frame.drop(columns=['seed','gw']).groupby(keys,as_index=False).mean().merge(truth,on=keys,validate='one_to_one')
    per_seed=[]
    for seed,g in frame.groupby('seed'):
        g=g.merge(truth,on=keys,validate='one_to_one')
        for arm in ['current_v4','role_candidate']:
            per_seed.append(dict(seed=int(seed),arm=arm,**score(g.total_points-g.bonus,g[arm+'_xPts_nonbonus'])))
    pd.DataFrame(per_seed).to_csv(OUT/'seed_metrics.csv',index=False)
    metrics={arm:score(pooled.total_points-pooled.bonus,pooled[arm+'_xPts_nonbonus']) for arm in ['current_v4','role_candidate']}
    report=dict(rows=len(pooled),fixtures=int(pooled.fixture_uuid.nunique()),total_draws_per_fixture_per_arm=1200,
        nonbonus=metrics,role_minus_current={k:metrics['role_candidate'][k]-metrics['current_v4'][k] for k in ['mae','rmse','bias']},
        model_promoted=False,classification='reused_diagnostic_not_new_holdout',seed_metrics=per_seed)
    (OUT/'metrics.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
