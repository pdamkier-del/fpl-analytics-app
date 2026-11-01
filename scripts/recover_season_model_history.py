"""Recover original published forecasts without recalculating historical predictions.

The older diagnostic PM and B are separate series. No p60/p90 is inferred from
means, and PM simulator minutes are kept distinct from analytic MM minutes.
"""
import hashlib,json,math,subprocess
from datetime import datetime
from pathlib import Path

PATH='app/vfinal-diagnostic.json'
def clock(value):return datetime.fromisoformat(value.replace('Z','+00:00'))
def git(*args):return subprocess.check_output(['git',*args])

def recover(ref,season,now):
    selected={};late=0;seen=0
    commits=git('log',ref,'--format=%H %cI','--',PATH).decode().splitlines()
    for line in commits:
        commit,published=line.split(' ',1)
        # A chosen newer publication supersedes every older publication from
        # the same origin window; do not reread megabytes of identical horizons.
        if any(clock(published)>=clock(x['data_asof']) and clock(published)<clock(x['origin_deadline']) for x in selected.values()):continue
        raw=git('show',commit+':'+PATH);doc=json.loads(raw);seen+=1
        if doc.get('season')!=season or doc.get('model')!='original_locked_vFinal_diagnostic':continue
        if not doc.get('gws')or not doc.get('origin_deadline'):continue
        gw=min(doc['gws'])
        if not clock(doc['data_asof'])<=clock(published)<clock(doc['origin_deadline']) or clock(published)>clock(now):late+=1;continue
        if gw not in selected or clock(published)>clock(selected[gw]['published_at']):
            selected[gw]=dict(doc,published_at=published,publication_commit=commit,archive_sha256=hashlib.sha256(raw).hexdigest())
    return selected,dict(path=PATH,commits_examined=len(commits),documents_read=seen,late_documents=late,selection='Latest immutable original-model publication before each origin deadline; first GW only.')

def mean(rows,key):return sum(r[key]for r in rows)/len(rows)if rows else None

def evaluate(selected,history,catalogue,fixtures,current):
    """Match stable B identity + original fixture/team/kickoff to official labels."""
    official={p['id']:p for p in catalogue['players']};identities={p['id']:p['player_uuid']for p in current['players']}
    if len({(r['player_id'],r['fixture_id'])for r in history['match_rows']})!=len(history['match_rows']):raise ValueError('Duplicate historical actual fixture')
    fx={f['id']:f for f in fixtures['fixtures']};matches={(r['player_id'],r['fixture_id']):r for r in history['match_rows']};gws={(r['player_id'],r['gw']):r for r in history['gw_rows']}
    weeks=[];players={};labels=[]
    for gw,doc in sorted(selected.items()):
        errors=[];pending=0;excluded=0;seen=set()
        for person in doc['players']:
            pid=person['id'];known=official.get(pid)
            if not known or known.get('code')is None or identities.get(pid)!=person['player_uuid']:excluded+=1;continue
            forecast=next((w for w in person['weeks']if w['gw']==gw),None)
            if not forecast:continue
            rows=[]
            for p in forecast['fixtures']:
                key=(pid,p['fixture_uuid'])
                if key in seen:raise ValueError('Duplicate historical player fixture')
                seen.add(key)
                fid=int(p['fixture_uuid'].rsplit('-',1)[1]);f=fx.get(fid)
                if not f or f['gw']!=gw or person['team_id']not in [f['home'],f['away']]or clock(f['kickoff'])!=clock(p['kickoff'])or clock(doc['published_at'])>=clock(p['kickoff']):excluded+=1;continue
                values=[p['p_start'],p['xmins'],p.get('simulated_minutes'),p['xpts']]
                if any(v is None or not math.isfinite(v)for v in values)or not 0<=p['p_start']<=1 or not all(0<=v<=90 for v in values[1:3]):raise ValueError('Invalid original archived prediction')
                label=gws.get((pid,gw));match=matches.get((pid,fid));actual=None;basis=None
                if f.get('finished')and label and label['gw_complete']:
                    if match and not match.get('provisional')and match['team_id']==person['team_id']:
                        actual=match['stats'];basis='official_fixture_history'
                    elif all(label['stats'].get(k)==0 for k in ['minutes','starts','total_points']):
                        actual=label['stats'];basis='official_final_GW_all_zero'
                row=dict(gw=gw,player_id=pid,fixture_id=fid,expected_minutes=p['simulated_minutes'],mm_expected_minutes=p['xmins'],xp=p['xpts'],p_start=p['p_start'],actual_minutes=actual['minutes']if actual else None,actual_points=actual['total_points']if actual else None,actual_starts=actual['starts']if actual else None,final=actual is not None,label_basis=basis)
                rows.append(row)
                if actual:
                    if not all(math.isfinite(actual[k])for k in ['minutes','starts','total_points'])or not 0<=actual['minutes']<=90 or actual['starts']not in (0,1):raise ValueError('Invalid historical actual result')
                    errors.append(dict(minute_mae=abs(row['expected_minutes']-actual['minutes']),minute_bias=row['expected_minutes']-actual['minutes'],mm_minute_mae=abs(p['xmins']-actual['minutes']),xp_mae=abs(p['xpts']-actual['total_points']),xp_bias=p['xpts']-actual['total_points'],start_brier=(p['p_start']-actual['starts'])**2));labels.append(row)
                else:pending+=1
            if rows:
                final=all(r['final']for r in rows)
                players.setdefault(pid,[]).append(dict(gw=gw,published_at=doc['published_at'],publication_commit=doc['publication_commit'],expected_minutes=sum(r['expected_minutes']for r in rows),mm_expected_minutes=sum(r['mm_expected_minutes']for r in rows),xp=sum(r['xp']for r in rows),p_start=[r['p_start']for r in rows],actual_minutes=sum(r['actual_minutes']for r in rows)if final else None,actual_points=sum(r['actual_points']for r in rows)if final else None,actual_starts=sum(r['actual_starts']for r in rows)if final else None,final=final))
        weeks.append(dict(gw=gw,status='complete'if errors and not pending else'pending_results',scored_rows=len(errors),pending_rows=pending,excluded_rows=excluded,publication_commit=doc['publication_commit'],published_at=doc['published_at'],data_asof=doc['data_asof'],archive_sha256=doc['archive_sha256'],model=doc['model'],**{k:mean(errors,k)for k in ['minute_mae','minute_bias','mm_minute_mae','xp_mae','xp_bias','start_brier']}))
    summaries={}
    for pid,rows in players.items():
        final=[r for r in rows if r['final']]
        summaries[pid]=dict(scored_gws=len(final),minute_mae=mean([dict(error=abs(r['expected_minutes']-r['actual_minutes']))for r in final],'error'),xp_mae=mean([dict(error=abs(r['xp']-r['actual_points']))for r in final],'error'),xp_bias=mean([dict(error=r['xp']-r['actual_points'])for r in final],'error'))
    return dict(model='original_locked_vFinal_diagnostic',label='Oprindelig MM → PM · publiceret dengang',scope='Separate from B; PM expected_minutes are archived simulation minutes, MM analytic minutes are retained separately. No p60/p90 reconstruction.',weeks=weeks),players,summaries,labels

