from pathlib import Path
import gzip,hashlib,json,sys
import pandas as pd,pytest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'code'));from verify_inputs import verify

def test_rejects_mutated_archived_evidence(tmp_path):
 p=tmp_path/'data';p.write_bytes(b'old');entries=[{'path':'data','sha256':hashlib.sha256(b'old').hexdigest()}];assert verify(tmp_path,entries)==1;p.write_bytes(b'new')
 with pytest.raises(ValueError,match='Checksum'):verify(tmp_path,entries)

def test_verifies_decoded_payload_not_just_container(tmp_path):
 raw=gzip.compress(b'original',mtime=0);(tmp_path/'data.gz').write_bytes(raw);entry={'path':'data.gz','sha256':hashlib.sha256(raw).hexdigest(),'decoded_sha256':hashlib.sha256(b'other').hexdigest()}
 with pytest.raises(ValueError,match='Decoded checksum'):verify(tmp_path,[entry])

def test_rejects_manifest_path_escape(tmp_path):
 with pytest.raises(ValueError,match='outside'):verify(tmp_path,[{'path':'../escape','sha256':'0'}])

def test_reproduces_published_scores_on_exact_same_rows():
 report=json.loads((R/'inputs/public/weekly-review--report.json').read_text());d=pd.read_csv(R/'results/enriched-player-evaluation.csv');assert set(d.gw)=={8,9,10};assert len(d)==2007;assert not d.duplicated(['gw','fixture','id']).any()
 for gw,g in d.groupby('gw'):
  w=next(w for w in report['weeks']if w['gw']==gw);assert w['status']=='complete';assert len(g)==w['scored_rows'];assert abs(abs(g.xp-g.points).mean()-w['xp_mae'])<1e-10;assert abs(abs(g.xmins-g.minutes).mean()-w['minute_mae'])<1e-10

def test_conditional_and_unconditional_scores_not_blended():
 j=json.loads((R/'results/evaluation.json').read_text());assert j['minute_bin_point_oracle']['supported_rows']+j['minute_bin_point_oracle']['excluded_rows']==2007;assert 'scope'in j['minute_bin_point_oracle'];assert j['production_changed']is False

def test_external_field_matches_original_target_and_cutoff():
 j=json.loads((R/'results/official-ep-next-benchmark.json').read_text())
 for s in j['sources']:assert s['field']=='ep_next'and s['next_gw_confirmed'];assert pd.Timestamp(s['official_fetched_at'])<=pd.Timestamp(s['model_cutoff'])<pd.Timestamp(s['deadline'])
 assert j['results'][0]['rows']==2007

def test_scoring_oracle_coverage():
 j=json.loads((R/'results/scoring-rule-verification.json').read_text());assert j['fixtures']==30 and j['official_player_rows']==2011;assert j['bonus_fixture_mismatches']==j['dc_threshold_mismatches']==j['dc_count_mismatches']==0

def test_rule_references_match_pinned_mathematics():
 for name in ['bps.py','defcon.py']:
  assert (R/'code/reference'/name).read_bytes()==(R/'evidence/active-source/src/fpl_v1_1_model'/name).read_bytes()

def test_recorded_result_hashes_match_reproduced_outputs():
 assert verify(R,json.loads((R/'result-integrity.json').read_text()))>0
