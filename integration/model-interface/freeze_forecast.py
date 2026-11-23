"""Export a read-only, content-addressed reference to a reviewed public B forecast."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

SHA256 = re.compile(r'[a-f0-9]{64}')
COMMIT = re.compile(r'[a-f0-9]{40}')


def freeze(published, destination, model_commit):
    if not COMMIT.fullmatch(model_commit):
        raise ValueError('Expected a complete Git model source commit')
    publication = json.loads((published / 'index.json').read_text())
    payload = (published / 'forecast.json').read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    forecast = json.loads(payload)
    identity = forecast.get('forecast_sha256')
    if (
        publication.get('forecast_file') != 'forecast.json'
        or publication.get('forecast_file_sha256') != digest
        or not isinstance(identity, str)
        or not SHA256.fullmatch(identity)
        or identity != publication.get('forecast_sha256')
        or forecast.get('model') != 'B-MM-PM-TS-v1'
        or publication.get('model') != forecast['model']
    ):
        raise ValueError('The published index does not identify the frozen B forecast')

    manifest = {
        'schema': 'fpl-frozen-forecast/v1',
        'model_source': model_commit,
        'model': forecast['model'],
        'season': forecast['season'],
        'gws': forecast['gws'],
        'data_cutoff': forecast['data_asof'],
        'origin_deadline': forecast['origin_deadline'],
        'forecast_sha256': identity,
        'payload_sha256': digest,
        'payload_file': 'forecast.json',
    }
    root = destination / digest
    root.mkdir(parents=True, exist_ok=True)
    files = {
        'forecast.json': payload,
        'manifest.json': (json.dumps(manifest, sort_keys=True) + '\n').encode(),
    }
    for name, content in files.items():
        path = root / name
        with tempfile.NamedTemporaryFile(dir=root) as temporary:
            temporary.write(content)
            temporary.flush()
            try:
                os.link(temporary.name, path)
            except FileExistsError:
                if path.read_bytes() != content:
                    raise ValueError(f'Frozen output already exists with different content: {path}') from None
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('published_current', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--model-commit', required=True)
    args = parser.parse_args()
    print(freeze(args.published_current, args.destination, args.model_commit))
