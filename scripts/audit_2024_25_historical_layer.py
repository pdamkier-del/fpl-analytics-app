"""Offline data preparation and audit ONLY. No model imports, fits or forecasts.
Final provider payloads are historical outcomes, never future schedules. Historical
publication is unknown: kickoff + 4h is an explicit research proxy, not a timestamp
certificate. Strict predeadline eligibility requires independently verified capture.
"""
from pathlib import Path
from collections import defaultdict, Counter
import csv, gzip, hashlib, json, math, unicodedata, uuid
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data_v1_1/raw/season_2024_25_v1'
OUT=ROOT/'data_v1_1/derived/season_2024_25_v1'
AUD=ROOT/'analysis/results/season-2024-25-data-audit-v1'

def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,float) and not math.isfinite(x):return None
 return x

def dump(path,x):path.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def rows(path):return [json.loads(s) for s in gzip.open(path,'rt')]
def write_rows(path,x):path.write_bytes(gzip.compress((''.join(json.dumps(clean(v),sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n' for v in x)).encode(),mtime=0))
def norm(x):return ''.join(c for c in unicodedata.normalize('NFKD',str(x)).casefold() if c.isalnum())
ALIASES={'manchestercity':'mancity','manchesterunited':'manutd','manunited':'manutd','nottinghamforest':'nottmforest','tottenhamhotspur':'spurs','tottenham':'spurs','brightonhovealbion':'brighton','brightonandhovealbion':'brighton','wolverhamptonwanderers':'wolves','newcastleunited':'newcastle','westhamunited':'westham','ipswichtown':'ipswich','leicestercity':'leicester','afcbournemouth':'bournemouth'}
def club(x):return ALIASES.get(norm(x),norm(x))
def unique(x):return next(iter(x)) if len(x)==1 else None

def asof(records,cutoff):
 """Exclude target/future/post-cutoff history. No implicit backfill."""
 cut=pd.Timestamp(cutoff)
 return [r for r in records if r.get('player_uuid') and pd.Timestamp(r['available_at_proxy'])<cut]

def main():
 manifest=json.loads((AUD/'source_manifest.json').read_text());bad=[]
 for s in manifest['sources']:
  b=(ROOT/s['path']).read_bytes()
  if hashlib.sha256(b).hexdigest()!=s['sha256']:bad.append(s['path'])
  if s.get('git_blob_sha') and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()!=s['git_blob_sha']:bad.append(s['path'])
 assert not bad,bad
 # Remove nonstandard NaN from captured Core exports, not from original raw bytes.
 for p in OUT.glob('*.jsonl.gz'):write_rows(p,rows(p))
 actual=pd.read_csv(OUT/'player_fixture_actuals.csv.gz');managers=actual.position.eq('AM')
 eligible=actual[~managers].copy();assert eligible.player_uuid.notna().all()
 assert not eligible.duplicated(['element','fixture']).any()
 eligible.to_csv(OUT/'eligible_player_fixture_actuals.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 gwcols=['total_points','minutes','starts','goals_scored','assists','clean_sheets','saves','bonus','bps','yellow_cards','red_cards','own_goals','penalties_missed','penalties_saved','expected_goals','expected_assists']
 pg=eligible.groupby(['gw','element','player_uuid'],as_index=False)[gwcols].sum(min_count=1)
 pg['quality']='EXACT_POSTMATCH';pg.to_csv(OUT/'player_gw_actuals.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 fixtures=pd.read_csv(OUT/'pl_fixture_actuals.csv');teams=pd.read_csv(RAW/'Vaastav/data/2024-25/teams.csv')
 team_names={int(r.id):club(r.name) for r in teams.itertuples()};plclubs=set(team_names.values())
 corefi={int(r['fpl_fixture_id']):r['fixture_uuid'] for r in rows(OUT/'existing_core_fixtures.jsonl.gz')}
 # Exact home/away/date tie, not season-end team or fuzzy name matching.
 fixture_keys={(team_names[int(r.team_h)],team_names[int(r.team_a)],pd.Timestamp(r.kickoff_time).isoformat()):int(r.id) for r in fixtures.itertuples()}
 ids=rows(OUT/'reference_player_identity_rows.jsonl.gz');opta=defaultdict(set)
 for r in ids:
  if r['id_namespace']=='opta_code':opta[str(r['external_id']).lstrip('p')].add(r['player_uuid'])
 names=defaultdict(set)
 identity=pd.read_csv(OUT/'player_identity.csv');byelement={int(r.fpl_element):r.player_uuid for r in identity.itertuples()}
 snapshots=rows(OUT/'deadline_player_candidates.jsonl.gz')
 for r in snapshots:
  if r['fpl_element'] in byelement:
   for k in ['player_name','web_name']:names[(norm(r[k]),club(r['team']))].add(byelement[r['fpl_element']])
 # Require FPL membership in this same PL fixture when using name/team resolution.
 members=defaultdict(set)
 for r in eligible.itertuples():members[(int(r.fixture),club(r.team))].add(r.player_uuid)
 matches=[];observations=[];provider_ids=defaultdict(set);mapping_rules={};role_rows=[]
 inventory={str(r['provider_match_id']):r['competition'] for r in json.loads((AUD/'fotmob_selected_inventory.json').read_text())}
 payloads=[]
 for p in sorted((RAW/'fotmob/details').glob('*.json')):
  j=json.loads(p.read_text());g=j['general'];mid=str(g['matchId']);ko=pd.Timestamp(g['matchTimeUTCDate']);h=club(g['homeTeam']['name']);a=club(g['awayTeam']['name'])
  assert g['finished'] and pd.Timestamp('2024-07-01',tz='UTC')<=ko<pd.Timestamp('2025-06-02',tz='UTC')
  comp=inventory.get(mid,'unknown');fplid=fixture_keys.get((h,a,ko.isoformat())) if comp=='prem' else None
  if comp=='prem':assert fplid is not None,(mid,h,a,ko)
  internal=corefi[fplid] if fplid else str(uuid.uuid5(uuid.NAMESPACE_URL,'fpl-analytics-app:2024-25:fotmob:'+mid))
  proxy=(ko+pd.Timedelta(hours=4)).isoformat()
  matches.append(dict(season='2024-25',match_id=internal,provider_match_id=mid,fpl_fixture_id=fplid,competition=comp,competition_name=g['leagueName'],round=g.get('matchRound'),stage=g.get('leagueRoundName'),kickoff=ko.isoformat(),home_team=g['homeTeam']['name'],away_team=g['awayTeam']['name'],home_provider_team_id=g['homeTeam']['id'],away_provider_team_id=g['awayTeam']['id'],result=j.get('header',{}).get('status',{}).get('scoreStr'),available_at_proxy=proxy,quality='EXACT_POSTMATCH',timing_quality='PROXY_CUTOFF_SAFE',future_schedule_forecast_eligible=False,source_url='https://www.fotmob.com/api/data/matchDetails?matchId='+mid))
  stats=j.get('content',{}).get('playerStats') or {};lineup=j.get('content',{}).get('lineup') or {}
  payloads.append((mid,internal,fplid,proxy,comp,j))
  for sid in ['homeTeam','awayTeam']:
   side=lineup.get(sid) or {};team=club(side.get('name',''))
   if team not in plclubs:continue
   for kind in ['starters','subs']:
    for player in side.get(kind,[]):
     pid=str(player['id']);stat=stats.get(pid,{})
     choices=opta.get(str(stat.get('optaId','')).lstrip('p'),set());rule='exact known Opta ID'
     if not choices and fplid:
      choices=names.get((norm(player['name']),team),set()) & members[(fplid,team)];rule='exact normalized name + team + same PL fixture'
     if len(choices)==1:provider_ids[pid].update(choices);mapping_rules[pid]=rule
 # A provider identity conflict is quarantined across all matches.
 unresolved=[];mapped_count=0
 for mid,internal,fplid,proxy,comp,j in payloads:
  stats=j.get('content',{}).get('playerStats') or {};lineup=j.get('content',{}).get('lineup') or {};g=j['general']
  for sid in ['homeTeam','awayTeam']:
   side=lineup.get(sid) or {};team=club(side.get('name',''))
   if team not in plclubs:continue
   for kind in ['starters','subs']:
    for slot,p in enumerate(side.get(kind,[])):
     pid=str(p['id']);stat=stats.get(pid,{})
     values={}
     for section in stat.get('stats',[]):
      for title,v in section.get('stats',{}).items():values[v.get('key',title)]=v.get('stat',{}).get('value')
     choices=provider_ids.get(pid,set());pu=unique(choices);state='mapped' if pu else 'ambiguous' if choices else 'unresolved'
     if pu:mapped_count+=1
     else:unresolved.append(dict(provider_player_id=pid,player_name=p['name'],team=side.get('name'),match_id=internal,status=state,competition=comp))
     r=dict(season='2024-25',provider='FotMob',provider_player_id=pid,opta_code=stat.get('optaId'),player_uuid=pu,player_name=p['name'],team=side.get('name'),provider_team_id=side.get('id'),match_id=internal,provider_match_id=mid,fpl_fixture_id=fplid,competition=comp,kickoff=g['matchTimeUTCDate'],available_at_proxy=proxy,publication_at=None,strict_forecast_eligible=False,quality='EXACT_POSTMATCH',timing_quality='PROXY_CUTOFF_SAFE',identity_status=state,identity_rule=mapping_rules.get(pid),started=kind=='starters',minutes=values.get('minutes_played'),rating=values.get('rating_title'),stats=values,source_url='https://www.fotmob.com/api/data/matchDetails?matchId='+mid)
     observations.append(r)
     if kind=='starters':role_rows.append(dict(**{k:r[k] for k in ['player_uuid','provider_player_id','player_name','team','match_id','provider_match_id','competition','available_at_proxy','quality','timing_quality','identity_status']},formation=side.get('formation'),lineup_slot=slot,lineup_slot_basis='provider starter array index, zero based; not classified',position_id=p.get('positionId'),usual_position_id=p.get('usualPlayingPositionId'),horizontal_layout=p.get('horizontalLayout'),vertical_layout=p.get('verticalLayout'),average_position=None,average_position_quality='UNAVAILABLE',formation_changes=None,final_role=None))
 assert len({r['match_id'] for r in matches})==len(matches)
 assert len({(r['provider_player_id'],r['match_id']) for r in observations})==len(observations)
 assert all(pd.Timestamp(r['available_at_proxy'])>pd.Timestamp(r['kickoff']) for r in observations)
 write_rows(OUT/'all_competition_match_actuals.jsonl.gz',matches);write_rows(OUT/'all_competition_player_observations.jsonl.gz',observations);write_rows(OUT/'raw_role_inputs.jsonl.gz',role_rows)
 write_rows(OUT/'unresolved_provider_identities.jsonl.gz',unresolved)
 ratings=[dict(provider=r['provider'],player_uuid=r['player_uuid'],match_id=r['match_id'],available_at=r['available_at_proxy'],rating=r['rating'],provider_player_id=r['provider_player_id'],player_name=r['player_name'],team=r['team'],competition=r['competition'],kickoff=r['kickoff'],minutes=r['minutes'],timing_quality=r['timing_quality'],strict_forecast_eligible=False) for r in observations if r['player_uuid'] and r['rating'] is not None]
 assert all(0<=float(r['rating'])<=10 for r in ratings)
 assert len({(r['provider'],r['player_uuid'],r['match_id']) for r in ratings})==len(ratings)
 pd.DataFrame(ratings).to_csv(OUT/'player_match_ratings.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 mapping=[dict(provider='FotMob',provider_player_id=k,player_uuid=unique(v),status='mapped' if len(v)==1 else 'ambiguous',rule=mapping_rules.get(k)) for k,v in sorted(provider_ids.items())]
 dump(OUT/'provider_identity_mapping.json',mapping)
 # Strict states stay UNKNOWN for all uncertified candidate payloads.
 write_rows(OUT/'availability_candidates.jsonl.gz',[dict(r,player_uuid=byelement.get(r['fpl_element']),normalized_availability_state='UNKNOWN' if not r['timing_verified'] else {'a':'AVAILABLE','d':'DOUBT','i':'OUT','s':'SUSPENDED','u':'OUT'}.get(r.get('status'),'UNKNOWN')) for r in snapshots])
 deadlines=json.loads((OUT/'deadlines.json').read_text());coverage=[]
 for d in deadlines:
  gw=d['gw'];cut=pd.Timestamp(d['cutoff']);ps=[r for r in snapshots if r['gw']==gw];e=eligible[eligible.gw==gw];fx=fixtures[fixtures.event==gw];prior=asof(observations,cut)
  c=Counter(list(fx.team_h)+list(fx.team_a));rated=[r for r in prior if r['rating'] is not None]
  coverage.append(dict(gw=gw,cutoff=d['cutoff'],actual_fixtures=len(fx),player_fixture_actuals=len(e),actual_players=e.element.nunique(),mapped_actual_rows=int(e.player_uuid.notna().sum()),dgw_teams=sum(v>1 for v in c.values()),bgw_teams=20-len(c),candidate_snapshot_players=len(ps),exact_predeadline_players=sum(r['timing_verified'] for r in ps),unverified_snapshot_excluded=sum(not r['timing_verified'] for r in ps),strict_carry_forward=0,strict_availability='UNAVAILABLE',prior_player_observations_proxy=len(prior),prior_players_proxy=len({r['player_uuid'] for r in prior}),prior_ratings_proxy=len(rated),prior_matches_proxy=len({r['match_id'] for r in prior}),future_schedule_quality='UNAVAILABLE',average_position_quality='UNAVAILABLE'))
 pd.DataFrame(coverage).to_csv(AUD/'coverage_by_gw.csv',index=False)
 field_gw=[]
 for c in coverage:
  e=eligible[eligible.gw==c['gw']]
  for f in gwcols:
   field_gw.append(dict(gw=c['gw'],cutoff=c['cutoff'],component='FPL/PM targets',field=f,quality='EXACT_POSTMATCH',non_null_rows=int(e[f].notna().sum()),total_rows=len(e),forecast_use='after match only'))
  for component,field,count,quality in [('MM','prior player events',c['prior_player_observations_proxy'],'PROXY_CUTOFF_SAFE'),('MM','prior ratings',c['prior_ratings_proxy'],'PROXY_CUTOFF_SAFE'),('MM','average position',0,'UNAVAILABLE'),('TS','deadline price/cohort/team/position',c['exact_predeadline_players'],'UNAVAILABLE' if not c['exact_predeadline_players'] else 'EXACT_PREDEADLINE'),('MM','availability',c['exact_predeadline_players'],'UNAVAILABLE' if not c['exact_predeadline_players'] else 'EXACT_PREDEADLINE'),('MI/TS','historical future schedule',0,'UNAVAILABLE')]:
   field_gw.append(dict(gw=c['gw'],cutoff=c['cutoff'],component=component,field=field,quality=quality,non_null_rows=count,total_rows=c['candidate_snapshot_players'],forecast_use='conditional proxy history only' if quality=='PROXY_CUTOFF_SAFE' else 'strict missing' if quality=='UNAVAILABLE' else 'predeadline'))
 pd.DataFrame(field_gw).to_csv(AUD/'coverage_by_gw_component.csv',index=False)
 components=[]
 def field(component,fields,quality,n,note):components.append(dict(component=component,fields=fields,quality=quality,rows=n,note=note))
 field('FPL outcomes','points, minutes, starts, goals, assists, clean_sheets, saves, bonus, BPS, cards, own_goals, penalties, xG, xA','EXACT_POSTMATCH',len(eligible),'Only usable after relevant match. DGW rows remain per-fixture; aggregate in player_gw_actuals.')
 field('Identity','season FPL element, stable code, player_uuid','RECONSTRUCTED_CUTOFF_SAFE',len(identity),'Identity only; no end-season team/price/availability fed back.')
 field('Deadline','GW deadline','RECONSTRUCTED_CUTOFF_SAFE',38,'Official API event values preserved in archived season payload; not a certificate of historical revisions.')
 field('TS/availability','deadline price, team, position, cohort, status, news, news_added, chances','UNAVAILABLE',len(snapshots),'38 raw candidate snapshots preserved; historical capture timing lacks independent server proof. Candidate clocks may support conditional sensitivity analysis only.')
 field('MM workload','kickoff, competition, round/stage, result','EXACT_POSTMATCH',len(matches),'Final inventories cannot reconstruct future draws or schedules.')
 field('MM role','formation, provider lineup slot, layout, starts','EXACT_POSTMATCH',len(role_rows),'Layout is planned formation geometry, NOT measured average position; no q/H calculation or classifier changes.')
 field('MM role','average position, formation changes, prior-season role bootstrap','UNAVAILABLE',0,'No measured average-position field found in captured provider payloads; cannot claim classifier parity.')
 field('PM events','raw FotMob xG/xA/shots/SOT, defensive events, keeper saves, penalties','EXACT_POSTMATCH',len(observations),'Original key-value stats retained; missing values stay null, provider xA is not replaced by FPL expected assists.')
 field('MM ratings','rating 0-10','EXACT_POSTMATCH',len(ratings),'Original FotMob scale retained.')
 field('History timing','available_at_proxy kickoff + 4h','PROXY_CUTOFF_SAFE',len(observations),'Conservative regulation/extra-time buffer; unknown publication/revision timestamps. Not exact real-time vintage. Core kickoff + 3h remains separately retained.')
 field('MI/TS schedule','predeadline future fixture/DGW/BGW and cup draw knowledge','UNAVAILABLE',0,'Final schedules explicitly forecast-ineligible; actual DGW/BGW counts are outcomes only.')
 field('PM scoring','2024 defensive contribution FPL points','UNAVAILABLE',0,'Not part of 2024/25 FPL scoring. Never synthesize 2025/26 points for the 2024 actual target.')
 field('Cold start','GW1-5 prior-season contextual inputs','UNAVAILABLE',0,'2023/24 raw role/workload layer outside this collection; same rule must be supplied historical inputs.')
 pd.DataFrame(components).to_csv(AUD/'coverage_by_component.csv',index=False)
 stats_fields=Counter(k for r in observations for k,v in r['stats'].items() if v is not None)
 dump(AUD/'provider_stat_field_coverage.json',dict(total_player_rows=len(observations),non_null_by_provider_key=stats_fields))
 comp=Counter(r['competition'] for r in matches);bycomp={k:dict(matches=v,player_rows=sum(r['competition']==k for r in observations),mapped_rows=sum(r['competition']==k and r['player_uuid'] is not None for r in observations),ratings=sum(r['competition']==k for r in ratings),formation_rows=sum(r['competition']==k and bool(r['formation']) for r in role_rows)) for k,v in sorted(comp.items())}
 dump(AUD/'coverage_by_competition.json',bycomp)
 dump(AUD/'coverage_by_team.json',{t:dict(player_rows=sum(r['team']==t for r in observations),mapped_rows=sum(r['team']==t and r['player_uuid'] is not None for r in observations),ratings=sum(r['team']==t for r in ratings)) for t in sorted({r['team'] for r in observations})})
 dump(AUD/'identity_audit.json',dict(fpl_players=len(identity),fpl_mapped=int(identity.status.eq('mapped').sum()),fpl_unresolved=int(identity.status.eq('unresolved').sum()),fpl_ambiguous=int(identity.status.eq('ambiguous').sum()),assistant_manager_rows_excluded=int(managers.sum()),provider_player_rows=len(observations),provider_mapped_rows=mapped_count,provider_unresolved_rows=sum(r['status']=='unresolved' for r in unresolved),provider_ambiguous_rows=sum(r['status']=='ambiguous' for r in unresolved),provider_unresolved_unique=len({r['provider_player_id'] for r in unresolved}),duplicate_fpl_player_fixture_rows=0,duplicate_rating_rows=0,forced_fuzzy_matches=0))
 dump(AUD/'leakage_audit.json',dict(raw_checksum_failures=bad,verified_raw_files=len(manifest['sources']),strict_snapshot_eligible_rows=sum(r['timing_verified'] for r in snapshots),unverified_snapshot_rows_quarantined=sum(not r['timing_verified'] for r in snapshots),publication_time_known_rows=0,observations_available_not_after_kickoff=sum(pd.Timestamp(r['available_at_proxy'])<=pd.Timestamp(r['kickoff']) for r in observations),rating_out_of_range=0,final_future_schedule_eligible_rows=0,model_executed=False,model_math_changed=False,training_overlap={'confirmed':'reproduce_pstart_v2_fixture_minutes.py trains on 2023-24 + 2024-25, holds out 2025-26','implication':'2024/25 is not an independent unseen baseline season','other_locked_fits':'requires complete training provenance review; no extrapolation from baseline evidence'},conditional_proxy_only=True,notes=['observed_at in old Core is 2026 ingestion, not historical publication','news_added timestamps a news change, not validity of entire later snapshot','A future direct API revision can alter an old match rating/stat; no revision vintage is available','All strict data missing stays missing; zero target leakage is not a claim of full historical usability']))
 blockers=['Unverified historical capture clocks for all 38 bootstrap candidates: strict deadline price/cohort/availability missing.','Historical future schedule/draw versions are absent; final cup/PL inventory is outcome-only.','Measured average positions and prior-season role bootstrap unavailable; full q/H classifier parity not established.','Locked runner season queries/paths and cold-start input artifacts are hardcoded to 2025/26; a data-only season adapter is not yet implemented.','Confirmed 2024/25 training overlap in baseline builder prevents describing this as an independent unseen-season test.','2024/25 point scoring differs: defensive contribution points introduced in 2025/26. Model was not changed.','Provider historical publication/revision times unavailable; kickoff + 4h is explicitly conditional proxy.']
 dump(AUD/'readiness.json',dict(status='NOT_READY',purpose='Strict unchanged independent locked 2024/25 replay',blockers=blockers,collected_data_usable_for='Outcome evaluation and explicitly conditional historical-history experiments; no replay run',official_competitions=bycomp,ratings=len(ratings),role_rows=len(role_rows),eligible_fpl_rows=len(eligible),player_gw_rows=len(pg),cutoff_gws=38))
 # Exact hashes of all prepared input files, avoiding a self-referential manifest.
 dump(AUD/'checkpoint_summary.json',dict(raw_source_files=len(manifest['sources']),provider_matches=len(matches),provider_player_rows=len(observations),mapped_provider_rows=mapped_count,ratings=len(ratings),role_input_rows=len(role_rows),fpl_fixture_rows=len(eligible),fpl_player_gw_rows=len(pg),verified_predeadline_gws=sum(any(r['timing_verified'] for r in snapshots if r['gw']==d['gw']) for d in deadlines),models_unchanged=True))
 dump(AUD/'prepared_manifest.json',[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(OUT.glob('*')) if p.is_file()])
 print(json.dumps(json.loads((AUD/'readiness.json').read_text()),indent=2))

if __name__=='__main__':main()
