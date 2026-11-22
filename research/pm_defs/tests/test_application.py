from pathlib import Path
import json,gzip,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[3];S=ROOT/'research/pm_defs';O=ROOT/'research/results/EXP-PM-DEFS-001'
def test_catalog_schema_and_source_refs_resolve():
 c=json.loads((S/'catalog.v1.json').read_text());schema=json.loads((S/'ledger.schema.v1.json').read_text());assert schema['properties']['catalog_id']['const']==c['catalog_id']
 refs={r['id']for r in json.loads((S/'evidence/rule-sources.json').read_text())}|{r['id']for r in json.loads((S/'evidence/local-sources.json').read_text())}
 assert all(set(x['rule_sources'])<=refs for x in c['components'])
 assert 'source_sha256'in schema['required']and schema['additionalProperties']is False

def test_full_declared_point_coefficients_match_archived_official_config():
 b=json.loads(gzip.decompress((ROOT/'analysis/audits/2026-11-22/inputs/archive/bootstrap.json.gz').read_bytes()));s=b['game_config']['scoring'];c=json.loads((S/'catalog.v1.json').read_text())['rulebooks']['2026-27'];p=c['point_constants']
 assert s['short_play']==p['appearance_positive_lt60']and s['long_play']==p['appearance_at_least60']
 for k,field in [('yellow_cards','yellow'),('red_cards','red_normalized'),('own_goals','own_goal'),('penalties_missed','penalty_miss'),('assists','assist')]:assert s[k]==p[field]
 assert s['saves']==1 and s['penalties_saved']==c['penalty_save_points']and s['bps']==0
 for pos in ['GKP','DEF','MID','FWD']:
  key='GK'if pos=='GKP'else pos;assert s['goals_scored'][pos]==c['goal_points'][key]and s['clean_sheets'][pos]==c['cs_points'][key]
  assert s['goals_conceded'][pos]==(-1 if pos in ['GKP','DEF']else 0)
  assert s['defensive_contribution'][pos]==(0 if pos=='GKP'else 2)
 # BPS60-minute boundary is deliberately distinct from FPLappearance/CS60+.
 assert c['bps']['appearance_1_to_60']==3 and c['bps']['appearance_over_60']==6

def test_application_keeps_prior_results_distinct_and_all_unknowns_explicit():
 r=json.loads((O/'contract-run-v2/coverage-and-contracts.json').read_text());assert r['status']=='completed'and not r['failures']
 assert r['checks']['forecast_ledger_matches']==r['checks']['actual_ledger_matches']==2007
 assert sum(g['official_player_rows']for g in r['by_gw'])==2011
 assert sum(g['official_only_not_scored']for g in r['by_gw'])==4
 assert r['prior_evidence']['status'].startswith('prior_study_receipts_only')
 assert r['prior_evidence']['PR32']['rows']==27092 and r['prior_evidence']['keeper_availability']['big_chance_save_rows']==0
 assert r['archived_scenario_fields']=={'minutes':2007,'points':2007}
 assert not(r['TS_executed']or r['fit_executed']or r['simulation_executed']or r['production_changed'])

def test_frozen_catalog_inputs_unchanged_and_checksum_helper_handles_entrypoint():
 manifest=json.loads((S/'implementation-manifest.v2.json').read_text())
 for path,h in manifest['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
 spec=importlib.util.spec_from_file_location('pm_defs_v2_checksum',S/'code/run_contract_audit_v2.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.digest(str(S/'catalog.v1.json'))==m.digest(S/'catalog.v1.json')
