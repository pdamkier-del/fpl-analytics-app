"""Weekly out-of-sample MM/PM review. No retrospective predictions or private TS data."""
import gzip,hashlib,json,subprocess,concurrent.futures
from pathlib import Path
from datetime import datetime,timezone
import requests
import pandas as pd
from archive_prospective_player_forecast import utc,build_records
from score_prospective_player_forecast import score

API='https://fantasy.premierleague.com/api/'
PATH='app/mm-preview/input-audit/'

def git(*args):return subprocess.check_output(['git',*args])
def receipt_from_original_publication(forecast,mm,documents,*,published_at,recovered_at,commit):
    """Read old predictions, never rerun them. The original public clock is evidence."""
    published=utc(published_at)
    if utc(recovered_at)<published:raise ValueError('Recovery clock predates original publication')
    if not utc(forecast['data_asof'])<=published<utc(forecast['origin_deadline']):raise ValueError('Original publication was not before deadline')
    if documents['forecast_sha256']!=forecast['forecast_sha256']:raise ValueError('Historical catalogue differs from forecast')
    manifest,records=build_records(forecast,mm,recorded_at=published_at,catalogue=documents['documents']['current-players.json']['players'])
    manifest.update(recovered_at=recovered_at,archive_basis='original_public_forecast_snapshot',note='recorded_at is the original immutable Git publication time; this receipt was reconstructed later without recalculating any prediction.')
    return dict(manifest=manifest,records=records,published_at=published_at,commit=commit)

def recover(ref):
    """Recover timestamped public receipts already committed to the live branch."""
    commits=git('log',ref,'--format=%H','--',PATH+'prospective-ledger-manifest.json').decode().splitlines()
    candidates={};late=[]
    for commit in commits:
        m=json.loads(git('show',commit+':'+PATH+'prospective-ledger-manifest.json'))
        published=git('show','-s','--format=%cI',commit).decode().strip()
        receipt=dict(manifest=m,published_at=published,commit=commit)
        if utc(published)>=utc(m['origin_deadline']):
            late.append(dict(receipt,ineligible_capture=True));continue
        key=(m['season'],m['origin_deadline'])
        if key not in candidates or utc(published)>utc(candidates[key]['published_at']):candidates[key]=receipt
    for receipt in candidates.values():
        m=receipt['manifest'];packed=git('show',receipt['commit']+':'+PATH+m['file'])
        if hashlib.sha256(packed).hexdigest()!=m['sha256']:raise ValueError('Historical ledger checksum mismatch')
        receipt['records']=[json.loads(x)for x in gzip.decompress(packed).splitlines()]
    # Before the ledger format existed, complete sealed forecasts were already
    # public. Recover only an original commit genuinely before its GW deadline.
    deadlines={utc(r['manifest']['origin_deadline'])for r in candidates.values()}
    historical=[]
    for commit in git('log',ref,'--format=%H','--diff-filter=AM','--','app/mm-preview/current/index.json').decode().splitlines():
        index=json.loads(git('show',commit+':app/mm-preview/current/index.json'))
        if index.get('scope')!='prospective_preview' or not index.get('origin_deadline'):continue
        deadline=utc(index['origin_deadline']);published=git('show','-s','--format=%cI',commit).decode().strip()
        if deadline in deadlines or not utc(index['data_asof'])<=utc(published)<deadline:continue
        def checked(name,key):
            raw=git('show',commit+':app/mm-preview/current/'+name)
            if hashlib.sha256(raw).hexdigest()!=index[key]:raise ValueError('Original public forecast checksum mismatch')
            return json.loads(raw)
        forecast=checked(index['forecast_file'],'forecast_file_sha256')
        mm=checked(index['mm_file'],'mm_file_sha256');documents=checked('existing-app-data.json','existing_app_data_sha256')
        from fpl_v1_1_model.forecast_snapshot import require_snapshot
        require_snapshot(forecast)
        historical.append(receipt_from_original_publication(forecast,mm,documents,published_at=published,recovered_at=datetime.now(timezone.utc).isoformat(),commit=commit))
        deadlines.add(deadline)
    return list(candidates.values())+historical+late

