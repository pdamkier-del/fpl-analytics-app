#!/usr/bin/env python3
"""Fresh verified sources -> unchanged original chain -> reproducible diagnostic."""
import hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from verify_canonical_raw_rebuild import execute
W=ROOT/'work/live-final-model';B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
def main():
    execute('collect_current_locked_inputs')
    m=json.loads((W/'source_manifest.json').read_text())
    if m['errors']:raise ValueError('Source collection errors: publication blocked')
    if int(m['target_gw'])>33:raise ValueError('Original six-GW TS horizon exceeds season; no shortened strategy substituted')
    # Capture authentic roster/news evidence now for subsequent historical training.
    b=json.loads((W/'bootstrap.json').read_text());gw=int(m['target_gw'])
    at=m['bootstrap_observed_at'];deadline=m['deadline']
    if datetime.fromisoformat(at)>=datetime.fromisoformat(deadline):raise ValueError('Roster observed after deadline')
    f=W/'predeadline_2026_archives'/f'gw{gw}.json';f.parent.mkdir(parents=True,exist_ok=True)
    if not f.exists():
        obj=dict(evidence=dict(gw=gw,snapshot_at_utc=at,official_deadline=deadline,players=len(b['elements']),source_sha256=hashlib.sha256((W/'bootstrap.json').read_bytes()).hexdigest(),source='Official FPL captured by this workflow; exact capture time, not publication time'),players=[dict(id=p['id'],team=p['team'],position=p['element_type'],name=p['web_name'],status=p['status'],news=p.get('news'),news_added=p.get('news_added'),chance_next=p.get('chance_of_playing_next_round')) for p in b['elements']])
        f.write_text(json.dumps(obj,indent=2)+'\n')
    for p in [W/'publication_provenance.json',ROOT/'work/live-manager-validation/tc_scenarios.json']:
        p.unlink(missing_ok=True)
    execute('audit_current_locked_inputs')
    execute('verify_canonical_raw_rebuild')
    audit=json.loads((W/'canonical_raw_rebuild.json').read_text())
    receipt=dict(cutoff=m['observed_at'],source_workflow='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],checksums={name:hashlib.sha256((B/name).read_bytes()).hexdigest() for name in ['vfinal_live_full_simulator_input.csv.gz','live_vfinal_fixture_xp.csv.gz']},reproducibility=dict(two_raw_rebuilds_exact=audit['passed']),source_limitations=['Historical availability times remain unverified kickoff + 4h proxies.','Partial BPS and historical MM coverage prevent full certification.'])
    (W/'publication_provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
    execute('build_live_vfinal_desktop');execute('run_live_tc_scenarios');execute('build_live_vfinal_desktop')
    execute('validate_live_manager_chain')
    # Recheck official next deadline after expensive original simulation.
    import urllib.request
    current=json.load(urllib.request.urlopen('https://fantasy.premierleague.com/api/bootstrap-static/',timeout=30))
    upcoming=next(e for e in current['events'] if e.get('is_next'))
    if int(upcoming['id'])!=gw or datetime.now(timezone.utc)>=datetime.fromisoformat(upcoming['deadline_time'].replace('Z','+00:00')):raise ValueError('Official GW changed during rebuild; publication blocked')
if __name__=='__main__':main()