def attach(source,ref,result,traces):
    source=Path(source);raw={name:(source/'history'/name).read_bytes()for name in ['match-results.json','current-players.json','live-fixtures.json']};index=json.loads((source/'history/index.json').read_text())
    for name,data in raw.items():
        if hashlib.sha256(data).hexdigest()!=index['files'][name]:raise ValueError('Historical source checksum mismatch: '+name)
    history,catalogue,fixtures=(json.loads(raw[n])for n in ['match-results.json','current-players.json','live-fixtures.json'])
    selected,audit=recover(ref,result['season'],result['updated_at'])
    legacy,players,summaries,labels=evaluate(selected,history,catalogue,fixtures,json.loads((source/'current/forecast.json').read_text()))
    legacy['archive_audit']=audit;result['original_model']=legacy
    completed=sorted({r['gw']for r in history['gw_rows']if r['gw_complete']})
    result['history_coverage']=dict(observed_at=history['observed_at'],completed_gws=completed,player_gw_rows=sum(r['gw_complete']for r in history['gw_rows']),player_fixture_rows=len(history['match_rows']),players=len(catalogue['players']),fixtures=sum(bool(f.get('finished'))for f in fixtures['fixtures']),b_forecast_gws=sorted(w['gw']for w in result['weeks']if w.get('forecast_sha256')),original_forecast_gws=sorted(selected),missing_original_gws=sorted(set(completed)-set(selected)),source_checksums=index['files'],note='Actual results are available independently of forecasts. Missing historic forecasts are never recomputed or replaced with current predictions.')
    for p in traces['players']:
        p['original_weeks']=players.get(p['id'],[]);p['original_summary']=summaries.get(p['id'],dict(scored_gws=0,minute_mae=None,xp_mae=None,xp_bias=None))
    out=source/'weekly-review';out.mkdir(exist_ok=True)
    early=baseline_archive(ref,result['season'])
    if early:
        payload=(json.dumps(early,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode();(out/'baseline-archive.json').write_bytes(payload)
        result['early_baseline_archive']={k:early[k]for k in ['model','published_at','publication_commit','status','reason']}|dict(file='baseline-archive.json',sha256=hashlib.sha256(payload).hexdigest(),players=len(early['forecasts']),origin_gw=early['meta']['next_gw'])
    payload=(json.dumps(dict(observed_at=history['observed_at'],records=labels),sort_keys=True,allow_nan=False)+'\n').encode();(out/'original-outcomes.json').write_bytes(payload);legacy['outcomes_sha256']=hashlib.sha256(payload).hexdigest()


def baseline_archive(ref,season):
    """Retain the early simple model as evidence, never as an MM/PM forecast."""
    for line in git('log',ref,'--format=%H %cI','--','app/data.js').decode().splitlines():
        commit,published=line.split(' ',1);raw=git('show',commit+':app/data.js').decode()
        if not raw.startswith('window.FPL_DATA='):continue
        doc=json.loads(raw.removeprefix('window.FPL_DATA=').rstrip(';\n'))
        meta=doc.get('meta',{})
        if meta.get('model_version')!='live_simple_baseline_v0.1'or meta.get('season','').replace('/','-')!=season:continue
        return dict(schema='fpl-early-baseline-archive-v1',model=meta['model_version'],published_at=published,publication_commit=commit,source_path='app/data.js',source_sha256=hashlib.sha256(raw.encode()).hexdigest(),meta=meta,forecasts=doc['forecasts'],status='archive_only_not_MM_PM_evaluation',reason='Different simple baseline; original metadata has no timezone-qualified feature cutoff or stable player codes. Kept as historical evidence, excluded from MM/PM accuracy.')
    return None
