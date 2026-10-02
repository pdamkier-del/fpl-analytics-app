#!/usr/bin/env python3
"""Download the minimal public FPL-Core-Insights role layer for one PL season.

Downloads only:
  GW*/fixtures.csv
  GW*/lineups.csv
  GW*/average_positions.csv

Then validates the 2025/26 Premier League invariants documented by the source:
380 fixtures, 8,360 starters (=22/match), and 380 unique lineup match IDs.
This script is intentionally separate from ingestion so source acquisition can be
re-run/audited without touching the model database.
"""
from __future__ import annotations
import argparse, csv, io, json, time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE='https://raw.githubusercontent.com/olbauday/FPL-Core-Insights/refs/heads/main/data/{season}/By%20Tournament/Premier%20League/GW{gw}/{name}'
FILES=('fixtures.csv','lineups.csv','average_positions.csv')


def get(url, retries=4, timeout=45):
    last=None
    for i in range(retries):
        try:
            req=Request(url,headers={'User-Agent':'FPL-xPts-role-data/1.0'})
            with urlopen(req,timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last=e
            if i+1<retries: time.sleep(1.5*(2**i))
    raise RuntimeError(f'failed after {retries} attempts: {url}: {last}')


def count_csv(path):
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--season-source',default='2025-2026',help='source repo folder, e.g. 2025-2026')
    ap.add_argument('--out-root',required=True)
    ap.add_argument('--gw-start',type=int,default=1)
    ap.add_argument('--gw-end',type=int,default=38)
    ap.add_argument('--overwrite',action='store_true')
    ap.add_argument('--dry-run',action='store_true')
    a=ap.parse_args()
    out=Path(a.out_root)
    manifest=[]
    for gw in range(a.gw_start,a.gw_end+1):
        d=out/f'GW{gw}'
        for name in FILES:
            url=BASE.format(season=a.season_source,gw=gw,name=name)
            p=d/name
            manifest.append({'gw':gw,'name':name,'url':url,'path':str(p)})
            if a.dry_run: continue
            if p.exists() and not a.overwrite: continue
            b=get(url)
            if not b.strip(): raise RuntimeError(f'empty response: {url}')
            d.mkdir(parents=True,exist_ok=True)
            p.write_bytes(b)
    if a.dry_run:
        print(json.dumps({'files':len(manifest),'first':manifest[:3],'last':manifest[-3:]},indent=2)); return

    fixtures=[]; lineups=[]; avgs=[]
    for gw in range(a.gw_start,a.gw_end+1):
        d=out/f'GW{gw}'
        fixtures.extend(count_csv(d/'fixtures.csv'))
        lineups.extend(count_csv(d/'lineups.csv'))
        avgs.extend(count_csv(d/'average_positions.csv'))
    match_ids={r.get('match_id') for r in fixtures if r.get('match_id')}
    lineup_match_ids={r.get('match_id') for r in lineups if r.get('match_id')}
    starters=sum(str(r.get('is_starting','')).strip().lower() in {'true','1','yes'} for r in lineups)
    report={
        'season_source':a.season_source,
        'gw_range':[a.gw_start,a.gw_end],
        'fixture_rows':len(fixtures),
        'unique_fixture_match_ids':len(match_ids),
        'lineup_rows':len(lineups),
        'unique_lineup_match_ids':len(lineup_match_ids),
        'starter_rows':starters,
        'average_position_rows':len(avgs),
        'files':len(manifest),
    }
    # Exact published invariants only apply to full 2025/26 PL download.
    if a.season_source=='2025-2026' and a.gw_start==1 and a.gw_end==38:
        expected={'fixture_rows':380,'unique_fixture_match_ids':380,'unique_lineup_match_ids':380,'starter_rows':8360}
        bad={k:(report[k],v) for k,v in expected.items() if report[k]!=v}
        if bad:
            raise RuntimeError(f'source validation failed: {bad}; report={report}')
        if len(avgs)<11000:
            raise RuntimeError(f'average-position coverage unexpectedly low: {len(avgs)}')
    (out/'ROLE_SOURCE_MANIFEST.json').write_text(json.dumps({'report':report,'files':manifest},indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
