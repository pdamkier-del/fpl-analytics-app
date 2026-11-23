"""Public-only consumer of existing original producer artifacts. No model calls."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

from archive import PIN, bundle, canonical, clock, require, sha
from computation_receipt import collect
from releases import Github, persist, recover

PRODUCER = 'mm-current-preview-publication.yml'
PATH = '.github/workflows/'+PRODUCER
TAG = re.compile(r'fpl-forecast-(\d{4}-\d{2})-gw(\d{2})-([a-f0-9]{64})')


class CaptureRejected(Exception):
    def __init__(self,code):self.code=code


def pages(backend, path, key=None):
    number=1
    while True:
        data=backend.api(path+('&'if '?'in path else'?')+f'per_page=100&page={number}')
        rows=data[key] if key else data
        yield from rows
        if len(rows)<100:
            return
        number+=1


def inventory(backend, now, *, full_run_lookup=False):
    """Check original receipts against provider IDs/digests. No private datasets."""
    runs=set();coverage={};errors=[];count=0
    for release in pages(backend,f'repos/{backend.repository}/releases'):
        match=TAG.fullmatch(release.get('tag_name',''))
        if not match:
            continue
        count+=1
        key=(match[1],int(match[2]))
        # Do not reread every historical revision every hour. Validate all recent
        # receipts and at least one complete representative per historical GW.
        # C1 still verifies every chosen revision on independent full recovery.
        if not full_run_lookup and key in coverage and clock(release['published_at'])<now-timedelta(hours=26):
            continue
        try:
            assets={a['name']:a for a in release['assets']}
            require(len(assets)==len(release['assets']), 'Duplicate assets')
            raw=backend.content(assets['manifest.json']);manifest=json.loads(raw)
            proof=json.loads(backend.content(assets['publication.json']))
            ids={k:manifest[k]for k in ['season','origin_gw','gws','forecast_sha256','model_source','files']}
            require(sha(canonical(ids))==match[3]==manifest['revision_id'], 'Revision mismatch')
            require(manifest['model_source']==PIN and manifest['season']==match[1] and manifest['origin_gw']==int(match[2]), 'Unreviewed source/identity')
            require(proof['release_id']==release['id'] and proof['tag']==release['tag_name'] and proof['revision_id']==match[3] and proof['forecast_sha256']==manifest['forecast_sha256'], 'Receipt mismatch')
            expected={'manifest.json':sha(raw),**manifest['files']}
            require(set(assets)=={*expected,'publication.json'} and set(proof['assets'])==set(expected), 'Incomplete/extra archive assets')
            for name,h in expected.items():
                asset=assets[name];receipt=proof['assets'][name]
                require(asset['state']=='uploaded' and asset['id']==receipt['id'] and receipt['sha256']==h, 'Asset identity changed')
                require(asset['created_at']==receipt['created_at'], 'Asset clock changed')
                provider=asset.get('digest')
                require((provider=='sha256:'+h) if provider else sha(backend.content(asset))==h, 'Asset digest changed')
                require(clock(manifest['data_cutoff'])<=clock(asset['created_at'])<clock(manifest['official_deadline']), 'Late original archive')
            published=max(clock(release['published_at']),*(clock(assets[n]['created_at'])for n in expected))
            require(clock(proof['publication_at'])==published<clock(manifest['official_deadline']), 'Publication clock mismatch')
            require(clock(assets['publication.json']['created_at'])<clock(manifest['official_deadline']), 'Completion receipt late')
            computation=json.loads(backend.content(assets['computation-receipt.json']))
            require(computation['repository']==backend.repository and computation['numerical_source']==PIN, 'Foreign producer receipt')
            runs.add(computation['run_id'])
            key=(manifest['season'],manifest['origin_gw'])
            if key not in coverage or clock(coverage[key]['data_cutoff'])<clock(manifest['data_cutoff']):
                coverage[key]={k:manifest[k]for k in ['season','origin_gw','revision_id','forecast_sha256','gws','official_deadline','data_cutoff']}
                coverage[key]['publication_at']=proof['publication_at']
        except Exception:
            # Do not echo downloaded documents, paths, signed redirects or values.
            errors.append({'release_id':release['id'],'reason_code':'invalid_public_archive_receipt'})
    return runs,coverage,errors,count


def candidates(backend, now, source_run=None):
    if source_run:
        require(str(source_run).isdigit(), 'Numeric source run required')
        rows=[backend.api(f'repos/{backend.repository}/actions/runs/{source_run}')]
    else:
        since=(now-timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
        rows=list(pages(backend,f'repos/{backend.repository}/actions/workflows/{PRODUCER}/runs?branch=main&status=completed&created=%3E%3D{since}', 'workflow_runs'))
    out=[]
    for row in rows:
        require(row.get('head_repository',{}).get('full_name')==backend.repository and row.get('head_branch')=='main' and row.get('path')==PATH, 'Foreign/unreviewed producer run')
        if row['status']=='completed':
            out.append(row)
    return sorted(out,key=lambda r:(r['created_at'],r['id']))


def download(repository, identifier, name, destination):
    """GitHub's existing artifact transport; never execute artifact contents."""
    reply=subprocess.run(['gh','run','download',str(identifier),'--repo',repository,
                          '--name',name,'--dir',str(destination)],capture_output=True,timeout=180)
    if reply.returncode:
        raise RuntimeError('Original artifact download unavailable')


