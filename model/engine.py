from __future__ import annotations
from pathlib import Path
import json, datetime, re

ROOT = Path(__file__).resolve().parent
VERSIONS = ROOT / 'versions'
RUNS = ROOT / 'runs'
ACTIVE = ROOT / 'active.json'
BASE_DATA = ROOT / 'base_data.json'
DEFAULTS = ROOT / 'defaults.json'

SAFE_VERSION = re.compile(r'[^A-Za-z0-9._-]+')


def _read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _merge(base, override):
    """Recursive dict merge; local/version values override shipped defaults."""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def default_config():
    if DEFAULTS.exists():
        return _read(DEFAULTS)
    return {}


def active_config():
    raw = _read(ACTIVE) if ACTIVE.exists() else {}
    return _merge(default_config(), raw)


def list_versions():
    out=[]
    for p in sorted(VERSIONS.glob('*.json')):
        try:
            d=_merge(default_config(), _read(p))
            out.append({k:d.get(k) for k in ('version','parent','created_utc','notes','engine_mode','methodology_version')})
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
        'methodology_version':cfg.get('methodology_version',current.get('methodology_version','live_simple_baseline_v0.1')),
        'engine_mode':cfg.get('engine_mode',current.get('engine_mode','bridge_passthrough')),
        'team_model':cfg.get('team_model',current.get('team_model',{})),
        'decision_model':cfg.get('decision_model',current.get('decision_model',{})),
        'forecast_parameters':cfg.get('forecast_parameters',current.get('forecast_parameters',{})),
        'component_modes':cfg.get('component_modes',current.get('component_modes',{})),
        'advanced_parameters':cfg.get('advanced_parameters',current.get('advanced_parameters',{})),
    }
    VERSIONS.mkdir(exist_ok=True)
    path=VERSIONS/f'{version}.json'
    if path.exists():
        raise ValueError('That version already exists; use a new version name')
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    ACTIVE.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    return _merge(default_config(), doc)


def activate(version: str):
    version=SAFE_VERSION.sub('-',str(version)).strip('-._')
    p=VERSIONS/f'{version}.json'
    if not p.exists():
        raise ValueError('Unknown version')
    raw=_read(p)
    ACTIVE.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
    return _merge(default_config(), raw)


def run_model():
    cfg=active_config()
    data=_read(BASE_DATA)
    meta=data.get('meta',{})
    # IMPORTANT: Forecast mathematics is still supplied by the authoritative
    # Live Data Bridge. Model Lab versions are real/versioned configuration,
    # but changing bridge parameters here does not silently fabricate a new
    # forecast. Components are ported into Python explicitly and separately.
    run={
        'run_id':datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'config_version':cfg.get('version'),
        'methodology_version':cfg.get('methodology_version'),
        'engine_mode':cfg.get('engine_mode'),
        'source_model_version':meta.get('model_version'),
        'players':len(data.get('forecasts',[])),
        'fixtures':len(data.get('fixtures',[])),
        'status':'completed_passthrough' if cfg.get('engine_mode')=='bridge_passthrough' else 'configuration_saved_engine_not_implemented'
    }
    RUNS.mkdir(exist_ok=True)
    (RUNS/f"{run['run_id']}.json").write_text(json.dumps(run,indent=2),encoding='utf-8')
    return run
