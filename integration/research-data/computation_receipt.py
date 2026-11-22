"""Read the existing successful producer job's GitHub clock; never backdate it."""
import argparse
import base64
import json
import re
import subprocess
from archive import PIN, canonical, require


def collect(repository, run):
    require(run.isdigit(), 'Numeric run required')
    def api(path):
        r=subprocess.run(['gh','api',f'repos/{repository}/'+path],capture_output=True)
        require(r.returncode==0,'Cannot verify original computation metadata')
        return json.loads(r.stdout)
    doc=api(f'actions/runs/{run}')
    require(doc.get('head_repository',{}).get('full_name')==repository, 'Foreign computation source')
    direct='.github/workflows/mm-current-live-preview.yml'
    wrapper='.github/workflows/mm-current-preview-publication.yml'
    if doc.get('path')==direct:
        require(doc.get('head_sha')==PIN and doc.get('conclusion')=='success', 'Standalone producer source mismatch')
        expected_name='current'
    else:
        require(doc.get('path')==wrapper, 'Unapproved computation workflow')
        raw=api('contents/'+wrapper+'?ref='+doc['head_sha'])
        workflow=base64.b64decode(raw['content']).decode()
        # Same exact-source checks as the existing verify_b_publication_artifact.py;
        # this sibling archive can run while the wrapper's UI job is still running.
        require(re.findall(r'^  PREVIEW_SOURCE_SHA: ([a-f0-9]{40})\s*$',workflow,re.M)==[PIN], 'Wrapper source mismatch')
        require(re.findall(r'^      source_ref: ([a-f0-9]{40})\s*$',workflow,re.M)==[PIN], 'Numerical checkout mismatch')
        expected=repository+'/'+direct+'@'+PIN
        require(re.findall(r'^    uses: (.+mm-current-live-preview\.yml@[^\s]+)\s*$',workflow,re.M)==[expected], 'Reusable workflow mismatch')
        expected_name='current / current'
    jobs=[];page=1
    while True:
        part=api(f'actions/runs/{run}/jobs?per_page=100&page={page}')['jobs'];jobs+=part
        if len(part)<100:break
        page+=1
    selected=[j for j in jobs if j['name']==expected_name and j['conclusion']=='success' and j['status']=='completed']
    require(len(selected)==1, 'A unique successful original B producer is required')
    job=selected[0]
    return dict(schema='fpl-computation-witness/v1',repository=repository,run_id=int(run),
                run_head_sha=doc['head_sha'],workflow_path=doc['path'],producer_job_id=job['id'],
                producer_job_name=job['name'],producer_started_at=job['started_at'],
                producer_completed_at=job['completed_at'],numerical_source=PIN,
                clock_basis='GitHub producer-job completion; upper bound, not exact model finish timestamp')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--repository',required=True);p.add_argument('--run',required=True)
    a=p.parse_args();print(canonical(collect(a.repository,a.run)).decode())
