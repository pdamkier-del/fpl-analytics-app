"""Fail closed against a reviewed deployment, artifact and complete file inventory.

A commit alone is insufficient: scheduled news publications reuse the same SHA.
Only public Pages files/metadata belong in the review record.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / 'baseline-preview-update-20261127.json'
PREFIX = 'previews/team-transfers-20261126/'


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path]))


def resolve(review, get=api):
    repo = review['repository']
    # GitHub orders deployments newest first; skip pending/failed publications.
    deployments = get(f'repos/{repo}/deployments?environment=github-pages&per_page=100')
    chosen = None
    for deployment in deployments:
        statuses = get(f'repos/{repo}/deployments/{deployment["id"]}/statuses')
        success = next((s for s in statuses if s['state'] == 'success'), None)
        if success:
            chosen = deployment, success
            break
    if chosen is None:
        raise ValueError('No successful live Pages deployment can be verified')
    deployment, status = chosen
    expected = review['deployment']
    if deployment['id'] != expected['id'] or deployment['sha'] != expected['sha']:
        raise ValueError('Live production advanced; review deployment and artifact content before preview publication')
    match = re.fullmatch(r'https://github.com/' + re.escape(repo) + r'/actions/runs/(\d+)/job/(\d+)', status['log_url'])
    if not match or int(match[1]) != expected['run_id'] or int(match[2]) != expected['job_id']:
        raise ValueError('Unexpected live deployment workflow provenance')
    run = get(f'repos/{repo}/actions/runs/{expected["run_id"]}')
    if run['head_sha'] != expected['sha'] or run['conclusion'] != 'success' or run['path'] != expected['workflow']:
        raise ValueError('Reviewed production workflow identity does not match')
    artifacts = get(f'repos/{repo}/actions/runs/{expected["run_id"]}/artifacts')['artifacts']
    matches = [a for a in artifacts if a['id'] == review['artifact']['id']]
    if len(matches) != 1:
        raise ValueError('Reviewed Pages artifact is missing')
    artifact = matches[0]
    for field in ('name', 'digest', 'size_in_bytes'):
        if artifact[field] != review['artifact'][field]:
            raise ValueError('Reviewed Pages artifact identity changed: ' + field)
    if artifact['expired']:
        raise ValueError('Reviewed Pages artifact expired; do not reconstruct production')
    return dict(run=expected['run_id'], artifact=artifact['name'], deployment=deployment['id'])


def hashes(site):
    result = {}
    for path in site.rglob('*'):
        if path.is_symlink():
            raise ValueError('Unexpected symlink in Pages site')
        if path.is_file():
            with path.open('rb') as stream:
                result[path.relative_to(site).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return result


def verify_site(site, review, allow_preview=False):
    expected = review['files']
    replacement = review.get('replaceable_preview_prefix')
    if replacement is not None and replacement != PREFIX:
        raise ValueError('Only the existing isolated preview may be replaced')
    for name in expected:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid reviewed file path')
    # The entire current artifact is verified before build. Only its own reviewed
    # preview subtree may differ after build; production files remain immutable.
    if allow_preview and replacement:
        expected = {name: digest for name, digest in expected.items() if not name.startswith(replacement)}
    actual = hashes(site)
    changed = [name for name, digest in expected.items() if actual.get(name) != digest]
    extra = [name for name in actual.keys() - expected.keys()
             if not (allow_preview and name.startswith(PREFIX))]
    if changed or extra:
        raise ValueError(f'Reviewed production content differs: {len(changed)} changed/missing, {len(extra)} unexpected; examples: {(changed + extra)[:4]}')
    return dict(original_files_unchanged=len(expected), reviewed_deployment=review['deployment']['id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['resolve', 'guard'])
    parser.add_argument('--review', type=Path, default=REVIEW)
    parser.add_argument('--site', type=Path)
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    review = json.loads(args.review.read_text())
    result = resolve(review)
    if args.action == 'guard':
        if args.site is None:
            parser.error('guard requires --site')
        result.update(verify_site(args.site, review, allow_preview=True))
    if args.github_output:
        with args.github_output.open('a') as output:
            for key in ('run', 'artifact'):
                output.write(f'{key}={result[key]}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
