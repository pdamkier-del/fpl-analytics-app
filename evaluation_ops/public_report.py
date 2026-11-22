"""Generate append-only reports from original public Git snapshots and final official labels."""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
from datetime import datetime,timezone
import requests
from .reporting import score,canonical,digest,validate_bundle
API='https://fantasy.premierleague.com/api/'
PUBLIC_PATH='app/mm-preview/current/'

def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL)
def recover(repo,ref,*,season=None,limit=2000):
 commits=git(repo,'log',ref,'--format=%H',f'--max-count={limit}','--',PUBLIC_PATH+'index.json').decode().splitlines();selected={};rejected=[]
 for commit in commits:
  try:
   read=lambda name:git(repo,'show',commit+':'+PUBLIC_PATH+name)
   index=json.loads(read('index.json'));gw=min(index.get('gws',[]))if index.get('gws')else None
   if gw in selected:continue
   published=git(repo,'show','-s','--format=%cI',commit).decode().strip()
   from .ts_capture import ledger
   if not index.get('origin_deadline')or not ledger.clock(index['data_asof'])<=ledger.clock(published)<ledger.clock(index['origin_deadline']):continue
   def checked(name,key):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+\.json',name):raise ValueError('Invalid snapshot path')
    raw=read(name)
    if hashlib.sha256(raw).hexdigest()!=index[key]:raise ValueError('Original file hash mismatch')
    return json.loads(raw)
   f=checked(index['forecast_file'],'forecast_file_sha256');m=checked(index['mm_file'],'mm_file_sha256');docs=checked('existing-app-data.json','existing_app_data_sha256')
   if season and f['season']!=season:continue
   bundle={'season':f['season'],'forecast':f,'mm':m,'documents':docs,'receipt':{'published_at':published,'publication_commit':commit,'forecast_sha256':f['forecast_sha256'],'archive_basis':'original_public_forecast_snapshot'}}
   gw=validate_bundle(bundle);selected[gw]=bundle
  except (ValueError,KeyError,TypeError,subprocess.CalledProcessError):rejected.append({'commit':commit,'reason':'snapshot_contract_or_source_missing'})
 return selected,rejected

def get(endpoint):
 r=requests.get(API+endpoint,headers={'Cache-Control':'no-cache'},timeout=60);r.raise_for_status();return r.json()

def collect_labels(bundle,bootstrap,fixtures,*,fetch=get,observed_at=None):
 gw=validate_bundle(bundle);event=next(e for e in bootstrap['events']if e['id']==gw);base={'season':bundle['season'],'event':event,'fixtures':fixtures,'identities':[{'id':p['id'],'code':p['code']}for p in bootstrap['elements']],'observed_at':observed_at or datetime.now(timezone.utc).isoformat(),'rows':[]}
 if not(event.get('finished')and event.get('data_checked')):return base
 live={p['id']:p for p in fetch(f'event/{gw}/live/')['elements']};games={f['id']:f for f in fixtures};catalog={p['id']:p for p in bundle['documents']['documents']['current-players.json']['players']};current={p['id']:p for p in bootstrap['elements']}
 for p in bundle['forecast']['players']:
  if p['id']not in current or p['id']not in catalog or current[p['id']]['code']!=catalog[p['id']]['code']:continue
  w=next(w for w in p['weeks']if w['gw']==gw);a=live.get(p['id'])
  if a is None:continue
  wanted={int(x['fixture_uuid'].split('-')[-1])for x in w['fixtures']};schedule={x['id']for x in fixtures if x.get('event')==gw and p['team_id']in[x['team_h'],x['team_a']]}
  if wanted!=schedule:continue
  explains={x['fixture']:x['stats']for x in a['explain']};history=None
  if len(wanted)>1 or len(explains)>1:
   history={h['fixture']:h for h in fetch(f"element-summary/{p['id']}/")['history']}
  for fx in wanted:
   game=games[fx]
   if not game.get('finished'):continue
   if history is not None:
    h=history.get(fx)
    if h is None:continue
    if (game['team_h']if h['was_home']else game['team_a'])!=p['team_id']:continue
    stats={**h,'total_points':h['total_points'],'starts':h['starts']}
   else:stats=a['stats']
   explain=explains.get(fx)
   if explain is None:
    if len(wanted)==1 and all(stats.get(k)==0 for k in ['minutes','starts','total_points']):explain=[]
    else:continue
   base['rows'].append({'fixture':fx,'id':p['id'],'team_id':p['team_id'],'stats':stats,'explain':explain})
 return base

def write_report(out,bundle,labels):
 report=score(bundle,labels);root=Path(out);root.mkdir(parents=True,exist_ok=True)
 # Outcome corrections make a new version; a forecast is never rebuilt or overwritten.
 key=digest({'forecast':bundle['forecast']['forecast_sha256'],'labels':labels});folder=root/f"GW{report['gw']:02d}"/key;folder.mkdir(parents=True,exist_ok=True)
 for name,obj in [('report.json',report),('source-receipt.json',bundle['receipt']),('outcome-receipt.json',{'sha256':digest(labels),'observed_at':labels['observed_at'],'event':labels['event']})]:
  raw=canonical(obj);path=folder/name
  if path.exists():
   if path.read_bytes()!=raw:raise ValueError('Immutable report would change')
  else:
   fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
   with os.fdopen(fd,'wb')as h:h.write(raw)
 return report,str(folder.relative_to(root))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path('.'));p.add_argument('--ref',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--season',default='2026-27');a=p.parse_args();bundles,rejected=recover(a.repo,a.ref,season=a.season);bootstrap=get('bootstrap-static/');fixtures=get('fixtures/');now=datetime.now(timezone.utc).isoformat();index=[]
 for gw,b in sorted(bundles.items()):
  labels=collect_labels(b,bootstrap,fixtures,observed_at=now);report,path=write_report(a.out,b,labels);index.append({'gw':gw,'status':report['status'],'path':path,'forecast_sha256':report['forecast_sha256'],'scored_rows':report['scored_rows']})
 # This file is a run summary, not a forecast or a replacement for older versioned reports.
 (a.out/'index.json').write_bytes(canonical({'schema':'fpl-operational-report-index-v1','run_at':now,'reports':index,'rejected_public_snapshots':rejected,'private_manager_data_included':False,'model_changed':False}))
 print(json.dumps({'rounds':len(index),'completed':sum(r['status']=='complete'for r in index),'private_data_exported':False}))
if __name__=='__main__':main()
