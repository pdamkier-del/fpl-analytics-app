#!/usr/bin/env python3
"""Reject an online manager request if the official FPL deadline/GW moved."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def verify(forecast,bootstrap,now):
    upcoming=[e for e in bootstrap['events'] if e.get('is_next')]
    if len(upcoming)!=1:raise ValueError('Official next GW is unavailable')
    event=upcoming[0]
    deadline=datetime.fromisoformat(event['deadline_time'].replace('Z','+00:00'))
    if event['id']!=min(forecast['gws']) or now>=deadline:
        raise ValueError('Official GW/deadline changed; a fresh verified forecast is required')
    recorded=datetime.fromisoformat(forecast['origin_deadline'].replace('Z','+00:00'))
    if recorded!=deadline:
        raise ValueError('Official deadline differs from the forecast; rebuild required')
    return event['id']

def main():
    forecast=json.loads((ROOT/'app/vfinal-diagnostic.json').read_text())
    bootstrap=json.load(urllib.request.urlopen('https://fantasy.premierleague.com/api/bootstrap-static/',timeout=30))
    gw=verify(forecast,bootstrap,datetime.now(timezone.utc))
    print('Official forecast window verified: GW',gw)

if __name__=='__main__':main()
