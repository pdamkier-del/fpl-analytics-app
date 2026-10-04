"""Direct minute/start evaluation of saved forecasts; no model fitting.

Primary comparison uses the exact 144-fixture point-diagnostic cohort.
The role-control comparison isolates the incremental workload block.
All outputs remain reused GW22-38 diagnostics, never new holdout evidence.
"""
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/results/direct-minutes-v4-diagnostic-v1'
KEYS = ['fixture_uuid', 'player_uuid', 'team_id', 'gw']
ARMS = {'original_v2': ('control_p_start', 'control_xmins'),
        'role_control': ('role_control_p_start', 'role_control_xmins'),
        'v4': ('v4_workload_start_p_start', 'v4_workload_start_xmins')}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def metrics(frame, arm):
    pc, mc = ARMS[arm]
    p = frame[pc].to_numpy(float)
    y = frame.y.to_numpy(float)
    err = frame[mc].to_numpy(float) - frame.minutes.to_numpy(float)
    clipped = np.clip(p, 1e-12, 1-1e-12)
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(abs(float((p[bins == b]-y[bins == b]).sum())) for b in range(10))/len(p)
    return dict(n=len(frame), minutes_mae=float(abs(err).mean()),
                minutes_rmse=float(np.sqrt((err**2).mean())), minutes_bias=float(err.mean()),
                start_brier=float(((p-y)**2).mean()),
                start_log_loss=float(-(y*np.log(clipped)+(1-y)*np.log1p(-clipped)).mean()),
                mean_predicted_minutes=float(frame[mc].mean()), actual_mean_minutes=float(frame.minutes.mean()),
                mean_p_start=float(p.mean()), actual_start_rate=float(y.mean()),
                calibration_ece_10_fixed_bins=float(ece))

