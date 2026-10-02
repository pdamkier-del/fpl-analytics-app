import json
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_independent_europe_fixtures import compare,normalize


def test_europe_organizer_aliases():
    for a,b in [('FC Midtjylland','Midtjylland'),('Malmö FF','Malmö'),('FC Porto','Porto'),('KuPS','KuPS Kuopio')]:
        assert normalize(a)==normalize(b)


def test_matching_detects_score_date_conflict_and_repeated_pair():
    source=pd.DataFrame([{'match_id':'25-26-europa-league-fc-midtjylland-vs-nottingham-forest',
      'tournament':'europa-league','gameweek':30,'home_score':1,'away_score':0,
      'kickoff_time':'2025-10-02T19:00:00Z','finished':True}])
    inventory=pd.DataFrame([
      {'competition':'europa-league','home':'Nottingham Forest','away':'Midtjylland','home_score':2,'away_score':3,
       'date':'2025-10-02','stage':'League phase','source_url':'organizer','source_line':1},
      {'competition':'europa-league','home':'Nottingham Forest','away':'Midtjylland','home_score':0,'away_score':1,
       'date':'2026-03-12','stage':'Round of 16','source_url':'organizer','source_line':2}])
    audit,q,_=compare(source,inventory)
    assert len(q)==1 and audit.iloc[0].candidate_count==1
    assert not audit.iloc[0].existing_kickoff_date_matches_candidate
    assert audit.iloc[0].independent_date=='2026-03-12'


def test_saved_europe_quarantine_and_pl_control():
    q=pd.read_csv(ROOT/'analysis/results/independent-europe-audit/workload_quarantine.csv')
    assert len(q)==40 and not q.match_id.duplicated().any()
    for file in ('official_player_minutes.csv','team_match_coverage.csv'):
        f=pd.read_csv(ROOT/'analysis/results/workload-quality-v3'/file)
        assert not f.match_id.isin(q.match_id).any()
    file='reused_holdout_diagnostic_predictions.csv.gz'
    a=pd.read_csv(ROOT/'analysis/results/workload-minutes-v1'/file)
    b=pd.read_csv(ROOT/'analysis/results/workload-quality-minutes-v3'/file)
    cols=[c for c in a if 'pl_only' in c or 'role_control' in c]
    assert len(cols)>=4
    pd.testing.assert_frame_equal(a[cols],b[cols],check_exact=True)


def test_current_default_rejects_missing_quarantine():
    import subprocess
    r=subprocess.run([sys.executable,str(ROOT/'scripts/build_workload_features.py'),
      '--db',str(ROOT/'work/core.sqlite3'),'--quarantine-csv',''],capture_output=True,text=True,cwd=ROOT)
    assert r.returncode!=0 and 'requires an audited quarantine' in r.stderr


def test_saved_fixture_inventory_is_audit_only():
    source=json.loads((ROOT/'data_v1_1/raw/independent-cup-inventory/UEFA_SOURCE_MANIFEST.json').read_text())
    assert not source['historical_publication_certified'] and not source['kickoff_time_available']
