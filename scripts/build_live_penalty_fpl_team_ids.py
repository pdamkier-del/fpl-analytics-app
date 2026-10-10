#!/usr/bin/env python3
"""Verify 2026/27 official FPL team namespace for the frozen penalty adapter.

team_code and team_id are both official FPL bootstrap team IDs here. A future
penalty-side ledger must use this *same FPL namespace*, not FotMob identifiers.
This reconstructs identity mapping only; it does not invent penalty attempts.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/live-final-model'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
def build(bootstrap,fixtures):
    teams=bootstrap['teams']
    ids=[int(t['id']) for t in teams]
    if len(ids)!=20 or len(set(ids))!=20 or set(ids)!=set(range(1,21)):
        raise ValueError('Expected 20 unique official FPL team identifiers')
    active={int(v) for m in fixtures for k in ('team_h','team_a') if (v:=m.get(k)) is not None}
    if active!=set(ids):raise ValueError('Fixture teams and official bootstrap teams differ')
    return pd.DataFrame({'team_code':sorted(ids),'team_id':sorted(ids)})
def main():
    boot=json.loads((WORK/'bootstrap.json').read_text())
    fixtures=json.loads((WORK/'fixtures.json').read_text())
    output=build(boot,fixtures)
    BASE.mkdir(parents=True,exist_ok=True)
    output.to_csv(BASE/'verified_penalty_team_ids.csv.gz',index=False,compression='gzip')
    print(json.dumps({'classification':'VERIFIED_FPL_TEAM_ID_NAMESPACE_NOT_PENALTY_EVIDENCE',
      'team_count':len(output),'mapping':'official FPL team id == FPL team code',
      'penalty_attempts_verified':False,'live_xp_certified':False}))
if __name__=='__main__':main()
