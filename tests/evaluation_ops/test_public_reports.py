from pathlib import Path
import gzip,json,copy,subprocess,os
import numpy as np,pytest
from evaluation_ops.reporting import score,digest,validate_bundle,crps
from evaluation_ops.public_report import write_report,collect_labels,recover
A=Path(__file__).resolve().parents[2]/'analysis/audits/2026-11-22'
@pytest.fixture(scope='module')
def archives():
 load=lambda n:json.loads(gzip.decompress((A/'inputs/archive'/n).read_bytes()))
 all_report=json.loads((A/'inputs/public/weekly-review--report.json').read_text());boot=load('bootstrap.json.gz');games=load('fixtures.json.gz');out=[]
 for gw in [8,9,10]:
  f=load(f'gw{gw}-forecast.json.gz');w=next(w for w in all_report['weeks']if w['gw']==gw);live=load(f'gw{gw}-live.json.gz');bundle={'season':f['season'],'forecast':f,'mm':load(f'gw{gw}-mm.json.gz'),'documents':load(f'gw{gw}-existing-app-data.json.gz'),'receipt':{'published_at':w['published_at'],'publication_commit':w['publication_commit'],'forecast_sha256':f['forecast_sha256'],'archive_basis':'original_public_forecast_snapshot'}}
  labels=collect_labels(bundle,boot,games,fetch=lambda path,L=live:L,observed_at='2026-11-22T10:00:00Z');out.append((bundle,labels,w))
 return out
@pytest.mark.parametrize('index',[0,1,2])
def test_existing_original_audit_numbers_match(archives,index):
 b,l,w=archives[index];r=score(b,l);assert r['status']=='complete';assert r['scored_rows']==w['scored_rows'];assert r['summary']['points']['xp_mae']==pytest.approx(w['xp_mae']);assert r['summary']['minutes']['minute_mae']==pytest.approx(w['minute_mae']);assert r['summary']['minutes']['start']['brier']==pytest.approx(next(x['brier']for x in w['metrics']if x['event']=='start'))
 assert r['official_ep_next']['rows']==w['scored_rows'];assert r['bps']['forecast_score_status']=='not_identified';assert len(r['calibration'])>0

def test_partial_gw_is_never_scored(archives):
 b,l,_=archives[0];l={**l,'event':{**l['event'],'data_checked':False}};r=score(b,l);assert r['status']=='pending_results'and r['scored_rows']==0

def test_mutated_or_late_forecast_rejected(archives):
 b,l,_=archives[0];b={**b,'receipt':{**b['receipt'],'published_at':b['forecast']['origin_deadline']}}
 with pytest.raises(ValueError,match='predeadline'):score(b,l)
 b=copy.deepcopy(archives[0][0]);b['forecast']['players'][0]['name']='tamper'
 with pytest.raises(ValueError,match='seal'):score(b,l)

def test_missing_labels_not_fabricated_as_zero(archives):
 b,l,_=archives[0];l={**l,'rows':l['rows'][1:]};r=score(b,l);assert r['status']=='partial_missing_labels';assert r['scored_rows']==len(b['forecast']['players'])-1;assert r['missing']

def test_no_revised_future_ep_next_used(archives):
 b,l,_=archives[0];l=copy.deepcopy(l)
 for p in l['identities']:p['ep_next']=999
 r=score(b,l);assert r['official_ep_next']['official_mae']<10

def test_immutable_reports_and_explicit_outcome_revision(archives,tmp_path):
 b,l,_=archives[0];r,path=write_report(tmp_path,b,l);before=(tmp_path/path/'report.json').read_bytes();r2,path2=write_report(tmp_path,b,l);assert path2==path
 new={**l,'observed_at':'2026-11-23T10:00:00Z'};_,path3=write_report(tmp_path,b,new);assert path3!=path;assert (tmp_path/path/'report.json').read_bytes()==before

def test_crps_known_distribution():assert crps([0,2],1)==pytest.approx(.5)

def test_schedule_change_quarantined(archives):
 b,l,_=archives[0];l={**l,'fixtures':copy.deepcopy(l['fixtures'])};team=b['forecast']['players'][0]['team_id'];l['fixtures'].append({'id':9999,'event':8,'finished':True,'team_h':team,'team_a':999});r=score(b,l);assert any(x['reason']=='schedule_changed_after_forecast'for x in r['missing'])