def archive_one(backend, row, destination, target, *, now=None, collector=collect, transport=download):
    now=now or datetime.now(timezone.utc)
    jobs=list(pages(backend,f'repos/{backend.repository}/actions/runs/{row["id"]}/jobs','jobs'))
    producer=[j for j in jobs if j['name']=='current / current']
    if not producer or producer[0]['conclusion']=='skipped':
        return dict(source_run=row['id'],status='not_a_new_numerical_run')
    if len(producer)!=1 or producer[0]['status']!='completed' or producer[0]['conclusion']!='success':
        return dict(source_run=row['id'],status='producer_failed',reason_code='no_successful_original_computation')
    try:witness=collector(backend.repository,str(row['id']))
    except Exception:raise CaptureRejected('producer_source_identity_unverified')from None
    artifacts=list(pages(backend,f'repos/{backend.repository}/actions/runs/{row["id"]}/artifacts','artifacts'))
    for name in ['mm-current-live-preview','current-B-origin-input-evidence']:
        selected=[a for a in artifacts if a['name']==name and not a.get('expired')]
        if len(selected)!=1:raise CaptureRejected('original_artifact_missing_expired_or_ambiguous')
    with tempfile.TemporaryDirectory(dir=destination) as temp:
        work=Path(temp)
        try:
            transport(backend.repository,row['id'],'mm-current-live-preview',work/'capture')
            transport(backend.repository,row['id'],'current-B-origin-input-evidence',work/'origin')
        except Exception:raise CaptureRejected('original_artifact_download_unavailable')from None
        current=work/'capture/current';source=work/'origin/work/current-B-inputs'
        f=json.loads((current/'forecast.json').read_bytes())
        if now>=clock(f['origin_deadline']):
            return dict(source_run=row['id'],status='late_rejected',reason_code='origin_deadline_passed')
        config=json.loads((Path(__file__).parent/'frozen-ts-config.json').read_text())
        try:folder=bundle(current,work/'bundles',config,sources=source,computation=witness,now=now)
        except Exception:raise CaptureRejected('public_forecast_contract_rejected')from None
        try:
            proof=persist(folder,backend,target,now=now)
            # Independent directory; no CI artifact is used by recovery.
            recovered,again=recover(proof['tag'],work/'release-only-recovery',backend)
            require(proof==again, 'Independent publication recovery differs')
        except Exception:raise CaptureRejected('permanent_write_or_recovery_failed')from None
        return dict(source_run=row['id'],status='archived_and_recovered',tag=proof['tag'],
                    forecast_sha256=proof['forecast_sha256'],revision_id=proof['revision_id'],
                    publication_at=proof['publication_at'])


def coverage_status(coverage, bootstrap, now, monitor_from):
    events=bootstrap.get('events',[])
    require(events and len({e['id']for e in events})==len(events), 'Official deadline calendar unavailable')
    future=sorted((e for e in events if clock(e['deadline_time'])>now),key=lambda e:clock(e['deadline_time']))
    # Derive season from official deadline calendar, not from an existing release.
    first=min(clock(e['deadline_time'])for e in events)
    season=f'{first.year}-{str(first.year+1)[-2:]}'
    next_gw=future[0]['id']if future else None
    due=[e['id']for e in events if monitor_from<=clock(e['deadline_time'])<=now]
    def eligible(g):
        item=coverage.get((season,g));event=next(e for e in events if e['id']==g)
        return bool(item and clock(item['publication_at'])<clock(event['deadline_time']))
    missing=[g for g in due if not eligible(g)]
    missing_next=next_gw is not None and not eligible(next_gw)
    return dict(season=season,next_origin_gw=next_gw,
                next_official_deadline=future[0]['deadline_time']if future else None,
                next_origin_archived=not missing_next,missing_completed_origins=missing,
                monitoring_from=monitor_from.isoformat(),
                status='missing_forecast'if missing or missing_next else'covered')


