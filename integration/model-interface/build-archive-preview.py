"""Build an isolated B preview only from a verified archive and its original UI data."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = 'pdamkier-del/fpl-analytics-app'
UI = '27bf5e1e1a17360bdbbfb41fbce7fe55679c6870'
ARCHIVE = 'd4d6e8046ad5d965cf41f5a8fce2b32a49fca16c'
ASSETS = Path(__file__).resolve().parent
FILES = {
    'current': ('index.json', 'forecast.json', 'mm.json', 'existing-app-data.json'),
    'gk': ('index.json', 'forecast.json', 'gk-mm.json', 'evidence.json'),
}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_capture(capture, archive, manifest):
    current, gk = capture / 'current', capture / 'gk'
    index, probabilities = read(current / 'index.json'), read(gk / 'index.json')
    for filename in ('index.json', 'forecast.json', 'mm.json'):
        require((current / filename).read_bytes() == gzip.decompress((archive / (filename + '.gz')).read_bytes()),
                f'Producer {filename} differs from the verified archive')
    require(index['forecast_sha256'] == manifest['forecast_sha256'], 'Unexpected forecast identity')
    require(sha(current / 'existing-app-data.json') == index['existing_app_data_sha256'], 'App bundle checksum mismatch')
    require(read(current / 'existing-app-data.json')['forecast_sha256'] == manifest['forecast_sha256'],
            'App bundle belongs to another forecast')
    for filename, key in [('forecast.json', 'forecast_sha256'), ('gk-mm.json', 'mm_sha256'), ('evidence.json', 'evidence_sha256')]:
        require(sha(gk / filename) == probabilities[key], f'Probability {filename} checksum mismatch')
    require((gk / 'forecast.json').read_bytes() == (current / 'forecast.json').read_bytes(),
            'Probability and transfer forecasts differ')


def live_window(manifest, news, now):
    cutoff = datetime.fromisoformat(manifest['data_cutoff'])
    deadline = datetime.fromisoformat(manifest['official_deadline'])
    return (news['next_gw'] == manifest['origin_gw']
            and datetime.fromisoformat(news['deadline']) == deadline
            and cutoff <= now < deadline and now - cutoff <= timedelta(hours=36))


def build(args):
    archive_root = args.archive_root.resolve()
    commit = subprocess.check_output(['git', '-C', str(archive_root), 'rev-parse', 'HEAD'], text=True).strip()
    require(commit == ARCHIVE, 'Archive helper checkout must be pinned to PR #53')
    require(subprocess.run(['git', '-C', str(archive_root), 'diff', '--quiet', 'HEAD', '--',
                            'integration/research-data', 'integration/model-interface/freeze_forecast.py']).returncode == 0,
            'Archive helpers have local modifications')
    sys.path.insert(0, str(archive_root / 'integration/research-data'))
    from archive import verify
    from automatic import download, inventory
    from releases import Github, recover

    out = args.out.resolve()
    require(not out.exists(), 'Use a new preview directory')
    now = datetime.now(timezone.utc)
    backend = Github(REPO)
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        tree = work / 'build'
        tree.mkdir()
        with (work / 'ui.tar').open('wb') as stream:
            subprocess.run(['git', '-C', str(args.repository), 'archive', UI, 'app', 'scripts'],
                           stdout=stream, check=True)
        subprocess.run(['tar', '-xf', str(work / 'ui.tar'), '-C', str(tree)], check=True)
        public = tree / 'app/mm-preview'
        subprocess.run([sys.executable, 'scripts/collect_dashboard_news.py'], cwd=tree, check=True)
        news = read(public / 'news/availability.json')
        tag = args.tag
        if tag is None:
            _, coverage, errors, _ = inventory(backend, now)
            require(not errors, 'Archive inventory has invalid receipts')
            matches = [x for x in coverage.values() if live_window(x, news, now)]
            require(len(matches) == 1, 'No unique current original in the verified archive')
            row = matches[0]
            tag = f"fpl-forecast-{row['season']}-gw{row['origin_gw']:02}-{row['revision_id']}"
        folder, _ = recover(tag, work / 'originals', backend)
        manifest = verify(folder)
        is_live = live_window(manifest, news, now)
        require(is_live or (args.allow_historical and args.tag), 'Archived forecast has expired or differs from official gameweek')
        receipt = read(folder / 'computation-receipt.json')
        capture = args.capture.resolve() if args.capture else work / 'producer-artifact'
        if not args.capture:
            download(REPO, receipt['run_id'], 'mm-current-live-preview', capture)
        verify_capture(capture, folder, manifest)
        for section, filenames in FILES.items():
            (public / section).mkdir(exist_ok=True)
            for filename in filenames:
                shutil.copyfile(capture / section / filename, public / section / filename)
        subprocess.run([sys.executable, 'scripts/integrate_desktop_probabilities.py'], cwd=tree, check=True)
        subprocess.run([sys.executable, str(ASSETS / 'preview-overlay.py'), str(public / 'app')], check=True)
        identity = {key: manifest[key] for key in ('forecast_sha256', 'model_source', 'gws', 'data_cutoff')}
        identity.update(ui_source=UI, archive_tag=tag, source_run=receipt['run_id'], live_window=is_live)
        (public / 'c2-archive-preview.json').write_text(json.dumps(identity, indent=2) + '\n')
        (tree / 'app/manager-service.json').write_text(
            json.dumps({'url': None, 'status': 'preview_worker_required'}) + '\n',
        )
        shutil.copytree(tree / 'app', out)
        print(json.dumps(identity))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True, help='Git checkout containing the pinned UI commit')
    parser.add_argument('--archive-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tag', help='Select an explicit reviewed archive instead of finding the current one')
    parser.add_argument('--capture', type=Path, help='Already downloaded original producer artifact')
    parser.add_argument('--allow-historical', action='store_true', help='Build an explicit old tag for browser regression')
    build(parser.parse_args())
