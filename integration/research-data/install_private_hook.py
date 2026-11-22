"""Install PR43's completion hook on a disposable verified runtime build.

No numerical source or worker entrypoint is changed. Never run on a live service.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
HOOK="""            # Private research receipt, after original worker and source/deadline gates.
            from evaluation_ops.ts_capture import after_success
            result['evaluation_capture']=after_success(forecast,body['state'],result)
"""
ROUTES="""
from evaluation_ops.private_routes import register
register(app,jobs,lock,ORIGIN,TTL)
"""


def install(destination):
    destination=destination.resolve()
    if destination==ROOT.resolve():
        raise ValueError('Use a disposable frozen runtime build')
    expected=json.loads((Path(__file__).parent/'frozen-source-hashes.json').read_text())
    source=destination/'service/app.py'
    app=source.read_text()
    original=app.replace(HOOK,'').removesuffix(ROUTES)
    for path,digest in expected.items():
        raw=original.encode() if path=='service/app.py' else (destination/path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:
            raise ValueError('Frozen runtime source mismatch: '+path)
    prefix="                result['forecast_variant']=forecast['model']\n"
    anchor=prefix+"            (directory/'result.json').write_text(json.dumps(result,allow_nan=False))\n            jobs[identifier]['status']='completed'"
    if original.count(anchor)!=1:
        raise ValueError('Completion boundary is not uniquely identified')
    patched=original.replace(anchor,prefix+HOOK+anchor[len(prefix):])+ROUTES
    copies=['evaluation_ops/__init__.py','evaluation_ops/ts_capture.py','evaluation_ops/private_routes.py',
            'analysis/followup-41-20261122/code/private_ts_ledger.py',
            'integration/research-data/frozen-ts-config.json']
    for p in copies:
        target=destination/p;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/p,target)
    source.write_text(patched)
    files={p:hashlib.sha256((destination/p).read_bytes()).hexdigest() for p in [*expected,*copies]}
    receipt=dict(schema='fpl-private-capture-runtime/v1',model_source='161b67b6fb8786a38e78c245b92a03ad841575d8',
                 ts_version='TS v3',ts_config_sha256=files['integration/research-data/frozen-ts-config.json'],
                 numerical_sources_unchanged=True,files=files)
    (destination/'integration/research-data/runtime-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('runtime',type=Path);a=p.parse_args()
    r=install(a.runtime)
    print(json.dumps({'status':'installed_on_verified_build','model_source':r['model_source'],'files_verified':len(r['files'])}))
