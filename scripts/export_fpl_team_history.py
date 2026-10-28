"""Export a public FPL entry history for private browser import, never publication."""
import argparse,json,concurrent.futures
from datetime import datetime,timezone
from pathlib import Path
import requests
API='https://fantasy.premierleague.com/api/'
def get(path):
 r=requests.get(API+path,timeout=40);r.raise_for_status();return r.json()
def collect(entry,season):
 if type(entry) is not int or not 0<entry<1000000000:raise ValueError('Ugyldigt manager-ID')
 history=get(f'entry/{entry}/history/');bootstrap=get('bootstrap-static/');events={e['id']:e for e in bootstrap['events']}
 from datetime import datetime
 first=min(events.values(),key=lambda e:e['id'])
 year=datetime.fromisoformat(first['deadline_time'].replace('Z','+00:00')).year
 if season!=f'{year}-{str(year+1)[-2:]}':raise ValueError('FPL-sæsonen matcher ikke den viste rapport')
 if len(history['current'])>38:raise ValueError('Ugyldig FPL-historik')
 def load(row):
  gw=row['event'];data=get(f'entry/{entry}/event/{gw}/picks/');e=events[gw];return dict(gw=gw,picks=data['picks'],automatic_subs=data.get('automatic_subs',[]),active_chip=data.get('active_chip'),entry_history=data['entry_history'],final=bool(e['finished']and e['data_checked']))
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:weeks=list(pool.map(load,history['current']))
 return dict(schema='fpl-official-entry-history-v1',season=season,entry_id=entry,observed_at=datetime.now(timezone.utc).isoformat(),weeks=weeks)
def main():
 p=argparse.ArgumentParser();p.add_argument('--entry',required=True,type=int);p.add_argument('--season',required=True);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 if a.entry<=0:raise ValueError('Use the public numeric entry ID, never credentials')
 data=collect(a.entry,a.season)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print('Exported',len(data['weeks']),'gameweeks to private import file; no repository/publication write')
if __name__=='__main__':main()
