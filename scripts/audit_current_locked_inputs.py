"""Materialize current source inputs using frozen role/workload components.
Never certifies a forecast merely because data collection or unit tests pass.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.role_classifier import classify_lineup,ROLES,template
from fpl_v1_1_model.role_history import RoleHistory,summarize_state
from fpl_v1_1_model.workload import WorkloadHistory
from fpl_v1_1_model.match_importance import BASE_COMPETITION_VALUES,canonical_competition,premier_league_stage_strength,knockout_stage_strength,opponent_strength_from_elo
from fpl_v1_1_model.pstart_v2 import match_importance
from fpl_v1_1_model.rating_history import validate_rating_ledger,build_rating_features
from fpl_v1_1_model.team_news_history import build_strict_team_news_features
from run_mm_v2_team_news_availability_experiment import policy_caps
from run_mm_unified_official_roles import compose
from fpl_v1_1_model.archived_current_season_cohorts import load_archived_rosters
from live_historical_membership import recover_zero_club
WORK=ROOT/'work/live-final-model';OUT=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
def readjl(p):return [json.loads(r) for r in gzip.decompress(p.read_bytes()).splitlines()]
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvgz(p,f):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(f.to_csv(index=False).encode(),mtime=0))
def materialize(horizon_end=None):
 OUT.mkdir(parents=True,exist_ok=True)
 bootstrap=json.loads((WORK/'bootstrap.json').read_text());fx=json.loads((WORK/'fixtures.json').read_text());ident=json.loads((WORK/'current_identity.json').read_text());asof=datetime.fromisoformat(json.loads((WORK/'source_manifest.json').read_text())['observed_at'].replace('Z','+00:00'));gw=next(e['id'] for e in bootstrap['events'] if e.get('is_next'));people={p['id']:p for p in bootstrap['elements'] if p['element_type']!=5};ids={p['fpl_element']:p for p in ident};teams={t['code']:t['id'] for t in bootstrap['teams']};team_names={t['id']:t['name'] for t in bootstrap['teams']}
 games=readjl(WORK/'match_actuals.jsonl.gz');events=readjl(WORK/'player_match_events.jsonl.gz');gmap={g['match_id']:g for g in games};emap={(r['match_id'],r['player_id']):r for r in events};line=pd.read_csv(ROOT/'data_v1_1/raw/all-competitions-2026-27/lineups.csv');rh=RoleHistory();wh=WorkloadHistory();classified=[];skipped=[];active=defaultdict(lambda:{'prem','fa-cup','efl-cup'})
 for g in games:
  for c in (g['home_team'],g['away_team']):
   if c in teams:active[teams[c]].add(canonical_competition(g['tournament']))
 for g in sorted(games,key=lambda g:(g['available_at'],g['match_id'])):
  mid=g['match_id'];known=pd.Timestamp(g['available_at']);ko=pd.Timestamp(g['kickoff_time']);comp=canonical_competition(g['tournament'])
  for side in ('home','away'):
   code=g[side+'_team'];tid=teams.get(code)
   if tid is None:continue
   group=line[(line.match_id==mid)&(line.team_side==side)];starters=group[group.is_starting.astype(str).str.lower().isin(['true','1'])].sort_values('lineup_slot')
   obs={str(r['player_uuid']):dict(minutes=float(r['minutes_played']),started=bool(r['started'])) for r in events if r['match_id']==mid and r['team_id']==tid and r.get('player_uuid') and r.get('minutes_played') is not None}
   wh.add_game(tid,mid,ko,known,'prem' if comp=='prem' else comp,obs,player_stats_complete=len(obs)>=11)
   formation=str(starters.formation.iloc[0]) if len(starters) else ''
   if len(starters)!=11 or starters.player_uuid.isna().any() or not template(formation):skipped.append(dict(match_id=mid,team_id=tid,reason='No complete mapped confirmed eleven and formation'));continue
   rows=[dict(player_uuid=str(r.player_uuid),slot=int(r.lineup_slot),position='G' if int(r.lineup_slot)==1 else str(r.position)) for r in starters.itertuples()]
   prior,_,_=rh.state(tid,ko,10,q_importance_scale=.1,h_importance_scale=.4,importance_floor=.35)
   roles=classify_lineup(formation,rows,{},prior)
   stage=premier_league_stage_strength(int(g['gameweek'])) if comp=='prem' else knockout_stage_strength(g.get('round_name'),ko.month)
   mi=match_importance(competition=comp,active_competitions=sorted(active[tid]),round_strength=stage,opponent_strength=opponent_strength_from_elo(None),base_values=BASE_COMPETITION_VALUES)
   players=[]
   for r in starters.itertuples():
    e=emap.get((mid,int(r.player_id)));z=roles[str(r.player_uuid)]
    if not e or e['minutes_played'] is None:break
    players.append(dict(player_uuid=str(r.player_uuid),role=z['final_role'],started=True,minutes=float(e['minutes_played']),disagreement=False))
    classified.append(dict(match_id=mid,team_id=tid,player_uuid=str(r.player_uuid),player=r.player_name,formation=formation,lineup_slot=int(r.lineup_slot),available_at=g['available_at'],importance=mi,**{k:v for k,v in z.items() if k!='prior_q'}))
   if len(players)==11:rh.add_game(tid,known,mid,players,importance=mi,competition=comp)
   else:skipped.append(dict(match_id=mid,team_id=tid,reason='Missing observed starter minutes'))
 if horizon_end is None:horizon_end=min(38,gw+5)
 if not gw<=horizon_end<=38:raise ValueError('Invalid forecast horizon')
 # One common forecast origin; future deadlines are not permission to read later outcomes.
 targets=[]
 for f in fx:
  if not (f.get('event') and gw<=f['event']<=horizon_end and not f.get('finished') and f.get('kickoff_time')):continue
  for home in (True,False):
   tid=f['team_h'] if home else f['team_a'];opp=f['team_a'] if home else f['team_h'];rs={speed:rh.state(tid,pd.Timestamp(asof),half,q_importance_scale=.1,h_importance_scale=.4,importance_floor=.35) for speed,half in [('fast',3),('slow',10)]};ws,default,last=wh.state(tid,asof)
   for fid,p in people.items():
    if p['team']!=tid:continue
    uid=ids[fid]['player_uuid']
    if not uid:continue
    r=dict(season='2026-27',gw=gw,target_gw=f['event'],fixture_uuid=f"live-2026-27-fpl-{f['id']}",fpl_fixture_id=f['id'],player_uuid=uid,fpl_element=fid,player=p['web_name'],team_id=tid,opponent_team_id=opp,team=team_names[tid],pos={1:'GK',2:'DEF',3:'MID',4:'FWD'}[p['element_type']],cutoff=asof.isoformat(),target_kickoff=f['kickoff_time'],was_home=home,roster_observed_at=json.loads((WORK/'source_manifest.json').read_text())['observed_at'],actual_start=None,actual_minutes=None)
    for speed in ('fast','slow'):
     states,caps,hist=rs[speed];state=states.get(uid,{})
     for k,v in summarize_state(state,caps).items():
      if k.startswith('role_'):r[k+'_'+speed]=v
     for fld in ('q','H'):
      for role in ROLES:r[f'{fld}_{role}_{speed}']=state.get(fld,{}).get(role,0.)
     if speed=='slow':
      q=state.get('q',{});r['expected_role']=max(sorted(q),key=q.get) if q else 'UNKNOWN';r['role_started_last_gw']=float(bool(hist and any(v['player_uuid']==uid and v['started'] for v in hist[-1]['players'])));r['max_history_known_at']=str(hist[-1]['known_at']) if hist else None
    r.update(ws.get(uid,default));targets.append(r)
 frame=pd.DataFrame(targets);ratings=validate_rating_ledger(pd.read_csv(ROOT/'data_v1_1/derived/mm_v2_ratings/player_match_ratings_2026_27.csv.gz'));frame=build_rating_features(frame,ratings);strict=pd.DataFrame(readjl(ROOT/'data_v1_1/derived/team_news_audit/2026-27-v2/predeadline_strict.jsonl.gz'));frame=build_strict_team_news_features(frame,strict)
 assert not frame.duplicated(['fixture_uuid','player_uuid']).any()
 assert all(pd.Timestamp(g['available_at'])<pd.Timestamp(asof) for g in games)
 csvgz(OUT/'source_feature_matrix.csv.gz',frame);csvgz(OUT/'classified_starters.csv.gz',pd.DataFrame(classified));dump(OUT/'current_identity.json',ident)
 # Event data for PM preserves observed values, including true zero outcomes.
 base=max((ROOT/'data_v1_1/raw/live-captures').iterdir());flookup={f['id']:f for f in fx};actual=[];unresolved=[];recovered=[]
 archive_dir=WORK/'predeadline_2026_archives';archived=load_archived_rosters(archive_dir,expected_gws=sorted(int(p.stem[2:]) for p in archive_dir.glob('gw*.json')))[0] if (archive_dir/'archive_manifest.json').exists() else {}
 for p in sorted((base/'fpl').glob('gw*.json')):
  n=int(p.stem[2:]);j=json.loads(p.read_text())
  for row in j['elements']:
   fid=row['id'];matchids=[x['fixture'] for x in row.get('explain',[])];who=ids.get(fid)
   if not who or not who.get('player_uuid'):unresolved.append(dict(gw=n,fpl_element=fid,reason='No stable identity'));continue
   if len(matchids)!=1:unresolved.append(dict(gw=n,fpl_element=fid,reason='Missing/split fixture statistics; preserve raw'));continue
   f=flookup[matchids[0]];tid=people[fid]['team']
   historical_team={r['team_id'] for r in events if r['player_id']==fid and gmap[r['match_id']]['gameweek']==n and gmap[r['match_id']]['kickoff_time']==pd.Timestamp(f['kickoff_time']).isoformat()}
   if len(historical_team)==1:tid=next(iter(historical_team))
   elif not historical_team:
    snapshot=archived.get(n,{}).get(fid);recovered_team=recover_zero_club(snapshot,who,row['stats'],f)
    if recovered_team is not None and recovered_team!=tid:
     recovered.append(dict(gw=n,fpl_element=fid,player_uuid=who['player_uuid'],fixture=f['id'],current_team=tid,historical_team=recovered_team,source=str(p.relative_to(ROOT)),minutes=row['stats']['minutes'],starts=row['stats']['starts']))
     tid=recovered_team
   if tid not in (f['team_h'],f['team_a']):unresolved.append(dict(gw=n,fpl_element=fid,reason='Historical club differs from current roster'));continue
   st=row['stats'];known=pd.Timestamp(f['kickoff_time'])+pd.Timedelta(hours=4)
   actual.append(dict(season='2026-27',gw=n,fixture_uuid=f"historical-2026-27-fpl-{f['id']}",player_uuid=who['player_uuid'],fpl_element=fid,team_id=tid,opponent_team_id=f['team_a'] if tid==f['team_h'] else f['team_h'],was_home=tid==f['team_h'],kickoff_at=f['kickoff_time'],available_at=known.isoformat(),fpl_position={1:'GK',2:'DEF',3:'MID',4:'FWD'}[people[fid]['element_type']],minutes=st.get('minutes'),started=st.get('starts'),xg=st.get('expected_goals'),xa=st.get('expected_assists'),defcon_count=st.get('defensive_contribution'),yellow_cards=st.get('yellow_cards'),fpl_red_cards=st.get('red_cards'),own_goals=st.get('own_goals'),goals=st.get('goals_scored'),fpl_assists=st.get('assists'),saves=st.get('saves'),bps=st.get('bps'),total_points=st.get('total_points'),penalties_saved=st.get('penalties_saved'),penalties_missed=st.get('penalties_missed'),timing_quality='PROXY_CUTOFF_SAFE',membership_quality='RECONSTRUCTED_CUTOFF_SAFE'))
 csvgz(OUT/'player_fixture_observations.csv.gz',pd.DataFrame(actual));dump(WORK/'historical_zero_membership_recovery.json',dict(rows=len(recovered),records=recovered,zero_values_are_explicit_official_observations=True,no_model_changes=True))
 counts=frame.groupby('target_gw').agg(players=('fpl_element','nunique'),fixture_rows=('fpl_element','size'),unknown_role=('expected_role',lambda s:int((s=='UNKNOWN').sum())),known_news_at_origin=('team_news_known','sum')).reset_index()
 dump(OUT/'coverage_audit.json',dict(forecast_cutoff=asof.isoformat(),source_capture=json.loads((WORK/'source_manifest.json').read_text())['observed_at'],per_gw=counts.to_dict('records'),classified_starters=len(classified),role_sides_skipped=skipped,actual_player_fixture_rows=len(actual),actual_rows_by_gw=dict(Counter(r['gw'] for r in actual)),unresolved_historical_records=unresolved,average_position_quality='UNAVAILABLE; structural confirmed slots retained',future_news_scope='chance applies to origin GW only; no future-GW availability certification',ratings=len(ratings),duplicate_rating_rows=0,ratings_outside_scale=0,target_match_rating_rows=0,future_outcomes=0,model_math_changed=False))
 # An existing frozen contract conflict, proved through the existing functions.
 probe=pd.DataFrame(dict(team_news_state=['OUT','SUSPENDED'],team_news_scoped_chance=[0.,0.],start_minutes_mean=[80.,80.]))
 caps=policy_caps(probe,'soft_0.5_0.1');xm=compose(probe,np.zeros(2),np.full(2,.2),np.full(2,20.))
 assert (caps==0).all() and (xm>0).all()
 dump(OUT/'locked_contract_audit.json',dict(status='BLOCKED_LOCKED_AVAILABILITY_CONTRACT_CONFLICT',existing_functions=['run_mm_v2_team_news_availability_experiment.policy_caps','run_mm_unified_official_roles.compose'],states=probe.team_news_state.tolist(),p_start=[0.,0.],q_sub_given_not_start=[.2,.2],sub_minutes=[20.,20.],existing_formula_xmins=xm.tolist(),release_requires_xmins=[0.,0.],explanation='The locked runner caps start probability but leaves the substitute branch nonzero. MM release rejects OUT/SUSPENDED with positive xMins. No mathematical change was made.',live_forecast_certified=False))
 manifest=[]
 for p in sorted(OUT.iterdir()):
  if p.is_file():manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 dump(OUT/'manifest.json',dict(season='2026-27',files=manifest,classification='CURRENT_SOURCE_INPUTS_NOT_CERTIFIED_LOCKED_FORECAST'))
 print('CURRENT INPUT AUDIT',len(frame),'six-GW rows',len(actual),'actual rows; locked availability contract conflict remains')
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--horizon-end',type=int);a=ap.parse_args();materialize(a.horizon_end)