def select(receipts,season,now):
    selected={};excluded=0
    for receipt in receipts:
        m=receipt['manifest']
        if m['season']!=season:continue
        if receipt.get('ineligible_capture'):excluded+=1;continue
        records=receipt['records']
        if len(records)!=m['records']:raise ValueError('Archive row count mismatch')
        recorded,data,deadline,published=map(utc,[m['recorded_at'],m['data_asof'],m['origin_deadline'],receipt['published_at']])
        if not data<=recorded<=published<=utc(now) or published>=deadline:excluded+=1;continue
        origin=min((r['gw']for r in records),default=None)
        if origin is None:continue
        if origin not in selected or published>utc(selected[origin]['published_at']):selected[origin]=receipt
    return selected,excluded

def report(receipts,bootstrap,fixtures,outcomes,*,now):
    season=str(bootstrap['season'])
    selected,excluded=select(receipts,season,now);weeks=[]
    for event in bootstrap['events']:
        gw=event['id']
        if not event.get('finished')and gw not in selected:continue
        receipt=selected.get(gw)
        row=dict(gw=gw,status='missing_predeadline_forecast',scored_rows=0,pending_rows=0)
        if receipt:
            m=dict(receipt['manifest']);records=[r for r in receipt['records']if r['gw']==gw];m['records']=len(records)
            # Only final, checked GW labels are passed to the existing scorer.
            final=event.get('finished')and event.get('data_checked')
            labels=outcomes if final else outcomes.iloc[:0]
            result=score(m,records,labels,asof=now)
            row.update(result,gw=gw,status='complete'if result['scored_rows']and not result['pending_rows']else'pending_results',forecast_sha256=m['forecast_sha256'],publication_commit=receipt['commit'],published_at=receipt['published_at'],model_code=m.get('forecast_code_sha256',{}),archive_basis=m.get('archive_basis','prospective_ledger'),recovered_at=m.get('recovered_at'))
            row['positions']=[]
            for pos in [1,2,3,4]:
                subset=[r for r in records if r['position']==pos]
                if subset:
                    sub=score(dict(m,records=len(subset)),subset,labels,asof=now)
                    row['positions'].append({k:sub[k]for k in ['scored_rows','minute_mae','minute_bias','xp_mae','xp_bias']}|{'position':pos})
        weeks.append(row)
    measured=[w for w in weeks if w['scored_rows']];n=sum(w['scored_rows']for w in measured)
    aggregate={k:sum(w[k]*w['scored_rows']for w in measured)/n if n else None for k in ['minute_mae','minute_bias','xp_mae','xp_bias']}
    aggregate.update(scored_rows=n,metrics=[])
    for event in ['start','0','60','90']:
        items=[m for w in measured for m in w['metrics']if m['event']==event];count=sum(m['rows']for m in items)
        aggregate['metrics'].append(dict(event=event,rows=count,**{k:sum(m[k]*m['rows']for m in items)/count if count else None for k in ['brier','bias','log_loss']}))
    return dict(schema='fpl-weekly-model-review-v1',season=season,updated_at=now,weeks=weeks,season_summary=aggregate,completed_scored_gws=sum(w['status']=='complete'for w in weeks),missing_gws=[w['gw']for w in weeks if w['status']=='missing_predeadline_forecast'],excluded_late_captures=excluded,selection='Latest publicly committed forecast before its origin GW deadline; first forecast GW only; each player/fixture once.',scope='B-model versions as published; all registered forecast players, including non-appearances.',ts=dict(status='not_measured',reason='Private transfer/chip plans have not been archived before deadlines. Player accuracy does not measure transfer decisions.'),sources=[API+'bootstrap-static/',API+'fixtures/',API+'element-summary/{player_id}/',API+'event/{gw}/live/'],production_changed=False,model_retrained=False)

