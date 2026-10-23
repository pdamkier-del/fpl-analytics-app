"""Reuse a completed, successful pinned numerical job; rerun all UI gates."""
import argparse
import base64
import json
import re
import subprocess

REPO = 'pdamkier-del/fpl-analytics-app'
MODEL_WORKFLOW = '.github/workflows/mm-current-live-preview.yml'
WRAPPER_WORKFLOW = '.github/workflows/mm-current-preview-publication.yml'
REUSABLE = REPO + '/' + MODEL_WORKFLOW + '@0c622eeb2b3da5c085660bc95e22cf2fd5447593'


def verify(run, artifacts, source, *, workflow='', jobs=()):
    if not re.fullmatch('[a-f0-9]{40}', source):
        raise ValueError('Invalid numerical source')
    if run.get('status') != 'completed':
        raise ValueError('Only completed artifact runs can be reused')
    if run.get('head_repository', {}).get('full_name') != REPO:
        raise ValueError('Foreign numerical artifact')
    if run.get('path') == MODEL_WORKFLOW:
        if run.get('head_sha') != source or run.get('conclusion') != 'success':
            raise ValueError('Wrong standalone numerical source')
    elif run.get('path') == WRAPPER_WORKFLOW:
        # A later UI job may fail or be cancelled without invalidating its
        # completed numerical predecessor. The new publisher reruns every UI,
        # official-news alignment and production-integrity gate.
        if run.get('conclusion') not in {'success', 'failure', 'cancelled'}:
            raise ValueError('Unverified wrapper completion')
        if run.get('head_branch') != 'main' or run.get('event') not in {'schedule', 'workflow_dispatch'}:
            raise ValueError('Wrapper must run from the reviewed main workflow')
        if re.findall(r'^  PREVIEW_SOURCE_SHA: ([a-f0-9]{40})\s*$', workflow, re.M) != [source]:
            raise ValueError('Immutable wrapper pins another numerical source')
        if re.findall(r'^      source_ref: ([a-f0-9]{40})\s*$', workflow, re.M) != [source]:
            raise ValueError('Numerical checkout differs from the declared pin')
        # Retain the reviewed legacy workflow for its old source. New sources
        # must use the workflow committed at that exact same immutable source;
        # an old workflow could silently omit a new opt-in numerical stage.
        expected=REUSABLE if source=='f492be4795bfd630ba91377d71497e68c1d85934' else REPO+'/'+MODEL_WORKFLOW+'@'+source
        if re.findall(r'^    uses: (.+mm-current-live-preview\.yml@[^\s]+)\s*$', workflow, re.M) != [expected]:
            raise ValueError('Unreviewed numerical workflow')
        if not any(j.get('name') == 'current / current' and j.get('status') == 'completed' and j.get('conclusion') == 'success' for j in jobs):
            raise ValueError('Wrapper did not complete the numerical computation')
    else:
        raise ValueError('Unapproved artifact workflow')
    matches = [a for a in artifacts if a.get('name') == 'mm-current-live-preview' and not a.get('expired')]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous numerical artifact')
    return matches[0]['id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    if not args.run.isdigit():
        raise ValueError('Invalid artifact run')
    def get(path):
        return json.loads(subprocess.check_output(['gh', 'api', 'repos/' + REPO + '/' + path]))
    run = get('actions/runs/' + args.run)
    artifacts = get('actions/runs/' + args.run + '/artifacts')['artifacts']
    workflow, jobs = '', []
    if run.get('path') == WRAPPER_WORKFLOW:
        commit = run['head_sha']
        if not re.fullmatch('[a-f0-9]{40}', commit):
            raise ValueError('Invalid immutable workflow commit')
        workflow = base64.b64decode(get('contents/' + WRAPPER_WORKFLOW + '?ref=' + commit)['content']).decode()
        jobs = get('actions/runs/' + args.run + '/jobs?per_page=100')['jobs']
    artifact = verify(run, artifacts, args.source, workflow=workflow, jobs=jobs)
    print(json.dumps(dict(run=int(args.run), artifact=artifact, numerical_source=args.source,
                          immutable_source_verified=True)))


if __name__ == '__main__':
    main()
