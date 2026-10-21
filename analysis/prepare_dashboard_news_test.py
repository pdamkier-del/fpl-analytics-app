"""Private synthetic browser-test fixture, never copied into public artifacts."""
from pathlib import Path
from datetime import datetime,timedelta
import argparse,json
from run_live_locked_ts import run

def prepare(forecast_path,out):
    f=json.loads(Path(forecast_path).read_text());people=f['players'];chosen=[];clubs={}
    for pos,count in [(1,2),(2,5),(3,5),(4,3)]:
        options=sorted((p for p in people if p['position']==pos),key=lambda p:(0 if p['name']in ['Haaland','Penders']else 1,p['price_tenths'],p['id']))
        for p in options:
            if clubs.get(p['team_id'],0)>=3:continue
            chosen.append(p);clubs[p['team_id']]=clubs.get(p['team_id'],0)+1;count-=1
            if not count:break
        if count:raise ValueError('Could not create legal synthetic UI fixture')
    state=dict(season=f['season'],gw=f['gws'][0],source='SYNTHETIC_DASHBOARD_UI_TEST_NOT_USER_TEAM',observed_at=(datetime.fromisoformat(f['data_asof'].replace('Z','+00:00'))-timedelta(hours=2)).isoformat(),bank_tenths=1000-sum(p['price_tenths']for p in chosen),free_transfers=2,squad=[dict(id=p['id'],purchase_price_tenths=p['price_tenths'])for p in chosen],chips_used={c:[]for c in ['wildcard','free_hit','bench_boost','triple_captain']})
    if state['bank_tenths']<0:raise ValueError('Synthetic fixture over budget')
    if f.get('chain_version')=='B-MM-PM-TS-v1':
        from b_preview_ts import preview_scoring
        with preview_scoring(f):result=run(f,state,include_chips=False)
    else:result=run(f,state,include_chips=False)
    result.update(validation_only=False,forecast_variant=f['model'],forecast_sha256=f['forecast_sha256'])
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(dict(state=state,result=result),ensure_ascii=False,allow_nan=False))
    print('Prepared private synthetic dashboard test fixture; original TS ran six GWs')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.forecast,a.out)
