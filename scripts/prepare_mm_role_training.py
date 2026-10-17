#!/usr/bin/env python3
"""Rebuild PR4 role-fit inputs from its verified capsule and canonical outcomes.

No new model, tuning or inferred health labels. The original source functions
are retained verbatim in pr4_individual_mm.py. Cached files are public research
inputs, not manager state, and carry exact input/code hashes.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame
from pr4_individual_mm import ledger,role_features,fit_role
from audit_mm_components import prefix_features,load_obs
from audit_capture_io import write_frame

ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def restore_original_news(frame):
    """The capsule omits caps; restore PR4's original strict-news join, not guesses."""
    from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
    parts=[]
    for season,g in frame.groupby('season',sort=False):
        if season=='2025-26':
            strict=read_split_gzip_jsonl(ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2','predeadline_strict.jsonl.gz')
            original=g.team_news_state.copy()
            g=g.drop(columns=[c for c in g if c.startswith('team_news_')])
            g=build_strict_team_news_features(g,strict,doubt_cap=.5,major_doubt_cap=.1)
            if not g.team_news_state.reset_index(drop=True).eq(original.reset_index(drop=True)).all():
                raise ValueError('Original strict-news states disagree with frozen capsule')
        else:
            g=g.copy();g['team_news_availability_cap']=1.
        parts.append(g)
    return pd.concat(parts,ignore_index=True)

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    frames={}
    for season,hours in [('2024-25',4),('2025-26',3)]:
        source=ROOT/f'work/mm-integration-source/mm-source/{season}_candidates.npz'
        f=load_frame(source);f=f[f['mode'].eq('original')].copy()
        obs=load_obs(ROOT/'work/core.sqlite3',season,hours)
        f=f.merge(obs[['fixture_uuid','player_uuid','kickoff_at','known']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
        f['outcome_known_at']=f.known;f['started']=f.y
        for dest,src in [('new_p_start','p'),('new_start_minutes','s'),('new_q_sub','q'),('new_sub_minutes','c'),('new_xmins','x')]:f[dest]=f[src]
        # The compact result capsule already includes this descriptive label;
        # prefix_features reconstructs it from prior-only observations.
        f=prefix_features(f.drop(columns=['player_type'],errors='ignore'),obs);frames[season]=f
        print('Canonical original MM prefix',season,len(f),flush=True)
    obs,audit=ledger(ROOT/'work/core.sqlite3',frames)
    write_frame(out/'verified_observations.csv.gz',obs)
    pieces=[]
    for season,frame in frames.items():
        f,_=role_features(frame,obs,42.)
        pieces.append(f)
        print('Original selected PR4 bands/h42/C1 features',season,len(f),flush=True)
    f=restore_original_news(pd.concat(pieces,ignore_index=True))
    write_frame(out/'role_training.csv.gz',f)
    cuts=[f[f.season.eq(s)].cutoff.max() for s in ['2024-25','2025-26']]
    parity=[]
    for cut in cuts:
        target=f[f.cutoff.eq(cut)].copy()
        train=f[pd.to_datetime(f.outcome_known_at,utc=True,format='mixed').lt(pd.Timestamp(cut))]
        predicted=fit_role(train,target,1.,'bands')
        season=target.season.iloc[0]
        reference=load_frame(ROOT/f'work/mm-integration-source/mm-source/{season}_candidates.npz')
        reference=reference[reference['mode'].eq('role_start')]
        z=target[['fixture_uuid','player_uuid']].assign(rebuilt=predicted).merge(reference[['fixture_uuid','player_uuid','p']],on=['fixture_uuid','player_uuid'],validate='one_to_one')
        error=float(abs(z.rebuilt-z.p).max())
        parity.append(dict(cutoff=cut,rows=len(z),max_abs_p_start_error=error,within_1e_6=error<=1e-6))
    paths=[ROOT/'scripts/pr4_individual_mm.py',ROOT/'scripts/prepare_mm_role_training.py',ROOT/'work/core.sqlite3',ROOT/'checkpoints/role_injury_mm_20261016/manifest.json']
    manifest=dict(scope='reconstructed_original_PR4_role_inputs',selection='bands_h42.0_C1.0',rows=len(f),observations=len(obs),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        outputs_sha256={p.name:digest(p) for p in [out/'role_training.csv.gz',out/'verified_observations.csv.gz']},
        reference_parity=parity,reference_parity_passed=all(r['within_1e_6'] for r in parity),
        historical_source_clock_certified=False,locked_model_active=False)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'availability_audit.json').write_text(json.dumps(audit,indent=2,default=str)+'\n')
    print(json.dumps(manifest,indent=2),flush=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'work/current-B-role-training');a=p.parse_args();build(a.out)
