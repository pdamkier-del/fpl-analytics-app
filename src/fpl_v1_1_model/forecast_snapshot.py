"""Content identity for forecasts; metadata only, no model decisions."""
import hashlib,json

def forecast_digest(payload):
    content={k:v for k,v in payload.items() if k!='forecast_sha256'}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()

def seal_forecast(payload):
    return {**payload,'forecast_sha256':forecast_digest(payload)}

def require_snapshot(payload,expected=None):
    digest=forecast_digest(payload)
    if payload.get('forecast_sha256')!=digest or (expected is not None and expected!=digest):
        raise ValueError('Forecast snapshot changed or content checksum missing/invalid')
    return digest
