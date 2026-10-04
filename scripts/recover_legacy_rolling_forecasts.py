"""Recover original rolling forecasts as quarantined evidence, never v4 inputs."""
import argparse,gzip,hashlib,io,json,zipfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
IDS={'FPL_PHASE_5T_ROLLING_SEASON_REPLAY.zip':'libfile_b0346c80c6d08191bb1065dd110599c4',
     'FPL_PHASE_5W_JOINT_CHIP_SEQUENCE.zip':'libfile_d87b1ff8c25c8191959ddd62f35b8809',
     'FPL_PHASE_5Y_HIT_BUFFER.zip':'libfile_7244ff358fa08191aab9edd5adc69c97'}
PREFIX='outputs/v1_1/phase5t_rolling_reference/'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archives',type=Path,default=ROOT/'work/recovered-horizon-archives/FPL')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/legacy-rolling-recovery-v1')
    a=ap.parse_args()
    if a.out.exists():raise FileExistsError('Use a new immutable output directory')
    archives=[];members={};lineage=[]
    wanted={PREFIX+'rolling_phase5q_forecasts.csv':'player_gw_forecasts',PREFIX+'rolling_fixture_forecasts.csv':'fixture_forecasts',
            PREFIX+'cutoff_audit.csv':'original_cutoff_audit',PREFIX+'manifest.json':'original_manifest.json',
            'run_phase5t_rolling_reference.py':'original_rolling_builder.py','PHASE_5T_FULL_SEASON_REPLAY.md':'original_phase5t_notes.md'}
    for name,lid in IDS.items():
        path=a.archives/name;archives.append(dict(name=name,library_file_id=lid,bytes=path.stat().st_size,sha256=sha(path.read_bytes())))
        with zipfile.ZipFile(path) as z:
            for member,installed in wanted.items():
                if member not in z.namelist():continue
                raw=z.read(member)
                if installed in members and members[installed]!=raw:raise ValueError('Archive versions disagree: '+member)
                members[installed]=raw;lineage.append(dict(archive=name,member=member,installed=installed,bytes=len(raw),sha256=sha(raw)))
    if set(members)!=set(wanted.values()):raise ValueError('Incomplete original source recovery')
    a.out.mkdir(parents=True);outputs=[]
    for name,raw in members.items():
        if name.endswith(('.py','.md','.json')):
            (a.out/name).write_bytes(raw);continue
        packed=gzip.compress(raw,mtime=0);parts=[]
        for i,start in enumerate(range(0,len(packed),32768)):
            part=packed[start:start+32768];path=f'{name}.csv.gz.part-{i:04d}';(a.out/path).write_bytes(part)
            parts.append(dict(path=path,bytes=len(part),sha256=sha(part)))
        outputs.append(dict(name=name,rows=len(pd.read_csv(io.BytesIO(raw))),parts=parts,compressed_sha256=sha(packed),uncompressed_sha256=sha(raw)))
    f=pd.read_csv(io.BytesIO(members['player_gw_forecasts']))
    pairs=set(zip(f.decision_gw.astype(int),f.gw.astype(int)))
    required={(origin,target) for origin in range(1,39) for target in range(origin,min(38,origin+5)+1)}
    if pairs!=required or not f.decision_gw.eq(f.origin_gw+1).all():raise ValueError('Original horizon index mismatch')
    m=dict(parent_checkpoint='40f1ba0d4036fd32c805081ad796f42b853568fd',classification='quarantined_legacy_reference_not_v4_not_new_holdout',
        full_season_ready=False,forecast_inputs_promoted=False,legacy_origin_target_cells=len(pairs),v4_origin_target_cells_recovered=0,
        original_model='Phase5Q legacy minutes + h12/ridge .25; differs from current frozen control/v4 common experiment',
        archives=archives,members=lineage,outputs=outputs,code_sha256=sha(Path(__file__).read_bytes()),
        disqualifying_source_findings=[
            'current_meta_by_origin reads same-target-GW merged_gw roster/team/position/value, not timestamped predeadline snapshots',
            'future horizon uses final archived season fixture schedule, not as-of schedule',
            'deadline_by_gw estimates first kickoff minus 90 minutes rather than verifies original deadline publication',
            'legacy player/team/minute/scoring model differs from restored frozen control/v4 paired inputs',
            'source original labels GW22-38 temporal validation; current recovery retains reused-diagnostic classification only'],
        unchanged='Core, active forecasts/results, original adapter/simulator/scoring and transfer/chip strategy')
    (a.out/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:m[k] for k in ['legacy_origin_target_cells','v4_origin_target_cells_recovered','forecast_inputs_promoted','full_season_ready']},indent=2))
if __name__=='__main__':main()
