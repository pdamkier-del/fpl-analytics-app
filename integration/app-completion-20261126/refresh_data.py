"""Refresh existing public data from the same verified producer; never run a model.

Only original producer JSON/CSV/GZ payloads are copied. All UI/code/private state
remain outside the overlay. The full old Pages snapshot must already be archived.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import urllib.request

from reviewed_baseline import PREFIX, REVIEW, api, hashes, resolve, verify_site

REPO='pdamkier-del/fpl-analytics-app'
SOURCE='d7060b51cf16016f7947b2ffc110909afea89bb7'
WRAPPER='140e3f88c4a1110b3b4a06d8a90ae691dca9e984'
PREFIXES=('mm-preview/current/','mm-preview/gk/','mm-preview/news/')
ARCHIVE='fpl-public-data-before-transfer-refresh-8108442989'


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()


def digest(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_text())
def clock(value):return datetime.fromisoformat(value.replace('Z','+00:00'))


def source_run(run_id,get=api):
    if not str(run_id).isdigit():raise ValueError('Numeric original producer run required')
    run=get(f'repos/{REPO}/actions/runs/{run_id}')
    if (run.get('status')!='completed' or run.get('conclusion')!='success' or
        run.get('path')!='.github/workflows/mm-current-preview-publication.yml' or
        run.get('head_sha')!=WRAPPER or run.get('head_branch')!='integration/stable-live-app-20261122'):
        raise ValueError('Original pinned producer wrapper did not succeed')
    jobs=get(f'repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100')['jobs']
    if not any(j['name']=='gk_cap_candidate / current'and j['conclusion']=='success'for j in jobs):
        raise ValueError('Exact original numerical producer did not pass')
    artifacts=get(f'repos/{REPO}/actions/runs/{run_id}/artifacts')['artifacts']
    selected=[a for a in artifacts if a['name']=='mm-current-live-preview'and not a['expired']]
    if len(selected)!=1:raise ValueError('Original public capture unavailable')
    a=selected[0]
    return dict(run_id=int(run_id),numerical_source=SOURCE,artifact_id=a['id'],artifact_digest=a['digest'])


def archive(tar_digest,review,get=api):
    release=get(f'repos/{REPO}/releases/tags/{ARCHIVE}')
    assets={a['name']:a for a in release['assets']}
    original=assets.get('original-pages.tar',{})
    expected='sha256:'+tar_digest
    baseline=assets.get('baseline.json',{})
    if original.get('state')!='uploaded'or original.get('digest')!=expected or baseline.get('digest')!='sha256:'+digest(REVIEW) or release.get('target_commitish')!=review['deployment']['sha']:
        raise ValueError('Permanent original public snapshot has not been preserved')
    return dict(tag=ARCHIVE,release_id=release['id'],asset_id=original['id'],digest=expected)


def official():
    with urllib.request.urlopen(urllib.request.Request('https://fantasy.premierleague.com/api/bootstrap-static/',headers={'Cache-Control':'no-cache'}),timeout=45)as response:return json.load(response)


def check_window(f,news,bootstrap,now):
    at,deadline=clock(f['data_asof']),clock(f['origin_deadline'])
    if not at<=now<deadline or (now-at).total_seconds()>f['freshness_limit_hours']*3600:
        raise ValueError('Fresh original forecast required before deadline')
    event=next((e for e in bootstrap['events']if e.get('is_next')),None)
    if not event or event['id']!=f['gws'][0]or clock(event['deadline_time'])!=deadline:
        raise ValueError('Official next GW/deadline does not match')
    people={p['id']:p for p in bootstrap['elements']}
    if len(people)!=len(bootstrap['elements'])or set(people)!={p['id']for p in f['players']}:
        raise ValueError('Official player identities changed')
    for p in f['players']:
        q=people[p['id']]
        if (p['team_id'],p['position'],p['price_tenths'])!=(q['team'],q['element_type'],q['now_cost']):
            raise ValueError('Official prices, clubs or positions changed; new original capture required')
    news_people={p['id']:p for p in news['players']}
    if set(news_people)!=set(people)or any((p['team'],p['position'],p['price_tenths'])!=(people[i]['team'],people[i]['element_type'],people[i]['now_cost'])for i,p in news_people.items()):
        raise ValueError('Official status catalogue differs from current prices')
    body={k:v for k,v in news.items()if k!='content_sha256'}
    if hashlib.sha256(canonical(body)).hexdigest()!=news.get('content_sha256'):
        raise ValueError('Official status checksum mismatch')
    observed=clock(news['observed_at'])
    if (news.get('schema')!='fpl-dashboard-availability-v1'or news.get('source_url')!='https://fantasy.premierleague.com/api/bootstrap-static/'or
        news['next_gw']!=event['id']or clock(news['deadline'])!=deadline or not 0<=(now-observed).total_seconds()<=3600):
        raise ValueError('Fresh original official status required')


def validate_capture(capture,old,now,bootstrap):
    f=read(capture/'current/forecast.json');index=read(capture/'current/index.json');gk=read(capture/'gk/index.json')
    for key in ('model','chain_version','mm_version','model_revision','code_sha256','parts','normal_match_timeline','freshness_limit_hours','season'):
        if f.get(key)!=old.get(key):raise ValueError('Frozen model/configuration differs: '+key)
    if not f.get('code_sha256')or f.get('locked_model_active')is not False or f['gws']!=old['gws']or len(f['gws'])!=6:
        raise ValueError('Same frozen six-GW model required')
    if clock(f['data_asof'])<=clock(old['data_asof']):raise ValueError('Producer did not supply newer original data')
    identity=hashlib.sha256(canonical({k:v for k,v in f.items()if k!='forecast_sha256'})).hexdigest()
    if f.get('forecast_sha256')!=identity or index['forecast_sha256']!=identity:
        raise ValueError('Original forecast identity mismatch')
    checks={'forecast.json':'forecast_file_sha256','mm.json':'mm_file_sha256','existing-app-data.json':'existing_app_data_sha256','catalogue.json':'catalogue_sha256','chain-validation.json':'chain_validation_sha256','pm-audit.json':'pm_audit_sha256','role-ledger.csv.gz':'role_ledger_sha256'}
    for name,key in checks.items():
        if digest(capture/'current'/name)!=index[key]:raise ValueError('Original producer checksum mismatch: '+name)
    for name,key in [('forecast.json','forecast_sha256'),('gk-mm.json','mm_sha256'),('evidence.json','evidence_sha256')]:
        if digest(capture/'gk'/name)!=gk[key]:raise ValueError('Original probability checksum mismatch')
    if (capture/'current/forecast.json').read_bytes()!=(capture/'gk/forecast.json').read_bytes():raise ValueError('Planner/probability forecasts differ')
    documents=read(capture/'current/existing-app-data.json')
    if documents['forecast_sha256']!=identity or index.get('desktop_probabilities',{}).get('forecast_sha256')!=identity:
        raise ValueError('Existing app adapter inputs do not match forecast')
    check_window(f,read(capture/'news/availability.json'),bootstrap,now)
    return f


def data_path(name):
    p=PurePosixPath(name)
    return not p.is_absolute()and '..'not in p.parts and name.startswith(PREFIXES)and name.endswith(('.json','.json.gz','.csv','.csv.gz'))


def candidate_changes(review,candidate):
    original=review['files'];files=candidate['files']
    if not set(original)<=set(files):raise ValueError('Existing publication files must not be deleted')
    changed=[p for p,h in files.items()if original.get(p)!=h]
    if any(not p.startswith(PREFIX)and(not data_path(p)or '/history/'in p and p in original or p not in original and '/history/'not in p)for p in changed):
        raise ValueError('Only original public data and the isolated preview may change; production UI/history are frozen')
    return changed


def apply(site,capture,review,source,previous_tar_digest,now,bootstrap):
    verify_site(site,review,allow_preview=True)
    old=read(site/'mm-preview/current/forecast.json');f=validate_capture(capture,old,now,bootstrap)
    for folder in ('current','gk','news'):
        for path in (capture/folder).rglob('*'):
            if path.is_symlink():raise ValueError('Symlink in public capture')
            if not path.is_file():continue
            relative='mm-preview/'+path.relative_to(capture).as_posix()
            if not data_path(relative):continue  # Preserve every UI/JS/CSS byte.
            if relative not in review['files']and '/history/'not in relative:
                raise ValueError('Unreviewed new public data path: '+relative)
            target=site/relative
            if '/history/'in relative and target.exists()and digest(target)!=digest(path):raise ValueError('Immutable original history differs')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    candidate=deepcopy(review);candidate.pop('replaceable_preview_prefix',None);candidate['files']=hashes(site)
    changes=candidate_changes(review,candidate)
    candidate['data_refresh']=dict(schema='fpl-original-data-refresh-v1',baseline_digest=hashlib.sha256(canonical(review)).hexdigest(),source=source,previous_tar_digest=previous_tar_digest,previous_forecast_sha256=old['forecast_sha256'],forecast_sha256=f['forecast_sha256'],data_asof=f['data_asof'],changed_files=changes)
    return candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['apply','guard']);p.add_argument('--site',type=Path,required=True);p.add_argument('--capture',type=Path);p.add_argument('--source-run');p.add_argument('--previous-tar',type=Path);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args()
    review=read(REVIEW);resolve(review);now=datetime.now(timezone.utc)
    if a.action=='apply':
        result=apply(a.site,a.capture,review,source_run(a.source_run),digest(a.previous_tar),now,official());a.candidate.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    else:
        result=read(a.candidate);meta=result['data_refresh']
        if meta['baseline_digest']!=hashlib.sha256(canonical(review)).hexdigest():raise ValueError('Reviewed live baseline differs')
        if source_run(meta['source']['run_id'])!=meta['source']or not archive(meta['previous_tar_digest'],review):raise ValueError('Original source/archive provenance differs')
        candidate_changes(review,result);verify_site(a.site,result)
        f=read(a.site/'mm-preview/current/forecast.json');check_window(f,read(a.site/'mm-preview/news/availability.json'),official(),now)
    print(json.dumps(result['data_refresh'],sort_keys=True))


if __name__=='__main__':main()
