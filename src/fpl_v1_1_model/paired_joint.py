"""Minute-only paired diagnostic around the unchanged archived simulator."""
from dataclasses import replace
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .phase4b import FrozenPlayerForecast, build_match_input
from .joint_simulator import simulate_many


def read_frozen_table(folder, name):
    folder = Path(folder)
    manifest = json.loads((folder/'manifest.json').read_text())
    entry = next(x for x in manifest['outputs'] if x['name'] == name)
    chunks = []
    for part in entry['parts']:
        path = (folder/part['path']).resolve()
        if not path.is_relative_to(folder.resolve()):
            raise ValueError('Invalid frozen part path')
        data = path.read_bytes()
        if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
            raise ValueError('Frozen part checksum mismatch')
        chunks.append(data)
    compressed = b''.join(chunks)
    if hashlib.sha256(compressed).hexdigest() != entry['compressed_sha256']:
        raise ValueError('Frozen stream checksum mismatch')
    raw = gzip.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != entry['uncompressed_sha256']:
        raise ValueError('Frozen table checksum mismatch')
    frame = pd.read_csv(io.BytesIO(raw))
    if len(frame) != entry['rows']:
        raise ValueError('Frozen table row mismatch')
    return frame


def build_pair(frame):
    """Call original adapter once; replace only candidate minute fields."""
    if frame.empty or frame.fixture_uuid.nunique() != 1 or frame.player_uuid.duplicated().any():
        raise ValueError('One unique fixture roster required')
    common = ['home_team_id','away_team_id','lambda_home_goals','lambda_away_goals',
              'assist_probability_per_goal','cutoff']
    if any(frame[c].nunique(dropna=False) != 1 for c in common):
        raise ValueError('Inconsistent common match input')
    teams = {int(frame.home_team_id.iloc[0]),int(frame.away_team_id.iloc[0])}
    if len(teams) != 2 or set(frame.team_id.astype(int)) != teams:
        raise ValueError('Both fixture teams required')
    for c in ['control_p_start','v4_workload_start_p_start','p_cameo_given_bench',
              'v4_p_cameo_given_bench']:
        x=frame[c].to_numpy(float)
        if not np.isfinite(x).all() or ((x<0)|(x>1)).any():
            raise ValueError('Invalid probability '+c)
    for c in ['control_xmins','v4_workload_start_xmins','start_minutes_mean',
              'v4_start_minutes_mean','cameo_minutes_mean','v4_cameo_minutes_mean']:
        x=frame[c].to_numpy(float)
        if not np.isfinite(x).all() or ((x < -1e-8)|(x > 90+1e-8)).any():
            raise ValueError('Invalid minutes '+c)
    for prefix, ps, xm in [('', 'control_p_start','control_xmins'),
                           ('v4_', 'v4_workload_start_p_start','v4_workload_start_xmins')]:
        p=frame[ps].to_numpy(float)
        composed=p*frame[prefix+'start_minutes_mean']+(1-p)*frame[prefix+'p_cameo_given_bench']*frame[prefix+'cameo_minutes_mean']
        if not np.allclose(composed,frame[xm],rtol=0,atol=1e-8):
            raise ValueError('Expected-minutes identity mismatch')
    players=[]
    for r in frame.itertuples(index=False):
        players.append(FrozenPlayerForecast(str(r.player_uuid),int(r.team_id),r.pos,
            r.control_p_start,r.control_xmins,r.start_minutes_mean,r.cameo_minutes_mean,
            r.p_cameo_given_bench,r.goal_mu,r.assist_mu,r.mu_dc,r.dc_alpha,
            r.p_yellow,r.p_red,r.lambda_saves if r.pos in ('GK','GKP') else 0.0,0.0,0.0))
    first=frame.iloc[0]
    control=build_match_input(home_team_id=int(first.home_team_id),away_team_id=int(first.away_team_id),
        lambda_home_goals=float(first.lambda_home_goals),lambda_away_goals=float(first.lambda_away_goals),
        players=players,assist_probability_per_goal=float(first.assist_probability_per_goal))
    lookup=frame.set_index('player_uuid')
    candidate=replace(control,players=tuple(replace(p,
        p_start=float(lookup.loc[p.player_id,'v4_workload_start_p_start']),
        p_cameo_given_bench=float(lookup.loc[p.player_id,'v4_p_cameo_given_bench']),
        start_minutes_mean=float(lookup.loc[p.player_id,'v4_start_minutes_mean']),
        cameo_minutes_mean=float(lookup.loc[p.player_id,'v4_cameo_minutes_mean'])) for p in control.players))
    return control,candidate


def run_pair(control,candidate,n,seed):
    # Same seed/budget; divergent branches consume different random draws.
    # This is not event-aligned common-random-number sampling.
    return simulate_many(control,n=n,seed=seed),simulate_many(candidate,n=n,seed=seed)
