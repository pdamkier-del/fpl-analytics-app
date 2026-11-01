"""Fresh-process TS memory/runtime on a labelled synthetic legal squad."""
import argparse,json,resource,time
from pathlib import Path
from service.preview_manager_job import calculate
from run_live_locked_ts import CHIPS

def main():
 p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();start=time.perf_counter();forecast=json.loads(a.forecast.read_text());clubs={};chosen=[]
 for pos,count in [(1,2),(2,5),(3,5),(4,3)]:
  for person in sorted([p for p in forecast['players']if p['position']==pos],key=lambda p:(p['price_tenths'],p['id'])):
   if clubs.get(person['team_id'],0)>=3:continue
   chosen.append(person);clubs[person['team_id']]=clubs.get(person['team_id'],0)+1;count-=1
   if not count:break
  if count:raise ValueError('Cannot construct legal TS regression squad')
 state=dict(season=forecast['season'],gw=min(forecast['gws']),source='SYNTHETIC_PRECISION_REGRESSION_NOT_USER_TEAM',validation_only=True,observed_at=forecast['data_asof'],bank_tenths=1000-sum(p['price_tenths']for p in chosen),free_transfers=2,squad=[dict(id=p['id'],purchase_price_tenths=p['price_tenths'])for p in chosen],chips_used={c:[]for c in CHIPS});before=json.dumps(state,sort_keys=True);parse_seconds=time.perf_counter()-start;start=time.perf_counter();result=calculate(forecast,state);assert result['ts_ran']and len(result['plan']['path'])==len(forecast['gws']);assert before==json.dumps(state,sort_keys=True)
 receipt=dict(passed=True,scope='Independent fresh-process canonical forecast + original TS; explicit synthetic legal squad; no private manager state or network POST',draws=forecast['scenario_contract']['draws'],parse_seconds=parse_seconds,ts_seconds=time.perf_counter()-start,process_peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,horizon=len(forecast['gws']),forecast_sha256=forecast['forecast_sha256'],state_preserved=True,backend_rules_unchanged=True)
 a.out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
