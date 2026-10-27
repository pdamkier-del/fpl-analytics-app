"""Isolate verified historical source packs; never overwrite live work/data."""
from pathlib import Path
import argparse,json,shutil,zipfile,hashlib
import requests
import pandas as pd
from restore_live_input_checkpoint import restore as restore_inputs
from restore_live_vfinal_checkpoint import restore
import build_current_b_inputs as producer
from backtest_current_season_b import ROOT,BASE,digest

def prepare(gw,out,ledger=None,release_manifest=None):
    out=Path(out).resolve()
    if ROOT==out or ROOT in out.parents and 'work'not in out.relative_to(ROOT).parts:raise ValueError('Use an isolated work/scratch output')
    source=out/'source';source.mkdir(parents=True,exist_ok=True)
    if release_manifest:
        from current_diagnostic_checkpoint import allowed
        manifest_path=Path(release_manifest);m=json.loads(manifest_path.read_text())
        if m['origin_gw']!=gw or not m['archive_url'].startswith('https://github.com/pdamkier-del/fpl-analytics-app/releases/download/'):raise ValueError('Invalid historical release witness')
        local=manifest_path.with_suffix('.zip')
        if local.exists():payload=local.read_bytes()
        else:
            r=requests.get(m['archive_url'],timeout=60);r.raise_for_status();payload=r.content
        if hashlib.sha256(payload).hexdigest()!=m['archive_sha256']:raise ValueError('Historical release checksum mismatch')
        import io
        with zipfile.ZipFile(io.BytesIO(payload))as z:
            if len(z.namelist())!=len(m['files'])or set(z.namelist())!=set(m['files']):raise ValueError('Historical release membership mismatch')
            for name in z.namelist():
                data=z.read(name)
                if not allowed(name)or hashlib.sha256(data).hexdigest()!=m['files'][name]:raise ValueError('Unsafe/corrupt historical source')
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        (out/'release-witness.json').write_bytes(manifest_path.read_bytes())
    elif gw==6:
        restore_inputs(source);restore(ROOT/'model/checkpoints/live_vfinal_20261010_v1',source)
    elif gw==7:
        restore(ROOT/'model/checkpoints/live_gw7_sources_20261010_v1',source);restore(ROOT/'model/checkpoints/live_vfinal_gw7_20261010_v2',source)
    elif gw==8:
        manifest=json.loads((ROOT/'work/live-final-model/source_manifest.json').read_text())
        if manifest['target_gw']!=8:raise ValueError('The retained GW8 source pack is no longer available')
        for name in [BASE,Path('work/live-final-model')]:
            (source/name).mkdir(parents=True,exist_ok=True)
        for name in ['vfinal_live_full_simulator_input.csv.gz','player_fixture_observations.csv.gz','classified_starters.csv.gz','verified_penalty_attempts.csv.gz','verified_penalty_team_sides.csv.gz']:
            shutil.copy2(ROOT/BASE/name,source/BASE/name)
        for name in ['bootstrap.json','fixtures.json','source_manifest.json','match_actuals.jsonl.gz','player_match_events.jsonl.gz','live_bps_source_audit.json']:
            shutil.copy2(ROOT/'work/live-final-model'/name,source/'work/live-final-model'/name)
        for r in manifest['sources']:
            original=ROOT/r['path']
            if original.exists():
                if digest(original)!=r['sha256']:raise ValueError('Raw GW8 source changed')
                target=source/r['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
        raw=source/'data_v1_1/raw/all-competitions-2026-27';raw.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'data_v1_1/raw/all-competitions-2026-27/lineups.csv',raw/'lineups.csv')
    else:raise ValueError('No complete before-deadline PM capsule for this origin')
    work=source/'work/live-final-model';base=source/BASE
    old=json.loads((work/'source_manifest.json').read_text());(work/'original-source-manifest.json').write_text(json.dumps(old,sort_keys=True))
    pm=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
    if not pm.gw.eq(gw).all()or pm.cutoff.nunique()!=1:raise ValueError('Historical PM capsule origin mismatch')
    cut=pd.Timestamp(pm.cutoff.iloc[0]);boot_times=[s['observed_at']for s in old['sources']if s['url'].endswith('/bootstrap-static/')]
    if not boot_times:raise ValueError('Original bootstrap capture receipt missing')
    old['bootstrap_observed_at']=max(boot_times,key=pd.Timestamp)
    if not all(pd.Timestamp(s['observed_at'])<cut for s in old['sources']):raise ValueError('Source acquisition follows original PM cutoff')
    old['observed_at']=cut.isoformat();old['backtest_adapter']={'original_manifest':'original-source-manifest.json','feature_cutoff_source':'unchanged verified original PM table','source_capture_times_unchanged':True}
    (work/'source_manifest.json').write_text(json.dumps(old,sort_keys=True))
    archives=work/'predeadline_2026_archives';archives.mkdir(exist_ok=True)
    for p in (ROOT/'work/live-final-model/predeadline_2026_archives').glob('gw*.json'):
        if pd.Timestamp(json.loads(p.read_text())['evidence']['snapshot_at_utc'])<cut:shutil.copy2(p,archives/p.name)
    # Role priors for the NP head use only observed prior fixtures. Original
    # historical q/H is reconstructed, not target performance or later roles.
    observed=pd.read_csv(base/'player_fixture_observations.csv.gz',low_memory=False)
    if not (base/'reconstructed_training_features.csv.gz').exists():
        roles=pd.read_csv(ROOT/BASE/'reconstructed_training_features.csv.gz',low_memory=False)
        roles=roles[roles.fixture_uuid.isin(observed.fixture_uuid)&pd.to_datetime(roles.outcome_known_at,utc=True).lt(cut)]
        roles.to_csv(base/'reconstructed_training_features.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    for name,target in [('current-B-role-training',ROOT/'work/current-B-role-training'),('core.sqlite3',ROOT/'work/core.sqlite3'),('mm-integration-source',ROOT/'work/mm-integration-source')]:
        link=source/'work'/name
        if not link.exists():link.symlink_to(target)
    for name in ['scripts','analysis']:
        if not (source/name).exists():(source/name).symlink_to(ROOT/name)
    producer.ROOT=source
    producer.WORK=work;producer.BASE=base
    producer.build(out/'inputs',ROOT/'work/current-B-role-training',ledger)
    return out/'inputs',source

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gw',type=int,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--ledger',type=Path);p.add_argument('--release-manifest',type=Path);a=p.parse_args();prepare(a.gw,a.out,a.ledger,a.release_manifest)
