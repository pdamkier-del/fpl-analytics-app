"""Prospective cycle v2: identical scores/selection, bounded archive metadata I/O."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
from archive_link import candidate_issues,recover_verified
from archive_link_v2 import load_runtime
from evaluate import score
from labels import digest,fetch_final,normalize
from metrics import block_intervals
from store import get_record,put_record,canonical

STUDY='fpl-research-mm-pm-v1'


def instant(s):return datetime.fromisoformat(s.replace('Z','+00:00'))


def stored_before_lock(backend,window,protocol):
    """Final primary uses only reports actually retained by the fixed data lock."""
    selected={};page=1;lock=instant(window['data_lock_at'])
    while True:
        rows=backend.api(f'repos/{backend.repository}/releases?per_page=100&page={page}')
        for release in rows:
            tag=release.get('tag_name','')
            if not tag.startswith(STUDY+'-report-gw'):continue
            assets=release.get('assets',[])
            if len(assets)!=1 or instant(assets[0]['created_at'])>lock:continue
            doc=get_record(backend,tag)
            if not doc or doc['protocol_sha256']!=protocol:continue
            result=doc['result'];gw=result['gw']
            if not window['first_origin']<=gw<=window['last_origin']:continue
            if instant(doc['labels']['payload']['observed_at_utc'])>lock:continue
            pointer=get_record(backend,STUDY+f'-selection-gw{gw:02}')
            if pointer!=result['selection']:raise ValueError('Report not linked to original selection')
            item=(instant(assets[0]['created_at']),tag,result)
            if gw not in selected or item[:2]>selected[gw][:2]:selected[gw]=item
        if len(rows)<100:break
        page+=1
    return [selected[g][2]for g in sorted(selected)]


def cumulative(reports,window,locked):
    valid=[r for r in reports if r['status']=='complete'];fixtures=sum(r['coverage']['fixtures']for r in valid)
    by_gw={r['gw']:r for r in valid}
    calendar=list(range(window['first_origin'],window['last_origin']+1))
    def values(model,metric):return [by_gw[g]['summary'][model][metric]if g in by_gw else None for g in calendar]
    from evaluate import mean
    priorities=[]
    for component in sorted({x['component']for r in valid for x in r['priority']}):
        rows=[x for r in valid for x in r['priority']if x['component']==component]
        priorities.append(dict(component=component,mean_gw_point_bias=mean([x['bias']for x in rows]),
            mean_gw_mae=mean([x['mae']for x in rows]),fixture_rows=sum(x['n']for x in rows),observed_nonzero=sum(x['observed_nonzero']for x in rows)))
    priorities.sort(key=lambda x:(-abs(x['mean_gw_point_bias']),-x['mean_gw_mae'],x['component']))
    return dict(complete_gws=len(valid),distinct_fixture_gw_pairs=fixtures,
        absolute_scores=dict(start_log_loss=mean(values('mm','start_log_loss')),point_crps=mean(values('pm','crps'))),
        component_priority=priorities,
        mm_start_comparison=block_intervals(values('mm','start_log_loss_delta'),fixtures,locked=locked),
        pm_point_comparison=block_intervals(values('pm','ep_mse_delta'),fixtures,locked=locked),
        interpretation='Interim descriptive only until fixed lock and minimum gates; no model acceptance')


def evaluate_selected(runtime,backend,selection,work,*,fetcher=fetch_final,now=None):
    folder,manifest,proof,docs=recover_verified(runtime,backend,selection['tag'],work/'originals')
    if manifest['revision_id']!=selection['revision_id']:raise ValueError('Selection identity changed')
    f=docs['forecast.json'];labels=fetcher(f)
    if labels['status']!='final':
        return dict(gw=selection['gw'],status='awaiting_results',scored_rows=0),None
    if instant(labels['payload']['observed_at_utc'])>(now or datetime.now(timezone.utc)):
        raise ValueError('Future label observation is ineligible')
    histories={(r['id'],r['fixture']):r['stats']for r in labels['history']}
    normalized=normalize(f,docs['official-bootstrap.json'],docs['official-fixtures.json'],
                         labels['payload'],labels['identities'],histories)
    result=score(f,docs['mm.json'],docs['official-bootstrap.json'],docs['official-fixtures.json'],normalized)
    # Semantic revisions exclude retrieval clocks and transient provider flags.
    semantic=dict(season=f['season'],gw=selection['gw'],event=labels['payload']['official_event'],
        fixtures=labels['payload']['official_fixtures'],rows=normalized,
        identities=sorted([r for r in labels['identities']if r['id']in{p['id']for p in f['players']}],key=lambda r:r['id']))
    label_hash=digest(semantic)
    result['label_revision_sha256']=label_hash
    result['selection']=selection;result['publication']=proof
    return result,labels


def cycle(runtime,backend,work,target,*,now=None,publish=False,fetcher=fetch_final):
    now=now or datetime.now(timezone.utc)
    boundary=json.loads((HERE/'registration-boundary.json').read_text())
    registered=instant(boundary['registered_at'])
    state=dict(schema='fpl-prospective-mm-pm-status/v1',observed_at=now.isoformat(),
        status='awaiting_eligible_original',rows=[],scores_prospective=0,
        protocol_sha256=hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),
        registration_at=boundary['registered_at'],model_changed=False,private_data_used=False)
    window_tag=STUDY+'-window';window=get_record(backend,window_tag)
    if window is not None and (window['protocol_sha256']!=state['protocol_sha256']or window['registration_sha256']!=boundary['event_sha256']):
        raise ValueError('Study window/protocol mismatch')
    final=get_record(backend,STUDY+'-final-primary')
    if final is not None:
        if final['window']!=window:raise ValueError('Final record belongs to another study window')
        state.update(status='final_primary_already_locked',final_primary=final);return state
    if window is not None and now>=instant(window['data_lock_at']):
        reports=stored_before_lock(backend,window,state['protocol_sha256'])
        rollup=cumulative(reports,window,True)
        status='final_complete'if rollup['complete_gws']>=12 and rollup['distinct_fixture_gw_pairs']>=120 else'final_inconclusive'
        record=dict(status=status,window=window,cumulative=rollup,source_revisions=[dict(gw=r['gw'],forecast_sha256=r['forecast_sha256'],label_revision_sha256=r['label_revision_sha256'])for r in reports])
        if publish:put_record(backend,STUDY+'-final-primary',record,target)
        state.update(record);return state
    candidates=candidate_issues(runtime,backend,registered,now)
    state['eligible_issue_candidates']=len(candidates)
    ready=[r for r in candidates if r['selection_ready']]
    state['candidate_origins']=sorted({r['gw']for r in candidates})
    if not ready:
        if candidates:state['status']='awaiting_selection_cutoff'
        return state
    if window is None:
        first=min(r['gw']for r in ready);last=min(38,first+15)
        chosen=next(r for r in reversed(ready)if r['gw']==first)
        _,_,_,docs=recover_verified(runtime,backend,chosen['tag'],work/'window-proof')
        events={e['id']:e for e in docs['official-bootstrap.json']['events']}
        window=dict(first_origin=first,last_origin=last,registration_sha256=boundary['event_sha256'],
            protocol_sha256=state['protocol_sha256'],data_lock_at=(instant(events[last]['deadline_time'])+timedelta(days=30)).isoformat(),
            calendar_basis='Original first selected issue bootstrap; never shifted by later outcomes')
        if publish:put_record(backend,window_tag,window,target)
    if window['protocol_sha256']!=state['protocol_sha256']or window['registration_sha256']!=boundary['event_sha256']:
        raise ValueError('Study window/protocol mismatch')
    state['window']=window;reports=[]
    for gw in range(window['first_origin'],window['last_origin']+1):
        selection_tag=STUDY+f'-selection-gw{gw:02}'
        selection=get_record(backend,selection_tag)
        if selection is None:
            issues=[r for r in ready if r['gw']==gw]
            if not issues:
                state['rows'].append(dict(gw=gw,status='awaiting_eligible_original_or_cutoff'));continue
            selection=issues[-1]
            recover_verified(runtime,backend,selection['tag'],work/f'pre-label-selection-{gw}')
            if publish:put_record(backend,selection_tag,selection,target)
        # Selection pointer is immutable before any outcome request.
        try:
            result,raw=evaluate_selected(runtime,backend,selection,work/f'gw{gw}',fetcher=fetcher,now=now)
        except Exception:
            state['rows'].append(dict(gw=gw,status='blocked_origin',reason_code='original_or_final_label_contract_rejected'))
            continue
        if result['status']=='awaiting_results':
            state['rows'].append(result);continue
        report=dict(experiment_ids=['EXP-MM-LIVE-001','EXP-PM-LIVE-001'],protocol_sha256=state['protocol_sha256'],
            implementation_sha256=hashlib.sha256((HERE/'implementation-manifest.v2.json').read_bytes()).hexdigest(),result=result,labels=raw)
        # Retrieval time is provenance, not a reason to publish an identical new score.
        semantic_key=digest(dict(protocol=state['protocol_sha256'],selection=selection,
            labels=result['label_revision_sha256'],implementation=report['implementation_sha256']))
        tag=STUDY+f'-report-gw{gw:02}-'+semantic_key
        old=get_record(backend,tag)
        if publish and old is None:put_record(backend,tag,report,target)
        if old is not None:report=old;result=old['result']
        reports.append(result)
        state['rows'].append(dict(gw=gw,status=result['status'],forecast_sha256=result['forecast_sha256'],
            label_revision_sha256=result['label_revision_sha256'],report_tag=tag,coverage=result['coverage']))
    state['status']='collecting_future_results';state['scores_prospective']=len(reports)
    if any(r['status']in ['blocked_origin','partial_data']for r in state['rows']):state['status']='blocked_or_partial_labels'
    state['cumulative']=cumulative(reports,window,False)
    return state


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--archive-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--repository',default='pdamkier-del/fpl-analytics-app');p.add_argument('--target',default=None)
    p.add_argument('--publish',action='store_true');p.add_argument('--verify-example')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.repository!='pdamkier-del/fpl-analytics-app':raise ValueError('Study repository is fixed')
    if any(a.out.iterdir()):raise ValueError('Use a fresh run directory')
    manifest=json.loads((HERE/'implementation-manifest.v2.json').read_text())
    for name,h in manifest['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise ValueError('Registered evaluation code changed')
    sys.path.insert(0,str(ROOT/'research/tools'));import registry
    for identifier in ['EXP-MM-LIVE-001','EXP-PM-LIVE-001','EXP-OPS-EVAL-001']:
        record=registry.read()[identifier];implementation=record['implementation']
        if implementation is None or implementation['harness_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise ValueError('Evaluation harness must be registered before execution')
        if record['state']not in ['running','awaiting_data']:raise ValueError('Study is not in a collection state')
    runtime=load_runtime(a.archive_root);backend=runtime[0].Github(a.repository)
    target=a.target or os.environ.get('GITHUB_SHA')or __import__('subprocess').check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    try:
        result=cycle(runtime,backend,a.out,target,publish=a.publish)
        if a.verify_example:
            _,m,proof,docs=recover_verified(runtime,backend,a.verify_example,a.out/'infrastructure-example')
            result['archive_link_check']=dict(status='verified',revision_id=m['revision_id'],forecast_sha256=m['forecast_sha256'],
                gws=m['gws'],official_deadline=m['official_deadline'],scenarios=docs['forecast.json']['scenario_contract'],
                evidence_class='infrastructure_only_no_outcomes',scored_rows=0,
                eligible_for_this_registration=instant(m['data_cutoff'])>instant(result['registration_at']))
    except Exception as error:
        result=dict(status='blocked',reason_code='archive_identity_selection_or_label_contract_failed',
                    error_type=type(error).__name__,scores_prospective=None,
                    partial_run_status='Unknown; inspect immutable research records, never assume zero')
    (a.out/'status.json').write_bytes(canonical(result))
    summary=f"# Frozen MM/PM prospective evaluation\n\nStatus: {result['status']}\n\nCompleted scored future origins: {result.get('scores_prospective',0)}\n\nNo model changes or private state. Read status.json for coverage and pending gates.\n"
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a')as handle:handle.write(summary)
    if result['status'].startswith('blocked'):return 1
    return 0


if __name__=='__main__':sys.exit(main())
