"""Independently recompute saved direct-minute metrics and report accounting."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'analysis/results/direct-minutes-v4-diagnostic-v1'

def main():
    m = json.loads((OUT/'manifest.json').read_text())
    checks = 0
    for item in m['sources']:
        assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest() == item['sha256']
        checks += 1
    for item in m['outputs']:
        assert hashlib.sha256((OUT/item['path']).read_bytes()).hexdigest() == item['sha256']
        checks += 1
    packed = b''.join(p.read_bytes() for p in sorted(OUT.glob('evaluated_rows.csv.gz.part-*')))
    assert hashlib.sha256(packed).hexdigest() == m['evaluated_rows_compressed_sha256']
    raw = gzip.decompress(packed)
    assert hashlib.sha256(raw).hexdigest() == m['evaluated_rows_uncompressed_sha256']
    frame = pd.read_csv(io.BytesIO(raw));checks += 2
    assert len(frame) == 11794 and frame.fixture_uuid.nunique() == 144
    assert not frame[['fixture_uuid','player_uuid']].duplicated().any()
    assert set(frame.gw) == set(range(22,39));checks += 3
    arms = {'original_v2':('control_p_start','control_xmins'),
            'role_control':('role_control_p_start','role_control_xmins'),
            'v4':('v4_workload_start_p_start','v4_workload_start_xmins')}
    def recompute(g,pc,mc):
        err = g[mc]-g.minutes;p = g[pc].clip(1e-12,1-1e-12)
        return dict(minutes_mae=float(err.abs().mean()),minutes_rmse=float(np.sqrt((err**2).mean())),
                    minutes_bias=float(err.mean()),start_brier=float(((g[pc]-g.y)**2).mean()),
                    start_log_loss=float(-(g.y*np.log(p)+(1-g.y)*np.log(1-p)).mean()))
    calibration = pd.read_csv(OUT/'start_calibration.csv')
    for arm,(pc,mc) in arms.items():
        for key,value in recompute(frame,pc,mc).items():
            assert np.isclose(value,m['metrics'][arm][key],atol=1e-12,rtol=0);checks += 1
        c = calibration[calibration.arm==arm]
        assert c.n.sum()==len(frame)
        bins=np.minimum((frame[pc]*10).astype(int),9)
        for i,r in enumerate(c.itertuples()):
            g=frame[bins==i];assert len(g)==r.n
            if len(g):
                assert np.isclose(g[pc].mean(),r.mean_probability,atol=1e-12,rtol=0)
                assert np.isclose(g.y.mean(),r.actual_start_rate,atol=1e-12,rtol=0)
            checks += 1
        ece=float((c.n*(c.mean_probability-c.actual_start_rate).abs()).sum()/len(frame))
        assert np.isclose(ece,m['metrics'][arm]['calibration_ece_10_fixed_bins'],atol=1e-12,rtol=0);checks += 1
    groups=pd.read_csv(OUT/'group_metrics.csv')
    for dimension in groups.dimension.unique():
        for arm in arms:
            assert groups[(groups.dimension==dimension)&(groups.arm==arm)].n.sum()==len(frame);checks += 1
    policies=json.loads((ROOT/'analysis/results/season-2025-26-mechanics-v1/verification.json').read_text())['policy_checks']
    for item in policies:
        assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'];checks += 1
    report=dict(passed=True,checks=checks,rows=len(frame),fixtures=144,source_and_output_hashes_verified=True,
                saved_row_metrics_recomputed=True,calibration_counts_and_values_recomputed=True,
                all_strata_partition_entire_cohort=True,policy_hashes_unchanged=True,
                classification=m['classification'])
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
