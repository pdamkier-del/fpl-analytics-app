"""Serve the generated B build and unchanged, ephemeral TS worker on loopback."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

from flask import Flask, abort, jsonify, request, send_from_directory

CHIPS = {'wildcard': 'wildcard', 'freehit': 'free_hit', 'bboost': 'bench_boost', '3xc': 'triple_captain'}


def official(path):
    url = 'https://fantasy.premierleague.com/api/' + path
    with urlopen(Request(url, headers={'Cache-Control': 'no-cache'}), timeout=15) as response:
        return json.load(response)


def squad_draft(entry, target, get=official):
    summary = get(f'entry/{entry}/')
    event = summary['current_event']
    if summary['id'] != entry or type(event) is not int or not 1 <= event < target:
        raise ValueError('Ingen tidligere offentlig holdopstilling til denne gameweek.')
    picks = get(f'entry/{entry}/event/{event}/picks/')
    if picks['entry_history']['event'] != event or picks['active_chip'] == 'freehit':
        raise ValueError('Seneste offentlige hold kan være midlertidigt. Bekræft din permanente trup i FPL.')
    ordered = sorted(picks['picks'], key=lambda player: player['position'])
    ids = [player['element'] for player in ordered]
    if [player['position'] for player in ordered] != list(range(1, 16)) or len(set(ids)) != 15:
        raise ValueError('Det officielle svar indeholder ikke 15 entydige spillere.')
    active_chips = {chip: [] for chip in CHIPS.values()}
    for chip in get(f'entry/{entry}/history/')['chips']:
        if chip['name'] in CHIPS and 1 <= chip['event'] <= event:
            active_chips[CHIPS[chip['name']]].append(chip['event'])
    return {
        'gw': target, 'source': f'Officiel GW{event}-trup bekræftet i FPL',
        'source_gw': event, 'draft_only': True, 'squad': [{'id': pid} for pid in ids],
        'chips_used': active_chips,
    }


def fresh_forecast(forecast, now):
    cutoff = datetime.fromisoformat(forecast['data_asof'])
    deadline = datetime.fromisoformat(forecast['origin_deadline'])
    return cutoff <= now < deadline and now - cutoff <= timedelta(hours=36)


def create(runtime, public, port):
    sys.path.insert(0, str(runtime))
    from service import app as original

    origin = f'http://127.0.0.1:{port}'
    original.ORIGIN = origin
    allowed = {
        'mm-preview/current/forecast.json': public / 'mm-preview/current/forecast.json',
        'mm-preview/current/tc-samples.csv.gz': public / 'mm-preview/current/tc-samples.csv.gz',
    }
    def get_public(name):
        if name == 'current-players.json':
            bundle = public / 'mm-preview/current/existing-app-data.json'
            return json.dumps(json.loads(bundle.read_bytes())['documents'][name]).encode()
        return allowed[name].read_bytes()

    original.get_public = get_public
    original_verify = original.verify_snapshot_now

    def verify_snapshot(forecast):
        if not fresh_forecast(forecast, datetime.now(timezone.utc)):
            raise ValueError('Prognosen er udløbet.')
        from fpl_v1_1_model.forecast_snapshot import require_official_catalog
        require_official_catalog(forecast, official('bootstrap-static/')['elements'])
        return original_verify(forecast)

    original.verify_snapshot_now = verify_snapshot
    app = Flask(__name__, static_folder=None)

    @app.before_request
    def loopback_only():
        if request.host != f'127.0.0.1:{port}':
            abort(403)

    @app.after_request
    def no_cache(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/manager-service.json')
    def config():
        return jsonify(
            url='/preview-api', status='original_python_service',
            runtime='original_locked_python', supports_public_squad_import=True,
        )

    @app.get('/preview-api/squad/<entry>')
    def draft(entry):
        if not re.fullmatch(r'[1-9][0-9]{0,8}', entry):
            abort(400)
        target = json.loads(get_public('current-players.json'))['next_gw']
        try:
            return jsonify(squad_draft(int(entry), target))
        except ValueError as error:
            return jsonify(error=str(error)), 422
        except (OSError, KeyError, TypeError):
            return jsonify(error='Den officielle trup kunne ikke verificeres.'), 502

    @app.get('/preview-api/health')
    def health():
        return original.health()

    @app.post('/preview-api/preview/plans')
    def plan():
        if request.headers.get('Origin') != origin:
            abort(403)
        forecast = json.loads(get_public('mm-preview/current/forecast.json'))
        if not fresh_forecast(forecast, datetime.now(timezone.utc)):
            return jsonify(error='Prognosen er udløbet. Afventer en ny verificeret prognose.'), 409
        return original.create(preview=True)

    @app.get('/preview-api/plans/<identifier>')
    def status(identifier):
        return original.status(identifier)

    @app.get('/<path:name>')
    def static_file(name):
        return send_from_directory(public, name)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('public', type=Path)
    parser.add_argument('--port', type=int, default=18125)
    args = parser.parse_args()
    create(args.runtime.resolve(), args.public.resolve(), args.port).run('127.0.0.1', args.port)