COLS=['season','fixture_uuid','player_uuid','team_id','is_final','known_at','kickoff','started','minutes','total_points','source_url','label_basis']
def collect_outcomes(selected,bootstrap,fixtures,now):
    event_by={e['id']:e for e in bootstrap['events']};fixture_by={f['id']:f for f in fixtures};players={p['id']:p for p in bootstrap['elements']};needed={}
    for gw,receipt in selected.items():
        e=event_by.get(gw,{})
        if not(e.get('finished')and e.get('data_checked')):continue
        for p in receipt['records']:
            if p['gw']!=gw or not p['eligible_for_pre_match_validation']:continue
            fixture=fixture_by.get(int(p['fixture_uuid'].split('-')[-1]));person=players.get(p['player_id'])
            if not fixture or not fixture.get('finished')or not person or person.get('code')!=p.get('fpl_code'):continue
            if fixture['event']!=gw or utc(fixture['kickoff_time'])!=utc(p['kickoff'])or p['team_id']not in [fixture['team_h'],fixture['team_a']]:continue
            needed.setdefault(p['player_id'],[]).append((p,fixture))
    live={}
    for predictions in needed.values():
        for p,_ in predictions:
            if p['gw']not in live:
                r=requests.get(API+f"event/{p['gw']}/live/",timeout=45);r.raise_for_status();live[p['gw']]={e['id']:e['stats']for e in r.json()['elements']}
    def load(item):
        player_id,predictions=item;
        zero=all((s:=live[p['gw']].get(player_id))is not None and s.get('minutes')==0 and s.get('starts')==0 and s.get('total_points')==0 for p,_ in predictions)
        if zero:return [dict(season=bootstrap['season'],fixture_uuid=p['fixture_uuid'],player_uuid=p['player_uuid'],team_id=p['team_id'],is_final=True,known_at=now,kickoff=p['kickoff'],started=0,minutes=0,total_points=0,source_url=API+f"event/{p['gw']}/live/",label_basis='official_final_GW_all_zero')for p,_ in predictions]
        r=requests.get(API+f'element-summary/{player_id}/',timeout=45);r.raise_for_status();history={h['fixture']:h for h in r.json()['history']};rows=[]
        for p,fixture in predictions:
            h=history.get(fixture['id'])
            if h is None:continue # No fabricated zero-minute label.
            if (fixture['team_h']if h['was_home']else fixture['team_a'])!=p['team_id']or utc(h['kickoff_time'])!=utc(p['kickoff']):raise ValueError('Official fixture identity mismatch')
            rows.append(dict(season=bootstrap['season'],fixture_uuid=p['fixture_uuid'],player_uuid=p['player_uuid'],team_id=p['team_id'],is_final=True,known_at=now,kickoff=p['kickoff'],started=h['starts'],minutes=h['minutes'],total_points=h['total_points'],source_url=API+f'element-summary/{player_id}/',label_basis='official_fixture_history'))
        return rows
    with concurrent.futures.ThreadPoolExecutor(max_workers=6)as pool:rows=[r for batch in pool.map(load,needed.items())for r in batch]
    return pd.DataFrame(rows,columns=COLS)

def player_traces(selected,bootstrap,outcomes):
    labels={(r.fixture_uuid,r.player_uuid):r for r in outcomes.itertuples()}
    players={p['id']:dict(id=p['id'],name=p['web_name'],position=p['element_type'],weeks=[])for p in bootstrap['elements']}
    for gw,receipt in selected.items():
        grouped={}
        for p in receipt['records']:
            if p['gw']==gw and p['eligible_for_pre_match_validation']and p.get('fpl_code')is not None:grouped.setdefault(p['player_id'],[]).append(p)
        for player_id,records in grouped.items():
            if player_id not in players:continue
            actual=[labels.get((p['fixture_uuid'],p['player_uuid']))for p in records]
            complete=all(a is not None for a in actual)
            players[player_id]['weeks'].append(dict(gw=gw,forecast_sha256=receipt['manifest']['forecast_sha256'],published_at=receipt['published_at'],xp=sum(p['xp']for p in records),expected_minutes=sum(p['expected_minutes']for p in records),p_start=[p['p_start']for p in records],actual_minutes=sum(a.minutes for a in actual)if complete else None,actual_points=sum(a.total_points for a in actual)if complete else None,actual_starts=sum(a.started for a in actual)if complete else None,final=complete))
    for p in players.values():
        p['weeks'].sort(key=lambda w:w['gw']);final=[w for w in p['weeks']if w['final']];n=len(final)
        p['summary']=dict(scored_gws=n,minute_mae=sum(abs(w['expected_minutes']-w['actual_minutes'])for w in final)/n if n else None,xp_mae=sum(abs(w['xp']-w['actual_points'])for w in final)/n if n else None,xp_bias=sum(w['xp']-w['actual_points']for w in final)/n if n else None)
    return dict(schema='fpl-player-season-review-v1',season=bootstrap['season'],players=list(players.values()))