def main():
    if OUT.exists():
        raise FileExistsError('Immutable diagnostic already exists')
    folder = ROOT / 'analysis/results/deadline-joint-inputs-v1'
    manifest = json.loads((folder/'manifest.json').read_text())
    # Verify pre-existing provenance before reading evaluation outcomes.
    for source in manifest['sources']:
        assert sha(ROOT/source['path']) == source['sha256'], source['path']
    inputs = read_frozen_table(folder, 'inputs')
    excluded = read_frozen_table(folder, 'excluded_fixtures')
    assert inputs.fixture_uuid.nunique() == 144 and len(inputs) == 11794
    assert not inputs[KEYS].duplicated().any()
    assert not set(inputs.fixture_uuid) & set(excluded.fixture_uuid)
    vpath = ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    bpath = ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    v = pd.read_csv(vpath)
    b = pd.read_csv(bpath)
    frame = inputs.merge(v[KEYS+['team','player','expected_role','role_information_change',
                    'target_role_case_posthoc','y','minutes','workload_start_p_start','workload_start_xmins',
                    'role_control_p_start','role_control_xmins']], on=KEYS, validate='one_to_one')
    assert len(frame) == len(inputs)
    matched = frame.merge(b[KEYS+['y','minutes','p_start_v2','expected_minutes_v2']],on=KEYS,
                          suffixes=('', '_v2'),validate='one_to_one')
    assert len(matched) == len(frame)
    assert matched.y.eq(matched.y_v2).all() and matched.minutes.eq(matched.minutes_v2).all()
    assert np.allclose(matched.control_p_start,matched.p_start_v2,rtol=0,atol=1e-12)
    assert np.allclose(matched.control_xmins,matched.expected_minutes_v2,rtol=0,atol=1e-12)
    assert np.allclose(frame.v4_workload_start_p_start,frame.workload_start_p_start,rtol=0,atol=1e-12)
    assert np.allclose(frame.v4_workload_start_xmins,frame.workload_start_xmins,rtol=0,atol=1e-12)
    with sqlite3.connect(ROOT/'work/core.sqlite3') as conn:
        truth = pd.read_sql_query("SELECT DISTINCT fixture_uuid,player_uuid,team_id,gw,started,minutes "
                                  "FROM player_fixture_observations WHERE season='2025-26'",conn)
    joined = frame.merge(truth,on=KEYS,suffixes=('', '_core'),validate='one_to_one')
    assert len(joined) == len(frame)
    assert joined.started.eq(joined.y).all() and joined.minutes_core.eq(joined.minutes).all()
    for arm,(pc,mc) in ARMS.items():
        assert frame[pc].between(0,1).all() and frame[mc].between(0,90).all()
        assert np.isfinite(frame[[pc,mc]].to_numpy()).all()
    score = {arm:metrics(frame,arm) for arm in ARMS}
    differences = {arm:{key:score['v4'][key]-score[arm][key] for key in
                   ['minutes_mae','minutes_rmse','minutes_bias','start_brier','start_log_loss','calibration_ece_10_fixed_bins']}
                   for arm in ['original_v2','role_control']}
    OUT.mkdir(parents=True)
    groups = []
    frame['role_information_change_band'] = pd.cut(frame.role_information_change,
        bins=[-np.inf,.01,.05,.1,np.inf],labels=['below_0.01','0.01_to_0.05','0.05_to_0.1','at_least_0.1'],right=False)
    for column in ['gw','pos','expected_role','role_information_change_band','target_role_case_posthoc']:
        for key,g in frame.groupby(column,dropna=False):
            for arm in ARMS:
                groups.append(dict(dimension=column,group=str(key),arm=arm,**metrics(g,arm)))
    frame['actual_appearance_case'] = np.where(frame.y.eq(1),'starter',np.where(frame.minutes.gt(0),'substitute','did_not_play'))
    for key,g in frame.groupby('actual_appearance_case'):
        for arm in ARMS:
            groups.append(dict(dimension='actual_appearance_case_posthoc',group=key,arm=arm,**metrics(g,arm)))
    pd.DataFrame(groups).to_csv(OUT/'group_metrics.csv',index=False)
    calibration = []
    for arm,(pc,_) in ARMS.items():
        bins = np.minimum((frame[pc]*10).astype(int),9)
        for index in range(10):
            g = frame[bins == index]
            calibration.append(dict(arm=arm,bin_lower=index/10,bin_upper=(index+1)/10,n=len(g),
                                    mean_probability=float(g[pc].mean()) if len(g) else None,
                                    actual_start_rate=float(g.y.mean()) if len(g) else None))
    pd.DataFrame(calibration).to_csv(OUT/'start_calibration.csv',index=False)
    pd.DataFrame([dict(arm=arm,**values) for arm,values in score.items()]).to_csv(OUT/'overall_metrics.csv',index=False)
    # GW block resampling preserves within-GW player/fixture dependencies.
    rng = np.random.default_rng(20261004)
    weeks = sorted(frame.gw.unique())
    blocks = rng.integers(0,len(weeks),size=(2000,len(weeks)))
    intervals = {}
    for arm,(pc,mc) in ARMS.items():
        if arm == 'v4': continue
        p,m = ARMS['v4']
        losses = dict(minutes_mae=abs(frame[m]-frame.minutes)-abs(frame[mc]-frame.minutes),
                      start_brier=(frame[p]-frame.y)**2-(frame[pc]-frame.y)**2)
        intervals[arm] = {}
        for key,loss in losses.items():
            grouped = pd.DataFrame(dict(gw=frame.gw,loss=loss)).groupby('gw').loss.agg(['sum','count']).loc[weeks]
            estimates = grouped['sum'].to_numpy()[blocks].sum(axis=1)/grouped['count'].to_numpy()[blocks].sum(axis=1)
            intervals[arm][key] = dict(lower=float(np.quantile(estimates,.025)),upper=float(np.quantile(estimates,.975)))
    keep = KEYS+['pos','expected_role','y','minutes','actual_appearance_case']+[c for pair in ARMS.values() for c in pair]
    raw = frame[keep].sort_values(KEYS).to_csv(index=False).encode()
    packed = gzip.compress(raw,mtime=0)
    for index,start in enumerate(range(0,len(packed),32768)):
        (OUT/f'evaluated_rows.csv.gz.part-{index:04d}').write_bytes(packed[start:start+32768])
    result = dict(classification='reused_diagnostic_not_new_holdout',season='2025-26',gw_range=[22,38],
                  fixtures=144,rows=len(frame),excluded_whole_fixtures=26,metrics=score,v4_minus= differences,
                  bootstrap=dict(method='2000 paired GW-block resamples of 17 reused GWs; exploratory, not independent confirmation',seed=20261004,intervals_95_percent=intervals),
                  no_fitting=True,no_model_policy_changes=True,
                  evaluated_rows_uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
                  evaluated_rows_compressed_sha256=hashlib.sha256(packed).hexdigest(),
                  comparisons=dict(original_v2='Exact unchanged control used in the 144-fixture joint point diagnostic',
                                   role_control='Internal role-only ablation; isolates additional workload features',
                                   v4='Frozen development-selected workload_start; not workload_decomposition'),
                  limitations=['GW22-38 reused after development; not new holdout',
                               'Incomplete all-competition history; FA Cup absent and other gaps documented',
                               '26 whole fixtures excluded identically for unverified roster evidence',
                               'Actual starter/substitute and target-role groups are posthoc descriptive only',
                               'Conditional starter/substitute errors assess expected total minutes, not conditional duration forecasts',
                               'V2 control inherits GW-order history availability; current cohort verification does not recertify it'],
                  sources=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in [vpath,bpath,folder/'manifest.json',Path(__file__)]],
                  verification=dict(forecast_values_match_frozen_sources=True,targets_match_both_forecast_files_and_core=True,
                                    rows_unique=True,both_arms_identical_cohort=True),
                  outputs=[dict(path=p.name,sha256=sha(p)) for p in sorted(OUT.iterdir())])
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(metrics=score,v4_minus=differences,bootstrap=result['bootstrap']),indent=2))

if __name__ == '__main__':
    main()
