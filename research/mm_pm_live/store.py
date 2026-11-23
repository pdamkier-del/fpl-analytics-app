"""Research-only write-once state/report assets. No forecast/app writes."""
import json
from pathlib import Path
import tempfile
from labels import digest


def canonical(doc):
    return json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def public_only(value):
    if isinstance(value,dict):
        if set(map(str.lower,value))&{'manager_state','manager_id','entry_id','bank_tenths','free_transfers','purchase_price_tenths','password','token','authorization','cookie','private_nonce'}:
            raise ValueError('Private fields forbidden in research reports')
        for item in value.values():public_only(item)
    elif isinstance(value,list):
        for item in value:public_only(item)


def get_record(backend,tag):
    release=backend.find(tag)
    if release is None:return None
    assets=release.get('assets',[])
    if not assets:return None
    if len(assets)!=1 or assets[0]['name']!='record.json':raise ValueError('Incomplete or unexpected research record')
    doc=json.loads(backend.content(assets[0]));h=doc.pop('record_sha256')
    if digest(doc)!=h:raise ValueError('Research record changed')
    return doc


def put_record(backend,tag,doc,target):
    public_only(doc)
    previous=get_record(backend,tag)
    if previous is not None:
        if previous!=doc:raise ValueError('Research observation is immutable')
        return previous
    # A concurrent/partial release is never clobbered. Same concurrency group in CI.
    release=backend.find(tag)or backend.create(tag,target)
    with tempfile.TemporaryDirectory()as temp:
        path=Path(temp)/'record.json'
        path.write_bytes(canonical({**doc,'record_sha256':digest(doc)}))
        backend.upload(tag,path)
    if get_record(backend,tag)!=doc:raise ValueError('Research record recovery failed')
    return doc
