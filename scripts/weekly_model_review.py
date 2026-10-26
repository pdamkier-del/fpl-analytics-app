"""Weekly out-of-sample MM/PM review. No retrospective predictions or private TS data."""
import gzip,hashlib,json,subprocess,concurrent.futures
from pathlib import Path
from datetime import datetime,timezone
import requests
import pandas as pd
from archive_prospective_player_forecast import utc
from score_prospective_player_forecast import score

API='https://fantasy.premierleague.com/api/'
PATH='app/mm-preview/input-audit/'

def git(*args):return subprocess.check_output(['git',*args])
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
    return list(candidates.values())+late

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
            row.update(result,gw=gw,status='complete'if result['scored_rows']and not result['pending_rows']else'pending_results',forecast_sha256=m['forecast_sha256'],publication_commit=receipt['commit'],published_at=receipt['published_at'],model_code=m.get('forecast_code_sha256',{}))
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
    return dict(schema='fpl-weekly-model-review-v1',season=season,updated_at=now,weeks=weeks,season_summary=aggregate,completed_scored_gws=sum(w['status']=='complete'for w in weeks),missing_gws=[w['gw']for w in weeks if w['status']=='missing_predeadline_forecast'],excluded_late_captures=excluded,selection='Latest publicly committed forecast before its origin GW deadline; first forecast GW only; each player/fixture once.',scope='B-model versions as published; all registered forecast players, including non-appearances.',ts=dict(status='not_measured',reason='Private transfer/chip plans have not been archived before deadlines. Player accuracy does not measure transfer decisions.'),sources=[API+'bootstrap-static/',API+'fixtures/',API+'element-summary/{player_id}/'],production_changed=False,model_retrained=False)

COLS=['season','fixture_uuid','player_uuid','team_id','is_final','known_at','kickoff','started','minutes','total_points']
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
    def load(item):
        player_id,predictions=item;r=requests.get(API+f'element-summary/{player_id}/',timeout=45);r.raise_for_status();history={h['fixture']:h for h in r.json()['history']};rows=[]
        for p,fixture in predictions:
            h=history.get(fixture['id'])
            if h is None:continue # No fabricated zero-minute label.
            if (fixture['team_h']if h['was_home']else fixture['team_a'])!=p['team_id']or utc(h['kickoff_time'])!=utc(p['kickoff']):raise ValueError('Official fixture identity mismatch')
            rows.append(dict(season=bootstrap['season'],fixture_uuid=p['fixture_uuid'],player_uuid=p['player_uuid'],team_id=p['team_id'],is_final=True,known_at=now,kickoff=p['kickoff'],started=h['starts'],minutes=h['minutes'],total_points=h['total_points']))
        return rows
    with concurrent.futures.ThreadPoolExecutor(max_workers=6)as pool:rows=[r for batch in pool.map(load,needed.items())for r in batch]
    return pd.DataFrame(rows,columns=COLS)

def build(source,ref):
    source=Path(source);now=datetime.now(timezone.utc).isoformat();receipts=recover(ref)
    # Include the new capture only once it has an actual public commit on a later run.
    bootstrap=requests.get(API+'bootstrap-static/',timeout=45);bootstrap.raise_for_status();bootstrap=bootstrap.json()
    # The archived receipt is authoritative for season identity; no guessed year conversion.
    season=json.loads((source/'current/forecast.json').read_text())['season'];bootstrap['season']=season
    fixtures=requests.get(API+'fixtures/',timeout=45);fixtures.raise_for_status();fixtures=fixtures.json()
    selected,_=select(receipts,season,now);outcomes=collect_outcomes(selected,bootstrap,fixtures,now)
    result=report(receipts,bootstrap,fixtures,outcomes,now=now)
    out=source/'weekly-review';out.mkdir(exist_ok=True)
    raw=(json.dumps(dict(observed_at=now,records=outcomes.to_dict(orient='records')),sort_keys=True,allow_nan=False)+'\n').encode()
    (out/'outcomes.json').write_bytes(raw);result['outcomes_sha256']=hashlib.sha256(raw).hexdigest()
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:result[k]for k in ['season','updated_at','completed_scored_gws','missing_gws','excluded_late_captures']}));return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('app/mm-preview'));p.add_argument('--ref',default='FETCH_HEAD');a=p.parse_args();build(a.source,a.ref)
