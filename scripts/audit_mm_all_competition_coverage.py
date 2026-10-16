#!/usr/bin/env python3
"""MM-only forensic inventory of archived other-competition appearances.

This script does not infer unobserved substitutions from player minutes,
and never labels a match 'important' from its outcome. Coverage first.
"""
import argparse,csv,gzip,json,collections
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE24=ROOT/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz'
SOURCE25=ROOT/'data_v1_1/raw/all-competitions-2025-26'
FIELDS=('competition','competition_name','tournament','tournament_name','league','league_name',
        'minutes','minutes_played','playing_time','started','is_starting','is_starter',
        'subbed_on','subbed_off','start_min','finish_min','match_id','provider_match_id',
        'player_uuid','identity_status','fixture_id','kickoff_at','date')
def read_jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)
def summarize(rows,origin):
    keys=collections.Counter();vals=collections.defaultdict(collections.Counter)
    n=0;samples=[]
    for row in rows:
        n+=1
        keys.update(row.keys())
        for k in FIELDS:
            if k in row and k in FIELDS[:6]:
                vals[k][str(row[k])]+=1
        if len(samples)<3:
            samples.append({k:row.get(k) for k in FIELDS if k in row})
    return dict(origin=origin,rows=n,columns=keys.most_common(),
                competition_values={k:dict(v.most_common(40)) for k,v in vals.items()},
                sample_fields=samples)
def run(out):
    result={'purpose':'Source inventory; NOT substitute count; NOT match-importance test',
            '2024':None,'2025':[]}
    if SOURCE24.exists():
        result['2024']=summarize(read_jsonl(SOURCE24),str(SOURCE24.relative_to(ROOT)))
    else:
        result['2024']={'status':'Not Available: source file missing'}
    if SOURCE25.exists():
        for p in sorted(SOURCE25.glob('GW*/*.csv')):
            if p.name not in ('lineups.csv','player_stats.csv','players.csv','matches.csv','fixtures.csv'):
                continue
            with p.open(newline='',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f)
                rows=summarize(reader,str(p.relative_to(ROOT)))
            result['2025'].append(rows)
    result['2025_file_count']=len(result['2025'])
    result['requires_verified_event_timing']=True
    result['substitutions_counted']=False
    result['match_importance_tested']=False
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('2024 rows',result['2024'].get('rows','unavailable'))
    print('2025 files',result['2025_file_count'])
    print('Inventory saved',dest)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='analysis/results/mm-match-importance-20261016/source-inventory.json')
    a=p.parse_args();run(a.out)
