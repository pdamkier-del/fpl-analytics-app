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
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _sync_directory(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def write_frame(path,frame):
    """Keep the previous complete CSV if serialization or gzip validation fails."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    try:
        with open(temporary,'wb') as raw:
            with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
                with io.TextIOWrapper(compressed,encoding='utf-8') as stream:
                    frame.to_csv(stream,index=False)
            raw.flush();os.fsync(raw.fileno())
        with gzip.open(temporary,'rb') as stream:
            while stream.read(1024*1024):pass
        os.replace(temporary,path)
        _sync_directory(path.parent)
    finally:temporary.unlink(missing_ok=True)
