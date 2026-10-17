#!/usr/bin/env python3
"""Verified official FPL fixture-roster skeleton for the MM current input chain.

Does NOT claim to produce B's historical role/chance/return-duration features.
Uses only immutable timestamped source-capture files. All nonofficial B features
remain unavailable and the current model must fail closed until they are built.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def build(bootstrap, fixtures, receipt, *, cutoff):
    if receipt.get('scope') != 'source_capture_not_forecast':
        raise ValueError('Expected source capture receipt, not a forecast')
    if hashlib.sha256(canonical(bootstrap)).hexdigest() != receipt.get('bootstrap_sha256'):
        raise ValueError('Bootstrap bytes do not match source receipt')
    if hashlib.sha256(canonical(fixtures)).hexdigest() != receipt.get('fixtures_sha256'):
        raise ValueError('Fixture bytes do not match source receipt')
    observed = datetime.fromisoformat(receipt['observed_at'].replace('Z', '+00:00'))
    cut = datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
    deadline = datetime.fromisoformat(receipt['origin_deadline'].replace('Z', '+00:00'))
    if any(t.tzinfo is None for t in (observed, cut, deadline)):
        raise ValueError('All clocks must be timezone aware')
    if not observed < cut < deadline:
        raise ValueError('Require source capture < feature cutoff < official deadline')
    next_events = [e for e in bootstrap['events'] if e.get('is_next')]
    if len(next_events) != 1:
        raise ValueError('One official next event required')
    origin = next_events[0]
    if origin['id'] != receipt['origin_gw'] or origin['deadline_time'] != receipt['origin_deadline']:
        raise ValueError('Event/deadline mismatch with source receipt')
    gws = list(range(int(origin['id']), min(39, int(origin['id']) + 6)))
    team_ids = {int(t['id']) for t in bootstrap['teams']}
    players = bootstrap['elements']
    ids = [int(p['id']) for p in players]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Duplicate/missing official player IDs')
    if any(int(p['team']) not in team_ids or int(p['element_type']) not in (1, 2, 3, 4) for p in players):
        raise ValueError('Unknown team or position in official roster')
    fixture_rows = []
    for f in fixtures:
        if f.get('event') not in gws:
            continue
        if f.get('started') or not f.get('kickoff_time'):
            raise ValueError('Started/unknown kickoff in target horizon')
        if int(f['team_h']) not in team_ids or int(f['team_a']) not in team_ids:
            raise ValueError('Unknown official fixture team')
        kick = datetime.fromisoformat(f['kickoff_time'].replace('Z', '+00:00'))
        if kick <= cut:
            raise ValueError('Target kickoff not after forecast cutoff')
        fixture_rows.append(f)
    if not fixture_rows:
        raise ValueError('No scheduled target fixtures')
    fixtures_by_id = {int(f['id']): f for f in fixture_rows}
    if len(fixtures_by_id) != len(fixture_rows):
        raise ValueError('Duplicate fixture IDs')
    rows = []
    for f in sorted(fixture_rows, key=lambda x: (x['event'], x['id'])):
        for p in players:
            if int(p['team']) not in (int(f['team_h']), int(f['team_a'])):
                continue
            rows.append(dict(
                season='2026-27', gw=int(f['event']), fixture_id=int(f['id']),
                fixture_uuid=f'live-2026-27-fpl-{int(f["id"])}',
                fpl_element=int(p['id']), team_id=int(p['team']),
                pos={1:'GK', 2:'DEF', 3:'MID', 4:'FWD'}[int(p['element_type'])],
                target_kickoff=f['kickoff_time'], cutoff=cut.isoformat(),
                role_feature_status='NOT_AVAILABLE',
                player_uuid_status='NOT_AVAILABLE_UNTIL_CANONICAL_MAPPING'))
    if len(rows) != sum(sum(int(p['team']) in (int(f['team_h']), int(f['team_a'])) for p in players) for f in fixture_rows):
        raise ValueError('Roster cardinality mismatch')
    return dict(
        scope='official_identity_fixture_skeleton_not_B_features',
        model_ready=False, reason='Canonical UUID mapping and verified predeadline role/chance/return features required',
        origin_gw=int(origin['id']), gws=gws, cutoff=cut.isoformat(),
        source_observed_at=observed.isoformat(), source_workflow=receipt.get('workflow'),
        bootstrap_sha256=receipt['bootstrap_sha256'],
        fixtures_sha256=receipt['fixtures_sha256'],
        fixture_count=len(fixture_rows), roster_rows=len(rows), rows=rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True, help='Directory containing capture receipt/bootstrap/fixtures JSON')
    p.add_argument('--cutoff', required=True, help='Verified timestamp after capture, before official deadline')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    source = args.source
    receipt = json.loads((source/'receipt.json').read_text())
    bootstrap = json.loads((source/'bootstrap.json').read_text())
    fixtures = json.loads((source/'fixtures.json').read_text())
    payload = build(bootstrap, fixtures, receipt, cutoff=args.cutoff)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(payload)+b'\n')
    print(json.dumps({k:v for k,v in payload.items() if k != 'rows'}, sort_keys=True))

if __name__ == '__main__':
    main()
