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


def require_official_catalog(payload,elements):
    """Do not plan at stale prices/club/position while GW and cutoff stay valid."""
    players=payload.get('players')
    if not isinstance(players,list) or not players or not isinstance(elements,list) or not elements:
        raise ValueError('Forecast or official player catalogue missing')
    official={p['id']:p for p in elements}
    if len(official)!=len(elements) or len({p['id'] for p in players})!=len(players):
        raise ValueError('Duplicate official/forecast identities')
    if set(official)!={p['id'] for p in players}:
        raise ValueError('Official roster changed; fresh forecast required')
    for player in players:
        current=official[player['id']]
        if (player['price_tenths'],player['team_id'],player['position'])!=(current['now_cost'],current['team'],current['element_type']):
            raise ValueError('Official prices, clubs or positions changed; fresh forecast required')
    return True