def attach_actual_history(traces,history,catalogue,bootstrap):
    """Actual stats can exist even when no forecast was saved. Never score these as predictions."""
    by={p['id']:p for p in traces['players']};codes={p['id']:p.get('code')for p in bootstrap['elements']};old_codes={p['id']:p.get('code')for p in catalogue['players']}
    for p in by.values():p['actual_history']=[]
    actual_season=history.get('season',catalogue.get('season'))
    if isinstance(actual_season,int):actual_season=f'{actual_season}-{(actual_season+1)%100:02d}'
    if actual_season!=bootstrap['season']:return
    traces['actual_history_observed_at']=history['observed_at']
    for r in history['gw_rows']:
        p=by.get(r['player_id'])
        if not p or not r['gw_complete']or codes.get(p['id'])is None or old_codes.get(p['id'])!=codes.get(p['id']):continue
        p['actual_history'].append(dict(gw=r['gw'],minutes=r['stats']['minutes'],points=r['stats']['total_points'],starts=r['stats']['starts']))

def build(source,ref):
    source=Path(source);now=datetime.now(timezone.utc).isoformat();receipts=recover(ref)
    # Include the new capture only once it has an actual public commit on a later run.
    bootstrap=requests.get(API+'bootstrap-static/',timeout=45);bootstrap.raise_for_status();bootstrap=bootstrap.json()
    # The archived receipt is authoritative for season identity; no guessed year conversion.
    season=json.loads((source/'current/forecast.json').read_text())['season'];bootstrap['season']=season
    fixtures=requests.get(API+'fixtures/',timeout=45);fixtures.raise_for_status();fixtures=fixtures.json()
    selected,_=select(receipts,season,now);outcomes=collect_outcomes(selected,bootstrap,fixtures,now)
    result=report(receipts,bootstrap,fixtures,outcomes,now=now)
    traces=player_traces(selected,bootstrap,outcomes);traces['updated_at']=now
    history=json.loads((source/'history/match-results.json').read_text())
    fixture_raw=(source/'history/live-fixtures.json').read_bytes();history_index=json.loads((source/'history/index.json').read_text())
    if hashlib.sha256(fixture_raw).hexdigest()!=history_index['files']['live-fixtures.json']:raise ValueError('Historical fixture season checksum mismatch')
    history['season']=json.loads(fixture_raw)['season']
    attach_actual_history(traces,history,json.loads((source/'history/current-players.json').read_text()),bootstrap)
    from season_round_benchmark import build as round_benchmarks
    result['round_benchmarks']=round_benchmarks(source)
    out=source/'weekly-review';out.mkdir(exist_ok=True)
    raw=(json.dumps(dict(observed_at=now,records=outcomes.to_dict(orient='records')),sort_keys=True,allow_nan=False)+'\n').encode()
    (out/'players.json').write_text(json.dumps(traces,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
    (out/'outcomes.json').write_bytes(raw);result['outcomes_sha256']=hashlib.sha256(raw).hexdigest()
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:result[k]for k in ['season','updated_at','completed_scored_gws','missing_gws','excluded_late_captures']}));return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('app/mm-preview'));p.add_argument('--ref',default='FETCH_HEAD');a=p.parse_args();build(a.source,a.ref)
