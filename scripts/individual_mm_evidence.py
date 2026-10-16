#!/usr/bin/env python3
"""Lossless public result capsule, including factorized per-row prediction arrays."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'analysis/results/individual-mm-20261015'
PACK=ROOT/'checkpoints/individual_mm_20261015'

def sha(b):return hashlib.sha256(b).hexdigest()

def encode_frame(frame):
    arrays={};categories=[]
    for col in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[col]):arrays['v_'+col]=frame[col].to_numpy()
        else:
            codes,labels=pd.factorize(frame[col],sort=False);arrays['c_'+col]=codes.astype(np.int32);arrays['l_'+col]=np.asarray(labels.astype(str),dtype=str);categories.append(col)
    arrays['_meta']=np.asarray(json.dumps(dict(columns=list(frame.columns),categories=categories)))
    buf=io.BytesIO();np.savez_compressed(buf,**arrays);return buf.getvalue()

def load_frame(path_or_bytes):
    source=io.BytesIO(path_or_bytes) if isinstance(path_or_bytes,bytes) else path_or_bytes
    with np.load(source,allow_pickle=False) as z:
        meta=json.loads(str(z['_meta']));out={}
        for col in meta['columns']:
            if col not in meta['categories']:out[col]=z['v_'+col]
            else:
                c=z['c_'+col];values=np.empty(len(c),dtype=object);values[:]=None;valid=c>=0;values[valid]=z['l_'+col][c[valid]];out[col]=values
    return pd.DataFrame(out)

def package():
    entries={}
    names=['selection.json','report.json','data_audit.json','horizon_selection.json','horizon_report.json','legacy_six_gw_contract.json','2024-25_pm_report.json','2025-26_pm_report.json','2024-25_pm_diagnostics.json','2025-26_pm_diagnostics.json','validation.json','source_manifest.json']
    for name in names:entries[name]=(RESULT/name).read_bytes()
    mm=['season','gw','fixture_uuid','player_uuid','team_id','pos','mode','p','s','q','c','x','y','minutes','cutoff','team_news_state','player_type']
    pm=['fixture_uuid','player_uuid','gw','mode','pos','team_id','xp','sim_minutes','total_points','minutes','appearance_points','goal_points','assist_points','cs_points','save_points','dc_points','negative_points','gc_points','penalty_save_points','expected_bonus']
    for season in ['2024-25','2025-26']:
        for kind,cols in [('candidates',mm),('pm_predictions',pm)]:
            frame=pd.read_csv(RESULT/f'{season}_{kind}.csv.gz',usecols=cols,low_memory=False,float_precision='round_trip')[cols]
            frame=frame.sort_values(['fixture_uuid','player_uuid','mode'],kind='stable').reset_index(drop=True)
            if kind=='pm_predictions' and frame['mode'].nunique()!=6:raise ValueError('Incomplete PM matrix')
            b=encode_frame(frame);decoded=load_frame(b)
            pd.testing.assert_frame_equal(frame,decoded,check_dtype=False,check_exact=True)
            entries[f'{season}_{kind}.npz']=b
    hc=['season','origin','target','horizon','origin_cutoff','fixture_uuid','player_uuid','team_id','p','x','role_p','role_x','control_p','control_x','started','minutes']
    f=pd.read_csv(RESULT/'horizon_predictions.csv.gz',usecols=hc,low_memory=False,float_precision='round_trip')[hc]
    b=encode_frame(f);pd.testing.assert_frame_equal(f,load_frame(b),check_dtype=False,check_exact=True);entries['horizon_predictions.npz']=b
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,b in sorted(entries.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,16,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b)
    data=buf.getvalue();(PACK/'parts').mkdir(parents=True,exist_ok=True);parts=[]
    for i,start in enumerate(range(0,len(data),65536)):
        b=data[start:start+65536];name=f'parts/evidence.zip.part-{i:04d}';(PACK/name).write_bytes(b);parts.append(dict(path=name,bytes=len(b),sha256=sha(b)))
    manifest=dict(classification='PUBLIC_RESEARCH_RESULTS_NOT_PRODUCTION_OR_TS_CERTIFICATION',zip_bytes=len(data),zip_sha256=sha(data),files={name:dict(bytes=len(b),sha256=sha(b)) for name,b in entries.items()},parts=parts,locked_model_active=False)
    (PACK/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(dict(zip_bytes=len(data),parts=len(parts),files=list(entries)),indent=2))

def restore(out):
    manifest=json.loads((PACK/'manifest.json').read_text());chunks=[]
    for item in manifest['parts']:
        p=(PACK/item['path']).resolve()
        if not p.is_relative_to(PACK.resolve()):raise ValueError('Unsafe part')
        b=p.read_bytes()
        if len(b)!=item['bytes'] or sha(b)!=item['sha256']:raise ValueError('Corrupt part')
        chunks.append(b)
    data=b''.join(chunks)
    if len(data)!=manifest['zip_bytes'] or sha(data)!=manifest['zip_sha256']:raise ValueError('Corrupt capsule')
    staged={}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(manifest['files']):raise ValueError('Unexpected capsule members')
        for name in z.namelist():
            if Path(name).name!=name:raise ValueError('Unsafe member')
            b=z.read(name);ref=manifest['files'][name]
            if len(b)!=ref['bytes'] or sha(b)!=ref['sha256']:raise ValueError('Corrupt member')
            if name.endswith('.npz'):load_frame(b)
            p=out/name
            if p.exists() and p.read_bytes()!=b:raise ValueError('Refusing to replace different evidence')
            staged[p]=b
    out.mkdir(parents=True,exist_ok=True)
    for p,b in staged.items():p.write_bytes(b)
    print('Verified and restored',len(staged),'research evidence files')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['package','restore']);p.add_argument('--out',type=Path,default=RESULT);a=p.parse_args();package() if a.stage=='package' else restore(a.out)
