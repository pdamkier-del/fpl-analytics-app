"""Atomic, fully validated public model input captures; no model mathematics."""
import gzip,io,json,os
from pathlib import Path


def checked_records(path):
    # Read and verify the gzip trailer before any costly simulation begins.
    with gzip.open(path,'rt') as stream:
        return [json.loads(line) for line in stream]


def write_records(path,records):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    try:
        with open(temporary,'wb') as raw:
            with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
                with io.TextIOWrapper(compressed,encoding='utf-8') as stream:
                    for record in records:stream.write(json.dumps(record,default=lambda x:x.item())+'\n')
            raw.flush();os.fsync(raw.fileno())
        verified=checked_records(temporary)
        if len(verified)!=len(records):raise ValueError('Incomplete model input capture')
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
