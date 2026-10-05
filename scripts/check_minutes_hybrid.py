"""Check frozen hybrid experiment, paired control identity and point metrics."""
import hashlib
import json
from pathlib import Path
import numpy as np
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]

def main():
    inputs=ROOT/'analysis/results/minutes-hybrid-inputs-20261005-v1'
    output=ROOT/'analysis/results/minutes-hybrid-paired-20261005-v1'
    old=ROOT/'analysis/results/deadline-joint-paired-diagnostic-v1'
    checks=0
    for folder in [ROOT/'analysis/results/minutes-components-20261005-v1',inputs]:
        m=json.loads((folder/'manifest.json').read_text())
        for s in m['sources']:
            assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256'];checks+=1
        for o in m['outputs']:
            if 'path' in o:
                assert hashlib.sha256((folder/o['path']).read_bytes()).hexdigest()==o['sha256'];checks+=1
    f=read_frozen_table(inputs,'inputs');t=read_frozen_table(inputs,'targets')
    pred=read_frozen_table(output,'predictions');control=read_frozen_table(old,'predictions')
    keys=['fixture_uuid','player_uuid']
    joined=pred.merge(control,on=keys,validate='one_to_one',suffixes=('_new','_old'))
    assert len(joined)==11794 and pred.fixture_uuid.nunique()==144;checks+=1
    for c in pred:
        if c.startswith('control_'):
            assert np.array_equal(joined[c+'_new'].to_numpy(),joined[c+'_old'].to_numpy());checks+=1
    m=json.loads((output/'manifest.json').read_text())
    assert m['inputs_manifest_sha256']==hashlib.sha256((inputs/'manifest.json').read_bytes()).hexdigest();checks+=1
    for s in m['code']:
        assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256'];checks+=1
    truth=pred.merge(t,on=keys,validate='one_to_one');assert len(truth)==len(f)
    for arm in ['control','v4']:
        error=truth[arm+'_xPts_nonbonus']-(truth.total_points-truth.bonus)
        scores=dict(mae=float(abs(error).mean()),rmse=float(np.sqrt((error**2).mean())),bias=float(error.mean()))
        for key,v in scores.items():assert np.isclose(v,m['nonbonus'][arm][key],atol=1e-12,rtol=0);checks+=1
    previous=json.loads((old/'manifest.json').read_text())
    delta={k:m['nonbonus']['v4'][k]-previous['nonbonus']['v4'][k] for k in ['mae','rmse','bias']}
    report=dict(passed=True,checks=checks,original_control_predictions_identical=True,
                current_v4=previous['nonbonus']['v4'],experimental_hybrid=m['nonbonus']['v4'],hybrid_minus_current_v4=delta,
                decision='retain current v4; hybrid gives no demonstrated downstream improvement at inherited 80-draw budget',
                model_promoted=False,classification='reused_diagnostic_not_new_holdout',
                caveat='Small stochastic differences do not establish statistical inferiority; confirm on development and independent data before promotion')
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
