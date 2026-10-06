"""Independently validate research ledger identity/timing/checksum invariants."""
import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def validate(folder):
    for name,digest in json.loads((folder/'SHA256_MANIFEST.json').read_text()).items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
    read=lambda name:[json.loads(r) for r in gzip.decompress((folder/name).read_bytes()).splitlines()]
    obs=read('observations.jsonl.gz');strict=read('predeadline_strict.jsonl.gz');conditional=read('predeadline_archive_clock.jsonl.gz')
    sources=json.loads((folder/'source_manifest.json').read_text())['sources']
    t=lambda x:dt.datetime.fromisoformat(x.replace('Z','+00:00'))
    checks=dict(observation_duplicate_source_player_gw=len(obs)-len({(r['source_id'],r['fpl_element'],r['gw']) for r in obs}),strict_duplicate_player_gw=len(strict)-len({(r['fpl_element'],r['gw']) for r in strict}),strict_target_leakage=sum(t(r['effective_at'])>=t(r['cutoff']) for r in strict),strict_unverified=sum(not r['timing_verified'] for r in strict),strict_unresolved=sum(r['identity_status']!='mapped' for r in strict),historical_pipeline_mismatches=sum(not r['pipeline_verified'] for r in sources),future_news=sum(r['future_news_timestamp'] for r in obs),chance_outside_0_100=sum(r[k] is not None and not 0<=r[k]<=100 for r in obs for k in ['chance_this_round','chance_next_round']),deadline_mismatches=sum(not r['deadline_matches'] for r in sources))
    assert not any(checks.values()),checks
    checks.update(strict_rows=len(strict),conditional_rows=len(conditional),strict_known_state_rows=sum(r['normalized_availability_state']!='UNKNOWN' for r in strict),conditional_known_state_rows=sum(r['normalized_availability_state']!='UNKNOWN' for r in conditional),strict_state_counts=dict(collections.Counter(r['normalized_availability_state'] for r in strict)),source_job_timestamp_rows=sum(r['timestamp_basis']=='github_successful_cache_job_completion' for r in strict),strict_carry_forward_rows=sum(r['carried_from_earlier_gw'] for r in strict),strict_unchanged_news_rows=sum(r['unchanged_news_since_previous_gw'] for r in strict))
    return checks
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--folder',type=Path,default=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2')
    a.add_argument('--out',type=Path)
    args=a.parse_args();result=validate(args.folder);text=json.dumps(result,indent=2)+'\n'
    if args.out:
        if args.out.exists():raise FileExistsError('Append-only audit result already exists')
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(text)
    print(text)