def execute(backend, destination, target, *, source_run=None, now=None,
            bootstrap=None, monitor_from=None, archiver=archive_one):
    now=now or datetime.now(timezone.utc)
    monitor_from=monitor_from or datetime(2026,11,23,tzinfo=timezone.utc)
    destination.mkdir(parents=True,exist_ok=True)
    report=dict(schema='fpl-automatic-public-archive-status/v1',observed_at=now.isoformat(),
                repository=backend.repository,source_run=source_run,rows=[],failures=[],
                status='running',
                model_recomputed=False,app_deployed=False,private_data_used=False)
    def checkpoint():
        path=destination/'status.json.tmp'
        path.write_bytes(canonical(report));path.replace(destination/'status.json')
    checkpoint()
    try:
        selected=candidates(backend,now,source_run)
        full_lookup=bool(source_run and any(clock(r['created_at'])<now-timedelta(hours=26)for r in selected))
        archived,coverage,errors,count=inventory(backend,now,full_run_lookup=full_lookup)
        report['inventory_release_count']=count;report['initial_inventory_errors']=errors
        for row in selected:
            report['current_source_run']=row['id'];checkpoint()
            print(f'Inspecting original producer {row["id"]}',flush=True)
            if row['id']in archived:
                report['rows'].append(dict(source_run=row['id'],status='already_archived_no_write'))
                checkpoint()
                continue
            try:
                result=archiver(backend,row,destination,target,now=now)
            except CaptureRejected as error:
                result=dict(source_run=row['id'],status='archive_failed',reason_code=error.code)
            except Exception:
                result=dict(source_run=row['id'],status='archive_failed',reason_code='original_capture_or_transport_rejected')
            report['rows'].append(result)
            checkpoint()
            print(f'Producer {row["id"]}: {result["status"]}',flush=True)
        _,coverage,errors,_=inventory(backend,now,full_run_lookup=full_lookup)
        report['failures']+=errors
        report['verified_origins']=list(coverage.values())
        if bootstrap is None:
            with urllib.request.urlopen('https://fantasy.premierleague.com/api/bootstrap-static/',timeout=30)as response:
                bootstrap=json.load(response)
        report['coverage']=coverage_status(coverage,bootstrap,now,monitor_from)
        bad=any(r['status']in ['archive_failed','producer_failed']for r in report['rows'])
        report['status']='failed'if report['failures']or bad or report['coverage']['status']!='covered'else'complete'
    except Exception:
        report['status']='failed'
        report['failures'].append({'reason_code':'discovery_or_official_coverage_unavailable'})
    report.pop('current_source_run',None);checkpoint()
    return report


def summary(report):
    coverage=report.get('coverage',{})
    lines=['# Automatic public FPL archive', '',f'Overall: **{report["status"]}**',
           f'Next official origin: {coverage.get("next_origin_gw","UNKNOWN")}',
           f'Next-origin archive verified: {coverage.get("next_origin_archived",False)}',
           f'Missing completed origins: {coverage.get("missing_completed_origins","UNKNOWN")}',
           '', '| Producer run | Result | Reason code |', '| --- | --- | --- |']
    lines += [f'| {r["source_run"]} | {r["status"]} | {r.get("reason_code", "")} |'for r in report['rows']]
    lines += ['', 'No model computation, app deployment or private capture is performed.',
              f'Initial invalid/incomplete receipts observed: {len(report.get("initial_inventory_errors", []))}; final unresolved: {len(report["failures"])}.',
              'See status.json and the original checksummed release/publication receipts.']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--repository',required=True);p.add_argument('--target',required=True)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--source-run')
    args=p.parse_args()
    report=execute(Github(args.repository),args.out,args.target,source_run=args.source_run)
    text=summary(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a')as handle:handle.write(text)
    print(text)
    if report['status']!='complete':
        print('::error::Public forecast archive incomplete: see coverage, source-run status and status.json')
        raise SystemExit(1)
