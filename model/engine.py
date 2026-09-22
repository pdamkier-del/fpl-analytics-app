from __future__ import annotations
from pathlib import Path
import json, datetime, re

ROOT = Path(__file__).resolve().parent
VERSIONS = ROOT / 'versions'
RUNS = ROOT / 'runs'
ACTIVE = ROOT / 'active.json'
BASE_DATA = ROOT / 'base_data.json'

SAFE_VERSION = re.compile(r'[^A-Za-z0-9._-]+')

def _read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def active_config():
    return _read(ACTIVE)

def list_versions():
    out=[]
    for p in sorted(VERSIONS.glob('*.json')):
        try:
            d=_read(p)
            out.append({k:d.get(k) for k in ('version','parent','created_utc','notes','engine_mode')})
        except Exception:
            pass
    return out

def save_version(payload: dict):
    current=active_config()
    raw=str(payload.get('version') or '').strip()
    version=SAFE_VERSION.sub('-', raw).strip('-._')
    if not version:
        raise ValueError('Version name is required')
    if len(version)>80:
        raise ValueError('Version name is too long')
    cfg=payload.get('config')
    if not isinstance(cfg, dict):
        raise ValueError('config must be an object')
    doc={
        'version':version,
        'parent':current.get('version'),
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'notes':str(payload.get('notes') or ''),
        'engine_mode':cfg.get('engine_mode','bridge_passthrough'),
        'team_model':cfg.get('team_model',{}),
        'decision_model':cfg.get('decision_model',{}),
        'component_modes':cfg.get('component_modes',{}),
        'advanced_parameters':cfg.get('advanced_parameters',{}),
    }
    path=VERSIONS/f'{version}.json'
    if path.exists():
        raise ValueError('That version already exists; use a new version name')
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    ACTIVE.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    return doc

def activate(version: str):
    version=SAFE_VERSION.sub('-',str(version)).strip('-._')
    p=VERSIONS/f'{version}.json'
    if not p.exists():
        raise ValueError('Unknown version')
    d=_read(p)
    ACTIVE.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    return d

def run_model():
    cfg=active_config()
    data=_read(BASE_DATA)
    meta=data.get('meta',{})
    # IMPORTANT: No forecast mathematics is invented here. Until each model
    # component is ported from the authoritative pipeline, this runner is a
    # reproducible passthrough of the current Live Data Bridge forecast.
    run={
        'run_id':datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'config_version':cfg.get('version'),
        'engine_mode':cfg.get('engine_mode'),
        'source_model_version':meta.get('model_version'),
        'players':len(data.get('forecasts',[])),
        'fixtures':len(data.get('fixtures',[])),
        'status':'completed_passthrough' if cfg.get('engine_mode')=='bridge_passthrough' else 'configuration_saved_engine_not_implemented'
    }
    (RUNS/f"{run['run_id']}.json").write_text(json.dumps(run,indent=2),encoding='utf-8')
    return run
