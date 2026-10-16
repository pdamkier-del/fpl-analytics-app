"""Durable allowlisted public MM research capsule; no private manager inputs."""
import base64,hashlib,io,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/role-injury-mm-20261016';PACK=ROOT/'checkpoints/role_injury_mm_20261016'
def sha(b):return hashlib.sha256(b).hexdigest()
def package():
    files={}
    for name in ['report.json','summary.json','coverage.csv','source_manifest.json','source_backed_news.csv.gz','predictions.npz','tactical_profiles.json']:
        files['results/'+name]=(OUT/name).read_bytes()
    for name in ['observations.jsonl.gz','predeadline_strict.jsonl.gz','source_manifest.json','SHA256_MANIFEST.json']:
        files['news-2024/'+name]=(ROOT/'work/news-2024-push-verified'/name).read_bytes()
    for name in ['2024-25_candidates.npz','2025-26_candidates.npz','selection.json','capsule_manifest.json']:
        files['mm-source/'+name]=(ROOT/'work/mm-source'/name).read_bytes()
    # No Core DB, PM tables, manager state, prices, token files or arbitrary glob.
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
        for name,b in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,16,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b)
    raw=buf.getvalue();(PACK/'parts').mkdir(parents=True,exist_ok=True);parts=[]
    for i,start in enumerate(range(0,len(raw),180000)):
        b=raw[start:start+180000];name=f'parts/{i:04d}.b64';(PACK/name).write_text(base64.b64encode(b).decode()+'\n');parts.append(dict(path=name,bytes=len(b),sha256=sha(b)))
    m=dict(classification='PUBLIC_MM_ONLY_RESEARCH_NOT_PRODUCTION',code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),zip_sha256=sha(raw),zip_bytes=len(raw),parts=parts,files={n:dict(bytes=len(b),sha256=sha(b))for n,b in files.items()},locked_model_active=False,pm_ts_chips_points_not_run=True)
    (PACK/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('Public MM capsule',len(raw),'bytes',len(parts),'parts')
def restore(destination):
    m=json.loads((PACK/'manifest.json').read_text());chunks=[]
    for p in m['parts']:
        b=base64.b64decode((PACK/p['path']).read_text(),validate=False)
        if len(b)!=p['bytes']or sha(b)!=p['sha256']:raise ValueError('Corrupt capsule part')
        chunks.append(b)
    raw=b''.join(chunks)
    if sha(raw)!=m['zip_sha256']:raise ValueError('Corrupt capsule archive')
    with zipfile.ZipFile(io.BytesIO(raw))as z:
        if set(z.namelist())!=set(m['files']):raise ValueError('Unexpected archive members')
        for name in z.namelist():
            p=(destination/name).resolve()
            if not p.is_relative_to(destination.resolve()):raise ValueError('Unsafe path')
            b=z.read(name)
            if sha(b)!=m['files'][name]['sha256']:raise ValueError('Corrupt archive member')
            if p.exists()and p.read_bytes()!=b:raise ValueError('Refuse different existing research evidence')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    print('All MM capsule files verified')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--restore',type=Path);a=p.parse_args();restore(a.restore)if a.restore else package()
