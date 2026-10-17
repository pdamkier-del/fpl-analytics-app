#!/usr/bin/env python3
"""Capture timestamped official evidence; never fabricate a missing B forecast.

The workflow artifact is an external timestamp witness. An absent verified B
feature producer is reported as blocked, rather than logging a fake prediction.
No manager state, authentication or account data is fetched.
"""
import argparse,hashlib,json,os,urllib.request
from datetime import datetime,timezone
from pathlib import Path


def capture(bootstrap,fixtures,*,observed_at,workflow):
    now=datetime.fromisoformat(observed_at)
    if now.tzinfo is None:raise ValueError('Timezone required')
    event=next((e for e in bootstrap['events'] if e.get('is_next')),None)
    if event is None:raise ValueError('No official next GW')
    deadline=datetime.fromisoformat(event['deadline_time'].replace('Z','+00:00'))
    if now>=deadline:raise ValueError('Capture after official deadline')
    ids=[p['id'] for p in bootstrap['elements']]
    if not ids or len(set(ids))!=len(ids):raise ValueError('Official player identities missing/duplicated')
    def sha(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(status='BLOCKED_CURRENT_B_FEATURES',scope='source_capture_not_forecast',
        observed_at=observed_at,origin_gw=event['id'],origin_deadline=event['deadline_time'],
        official_players=len(ids),bootstrap_sha256=sha(bootstrap),fixtures_sha256=sha(fixtures),
        workflow=workflow,locked_model_active=False,forecasts_registered=0,
        reason='No verified current PR8 role/chance/return-duration feature pack. Legacy/vNext is not B. Source capture is not a prospective prediction.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    def get(endpoint):
        with urllib.request.urlopen('https://fantasy.premierleague.com/api/'+endpoint,timeout=30) as r:return json.load(r)
    bootstrap=get('bootstrap-static/');fixtures=get('fixtures/')
    # Receipt time is after both responses. No claim of the source's unknown
    # publication time; subsequent predictions must use a later as-of cutoff.
    at=datetime.now(timezone.utc).isoformat()
    workflow='https://github.com/'+os.environ.get('GITHUB_REPOSITORY','pdamkier-del/fpl-analytics-app')+'/actions/runs/'+os.environ.get('GITHUB_RUN_ID','local-unwitnessed')
    receipt=capture(bootstrap,fixtures,observed_at=at,workflow=workflow)
    digest=hashlib.sha256(json.dumps(receipt,sort_keys=True).encode()).hexdigest()
    out=a.out/digest;out.mkdir(parents=True,exist_ok=False)
    for n,obj in [('receipt.json',receipt),('bootstrap.json',bootstrap),('fixtures.json',fixtures)]:
        (out/n).write_text(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(receipt))
if __name__=='__main__':main()
