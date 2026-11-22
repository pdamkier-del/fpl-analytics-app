"""Apply NEW PM dictionary/missingness contracts to existing archived containers.

No CS/DC/save/BPS efficacy audit, old decomposition, model, fit or simulation is
rerun. Prior study receipts are imported with provenance and labelled as such.
"""
import argparse,csv,gzip,hashlib,json,time
from collections import Counter,defaultdict
from functools import lru_cache
from pathlib import Path
from contracts import CAT,BASE,canonical_total,validate_ledger,validate_forecast_clock,ContractError
S=Path(__file__).resolve().parents[1];ROOT=S.parents[1];A=ROOT/'analysis/audits/2026-11-22/inputs/archive';OUT=ROOT/'research/results/EXP-PM-DEFS-001'
@lru_cache(None)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 raw=p.read_bytes();return json.loads(gzip.decompress(raw)if p.suffix=='.gz'else raw)
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def run(out):
 start=time.perf_counter();manifest=load(S/'implementation-manifest.json')
 for path,h in manifest['files'].items():assert digest(ROOT/path)==h,('Definition/harness/input changed',path)
 for item in load(S/'evidence/local-sources.json'):assert digest(ROOT/item['path'])==item['sha256']
 # Match the saved machine-readable point weights, not an assumed current rule.
 boot=load(A/'bootstrap.json.gz');scoring=boot['game_config']['scoring'];rule=CAT['rulebooks']['2026-27'];posmap={1:'GK',2:'DEF',3:'MID',4:'FWD'}
 for pos in ['GK','DEF','MID','FWD']:
  key='GKP'if pos=='GK'else pos;assert scoring['goals_scored'][key]==rule['goal_points'][pos];assert scoring['clean_sheets'][key]==rule['cs_points'][pos]
 assert scoring['bps']==0 and scoring['penalties_saved']==rule['penalty_save_points']and scoring['assists']==3
 report=load(A/'report.json.gz');official_stats=defaultdict(Counter);forecast_fields=Counter();draw_fields=Counter();bygw=[];failures=[];checks=Counter();identifiers=Counter();examples=[]
 for gw in [8,9,10]:
  f=load(A/f'gw{gw}-forecast.json.gz');raw=load(A/f'gw{gw}-live.json.gz');index=load(A/f'gw{gw}-index.json.gz');docs=load(A/f'gw{gw}-existing-app-data.json.gz');catalog={p['id']:p for p in docs['documents']['current-players.json']['players']};live={p['id']:p for p in raw['elements']};receipt=next(w for w in report['weeks']if w['gw']==gw);event=next(e for e in boot['events']if e['id']==gw)
  assert event['finished']and event['data_checked'];validate_forecast_clock(f['data_asof'],receipt['published_at'],f['origin_deadline']);checks['original_vintage_containers']+=1
  assert f['forecast_sha256']==index['forecast_sha256']==receipt['forecast_sha256']
  assert hashlib.sha256(gzip.decompress((A/f'gw{gw}-forecast.json.gz').read_bytes())).hexdigest()==index['forecast_file_sha256']
  rawkeys=set().union(*(p['stats'].keys()for p in raw['elements']))
  for field in rawkeys:
   for p in raw['elements']:
    c=official_stats[field];c['rows']+=1;c['present']+=field in p['stats'];c['non_null']+=p['stats'].get(field)is not None;c['zero']+=field in p['stats']and p['stats'][field]==0
  matched=0;extra=set(live)-{p['id']for p in f['players']}
  for p in f['players']:
   w=next(w for w in p['weeks']if w['gw']==gw);a=live[p['id']];matched+=1
   for name in w.get('scenarios',{}):draw_fields[name]+=1
   for fx in w['fixtures']:
    checks['matched_forecast_fixture_rows']+=1;components=fx['components'];forecast_fields.update(components.keys());values={('bonus_points'if k=='expected_bonus'else k):v for k,v in components.items()}
    try:
     diagnostics=dict(values)
     if fx.get('penalty_miss_points_subset_of_negative')is not None:
      diagnostics['penalty_miss_points']=fx['penalty_miss_points_subset_of_negative'];checks['penalty_miss_subset_checks']+=1
     split=fx.get('penalty',{})
     if all(split.get(k)is not None for k in ['expected_nonpenalty_goals','expected_penalty_goals']):
      coefficient=rule['goal_points'][posmap[p['position']]]
      diagnostics['nonpenalty_goal_points']=coefficient*split['expected_nonpenalty_goals'];diagnostics['penalty_goal_points']=coefficient*split['expected_penalty_goals'];checks['goal_origin_partition_checks']+=1
     else:checks['goal_origin_split_unknown']+=1
     expected=canonical_total(diagnostics)
     if abs(expected-fx['xpts'])>1e-8:raise ContractError('Canonical partition does not conserve archived xP')
     checks['forecast_partition_matches']+=1
     fixture=int(fx['fixture_uuid'].rsplit('-',1)[1]);row=dict(catalog_id=CAT['catalog_id'],season=f['season'],gw=gw,fixture_id=fixture,player_code=catalog[p['id']]['code'],fpl_position_at_deadline=posmap[p['position']],rulebook=rule['id'],source_sha256=digest(A/f'gw{gw}-forecast.json.gz'),mode='forecast',fields={k:dict(status='known',unit='fpl_points',value=v)for k,v in values.items()});validate_ledger(row);checks['forecast_ledger_matches']+=1
     label=next(e for e in a['explain']if e['fixture']==fixture)
     mapping={'minutes':'appearance_points','goals_scored':'goal_points','assists':'assist_points','clean_sheets':'cs_points','goals_conceded':'gc_points','saves':'save_points','penalties_saved':'penalty_save_points','defensive_contribution':'dc_points','bonus':'bonus_points','yellow_cards':'negative_points','red_cards':'negative_points','own_goals':'negative_points','penalties_missed':'negative_points'}
     # Explicit closed-world adapter: finalized complete official explain list
     # lists point awards, including nonzero ones. This is NOT zero-imputing
     # missing event subtypes or incomplete provider fields.
     actual={k:0 for k in BASE}
     for item in label['stats']:
      if item['identifier']not in mapping:raise ContractError('Unmapped official point-award identifier')
      if item.get('points_modification',0)!=0:raise ContractError('Modified labels require an explicit revision adapter')
      actual[mapping[item['identifier']]]+=item['points'];identifiers[item['identifier']]+=1
     if len(a['explain'])!=1:raise ContractError('Archived compatibility path is single-fixture; DGW needs independent fixture labels')
     if canonical_total(actual)!=a['stats']['total_points']:raise ContractError('Official complete point partition does not conserve total')
     row.update(mode='actual',source_sha256=digest(A/f'gw{gw}-live.json.gz'),fields={k:dict(status='known',unit='fpl_points',value=v)for k,v in actual.items()});validate_ledger(row);checks['actual_ledger_matches']+=1
     if len(examples)<2:examples.append(row)
    except (ContractError,KeyError,StopIteration,ValueError)as e:failures.append(dict(gw=gw,player_id=p['id'],fixture=fx['fixture_uuid'],error=str(e)))
  bygw.append(dict(gw=gw,forecast_players=len(f['players']),official_player_rows=len(raw['elements']),matched=matched,official_only_not_scored=len(extra),final_labels=True,original_issue=f['forecast_sha256'],cutoff=f['data_asof'],published_at=receipt['published_at'],deadline=f['origin_deadline']))
 prior32=load(S/'evidence/summary-scope.json');coverage32=list(csv.DictReader((S/'evidence/label-coverage.csv').open()));keeper=load(A/'raw-keeper-results.json.gz');cs=load(ROOT/'analysis/followup-41-20261122/results/pm-decomposition.json')['clean_sheets'];oldrules=load(ROOT/'analysis/audits/2026-11-22/results/scoring-rule-verification.json')
 imported=dict(status='prior_study_receipts_only_not_recomputed',PR32=dict(fixtures=prior32['fixtures'],rows=prior32['player_fixture_rows'],label_coverage_rows=len(coverage32),cs_label=prior32['cs_label'],dc_2024=prior32['dc_2024'],bps_background=prior32['bps_background']),PR41=oldrules,PR42=dict(cs_supported_player_rows=cs['supported_player_rows'],cs_unsupported_player_rows=cs['unsupported_player_rows'],cs_team_bounds_rows=cs['team_rows_with_probability_bounds'],cs_team_rows_excluded=cs['team_rows_excluded']),keeper_availability=dict(scope='Previously verified raw-provider availability summary, not raw shot/event data shipped by this PR',provider_keeper_rows=keeper['linked_played_keeper_rows'],inside_rows=keeper['explicit_inside_box_rows'],strict_keeper_rows=keeper['fully_reconciled_inside_box_rows'],xgot_rows=keeper['explicit_xgot_rows'],xgot_reconciled_rows=keeper['xgot_within_point03_rows'],big_chance_save_rows=keeper['big_chance_save_field_rows']))
 assert imported['PR32']['rows']==27092 and imported['PR42']['cs_team_bounds_rows']==57
 unknowns=[dict(target='ordinary_big_chance_saves',status='unavailable',basis='Keeper metadata0explicit fields; no xGOTthreshold surrogate'),dict(target='ordinary_inside_save_official_BPS_mapping',status='partial',basis='Provider141/133coverage is not a verified official Opta/FPL mapping or complete2026holdout'),dict(target='per_draw_background_BPS_and_event_covariance',status='not_archived',basis='Public scenario keys are total points/minutes; bonus means do not identify background'),dict(target='exact_player_CS_from_old_PR32',status='rule_derived_only',basis='No independent direct labels or sub-second/red-card-exit liability in those inputs'),dict(target='old_penalty_goal_origin',status='bounded',basis='PR32:2025scorers lack direct penalty-goal split; not borrowed from2026catalog'),dict(target='new_provider_rights',status='unverified',basis='No new provider acquired; public accessibility is not integration/redistribution permission'),dict(target='full_historical_rule_certification',status='partial',basis='Selected official2025changes and archived adapter are known; do not relabel all old targets as2026rules')]
 result=dict(experiment_id='EXP-PM-DEFS-001',catalog_id=CAT['catalog_id'],study_class='definition_and_coverage_contract_not_predictive_evaluation',scope='New source/container compatibility and schema tests only; prior performance/CS/DC/BPS studies not rerun',checks=dict(checks),failures=failures,rule_config_parity='all declared goal/CS position weights, PK-save/assist weights and BPSzero-direct-points agree with archived official game_config.scoring',by_gw=bygw,official_field_coverage={k:dict(v)for k,v in sorted(official_stats.items())},forecast_component_coverage=dict(sorted(forecast_fields.items())),archived_scenario_fields=dict(sorted(draw_fields.items())),official_award_identifier_occurrences=dict(sorted(identifiers.items())),prior_evidence=imported,unidentified=unknowns,example_fixture_ledgers=examples,fit_executed=False,simulation_executed=False,TS_executed=False,production_changed=False,elapsed_seconds=time.perf_counter()-start,status='completed'if not failures else'failed_contract')
 write(out/'coverage-and-contracts.json',result);print(json.dumps(dict(status=result['status'],checks=result['checks'],failures=len(failures),seconds=result['elapsed_seconds'])))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 if any(a.out.iterdir()):raise ValueError('Use a new result directory; never overwrite evidence')
 import sys;sys.path.insert(0,str(ROOT/'research/tools'));import registry
 registered=registry.read()['EXP-PM-DEFS-001'];assert registered['state']=='running'and registered['implementation']['harness_sha256']==digest(__file__)
 run(a.out)
