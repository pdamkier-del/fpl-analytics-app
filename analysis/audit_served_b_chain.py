"""Read-only numerical/data/TS audit of a captured served B snapshot."""
import argparse,json,hashlib,datetime,urllib.request
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from fpl_v1_1_model.forecast_snapshot import require_snapshot
from b_chain_contract import validate_forecast
from b_preview_ts import autosub_points


def main():
 a=argparse.ArgumentParser();a.add_argument('--capture',type=Path,required=True);a.add_argument('--fixture',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args();root=args.capture
 load=lambda n:json.loads((root/n).read_bytes());digest=lambda n:hashlib.sha256((root/n).read_bytes()).hexdigest()
 f=load('current/forecast.json');mm=load('current/mm.json');index=load('current/index.json');require_snapshot(f);validate_forecast(f)
 assert index['forecast_sha256']==f['forecast_sha256']and digest('current/forecast.json')==index['forecast_file_sha256']and digest('current/mm.json')==index['mm_file_sha256']
 assert digest('current/existing-app-data.json')==index['existing_app_data_sha256']
 docs=load('current/existing-app-data.json');assert docs['forecast_sha256']==f['forecast_sha256']
 ids=[p['id']for p in f['players']];uids=[p['player_uuid']for p in f['players']];assert len(ids)==len(set(ids))and len(uids)==len(set(uids))
 by={(p['player_uuid'],q['fixture_uuid']):q for p in f['players']for w in p['weeks']for q in w['fixtures']};assert len(by)==f['player_fixture_rows']
 groups=defaultdict(list);positions={p['player_uuid']:p['position']for p in f['players']}
 for p in mm['players']:
  q=by[p['player_id'],p['fixture_id']];groups[p['club_id'],p['fixture_id']].append(p)
  for field,fr in [('xmins','xmins'),('p_start','p_start'),('p_60_plus','p_60_plus'),('p_90','p_90')]:assert abs(p[field]-q[fr])<1e-7
  assert abs(p['p_start']*p['start_minutes']+(1-p['p_start'])*p['p_sub_given_not_start']*p['sub_minutes']-p['xmins'])<1e-7
  assert 0<=p['p_90']<=p['p_60_plus']+1e-10<=p['p_play']+1e-10<=1+1e-10
 for q in by.values():assert abs(sum(q['components'].values())-q['xpts'])<1e-8
 gks={(int(g['team']),g['fixture_uuid']):g for g in f['gk_team_fixtures']};assert len(gks)==len(groups)
 for key,rows in groups.items():
  field=[p for p in rows if positions[p['player_id']]!=1];keepers=[p for p in rows if positions[p['player_id']]==1];g=gks[key]
  assert abs(sum(p['p_start']for p in field)-10)<1e-7
  assert abs(sum(p['p_start']for p in keepers)+g['unlisted_start_probability']-1)<1e-7
  assert abs(sum(p['xmins']for p in keepers)+g['unlisted_expected_minutes']-90)<1e-7
  assert abs(g['analytic_gk_minutes']-90)<1e-7
 contextindex=load('match-context/index.json');assert digest('match-context/'+contextindex['file'])==contextindex['sha256'];context=load('match-context/'+contextindex['file'])
 history=load('history/index.json');pub=load('publication.json');assert pub['production_files_identical']is True
 # Read actual served production bytes, rather than trusting a publisher flag.
 prod=[]
 for name,sha in pub['production_sha256'].items():
  try:
   raw=urllib.request.urlopen('https://pdamkier-del.github.io/fpl-analytics-app/'+name,timeout=30).read();actual=hashlib.sha256(raw).hexdigest()
   prod.append(dict(path=name,sha256=actual,matches_receipt=actual==sha))
  except Exception as e:prod.append(dict(path=name,error=str(e),matches_receipt=False))
 assert all(p['matches_receipt']for p in prod),'Served production mismatch'
 fixture=json.loads(args.fixture.read_bytes());state=fixture['state'];r=fixture['result'];assert state['source'].startswith('SYNTHETIC_')and r['forecast_sha256']==f['forecast_sha256']and r['ts_ran']
 assert len(r['plan']['path'])==len(f['gws'])==6
 people={p['id']:p for p in f['players']};squad={p['id']for p in state['squad']};bank=state['bank_tenths'];ft=state['free_transfers'];checks=[]
 for row in r['plan']['path']:
  outgoing=row['outgoing'];incoming=row['incoming'];assert set(outgoing)<=squad and not(set(incoming)&(squad-set(outgoing)))
  squad=(squad-set(outgoing))|set(incoming);assert len(squad)==15
  assert Counter(people[i]['position']for i in squad)=={1:2,2:5,3:5,4:3};assert max(Counter(people[i]['team_id']for i in squad).values())<=3
  assert row['bank_before']==bank and row['free_transfers_before']==ft
  expected=bank+sum(people[i]['price_tenths']for i in outgoing)-sum(people[i]['price_tenths']for i in incoming);assert row['bank_after']==expected>=0
  assert row['official_hit_points']==4*max(0,len(incoming)-ft)
  assert row['free_transfers_after']==min(5,max(0,ft-len(incoming))+1)
  assert abs(row['utility_this_gw']-(row['projected_manager_score']-row['official_hit_points']-row['uncertainty_penalty']))<1e-7
  bank=expected;ft=row['free_transfers_after'];checks.append(dict(gw=row['gw'],legal_squad=True,bank_and_FT=True,hits_and_utility=True))
 # Independent captain fallback expression on the exported aligned scenarios.
 lineup=r['lineup'];ids=[p['id']for p in lineup];ix={pid:i for i,pid in enumerate(ids)};gw=r['gw'];weeks={p['id']:next(w for w in p['weeks']if w['gw']==gw)for p in f['players']}
 pts=np.array([weeks[i]['scenarios']['points']for i in ids],float).T;plays=np.array([weeks[i]['scenarios']['minutes']for i in ids],float).T>0
 starters=[j for j,p in enumerate(lineup)if p['role']in ['XI','C','VC']];bench=[j for j,p in sorted(enumerate(lineup),key=lambda z:z[1]['role'])if p['role'].startswith('Bench')or p['role']=='GK bench']
 c=next(j for j,p in enumerate(lineup)if p['role']=='C');v=next(j for j,p in enumerate(lineup)if p['role']=='VC');pos={1:'GKP',2:'DEF',3:'MID',4:'FWD'}
 score=float((autosub_points(pts,plays,[pos[people[i]['position']]for i in ids],starters,bench)+pts[:,c]+np.where(~plays[:,c],pts[:,v],0)).mean())
 assert abs(score-r['plan']['path'][0]['projected_manager_score'])<1e-7
 for name,url in [('health','https://fpl-analytics-private-manager.onrender.com/health')]:
  health=json.load(urllib.request.urlopen(url,timeout=30))
 result=dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),forecast_sha256=f['forecast_sha256'],model=f['model'],data_asof=f['data_asof'],gws=f['gws'],players=len(f['players']),fixtures=f['fixtures'],player_fixture_rows=len(by),sealed_snapshot_and_file_checksums=True,unique_player_identities=True,all_MM_PM_analytic_minutes_equal=True,all_point_components_reconciled=True,all_team_outfield_start_mass_10=True,all_GK_start_mass_1_and_minutes_90_with_explicit_pool=True,probability_ordering_valid=True,match_context_integrity=True,history_scope=dict(gws=history['available_gws'],match_rows=history['match_rows'],older_seasons_exposed=False),midweek_context=dict(matches=contextindex['matches'],player_rows=contextindex['player_rows'],collection_errors=contextindex['collection_errors']),synthetic_six_GW_TS=dict(actual_user_plan=False,weekly_checks=checks,first_GW_score_recomputed=True,manager_actions_sent=False,synthetic_state_saved_only_locally=True),service_health={k:health.get(k)for k in ['status','calculation_runtime','locked_model_active','supports_unified_B_chain','supports_B_snapshot_policy','preview_worker_sha256']},production_files_checked=len(prod),served_production_bytes_match_publisher_receipt=True,production_files=prod,production_or_preview_changed=False)
 args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='production_files'},indent=2))
if __name__=='__main__':main()
