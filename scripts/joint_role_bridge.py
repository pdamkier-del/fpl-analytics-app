"""Opt-in B joint-role bridge. Not imported by the original/default model."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

from fpl_v1_1_model.experimental_joint_role_assignment import build_role_distribution
from fpl_v1_1_model.experimental_role_importance import importance


def load_assignment_policy(root,path):
    root=Path(root);policy=json.loads(Path(path).read_text())
    if policy.get('version')!='joint-role-assignment-v1' or not 0<float(policy.get('strength',0))<=1:
        raise ValueError('Unsupported joint role policy')
    required={'scripts/joint_role_bridge.py',
              'src/fpl_v1_1_model/experimental_joint_role_assignment.py',
              'src/fpl_v1_1_model/experimental_role_assignment_history.py',
              'src/fpl_v1_1_model/experimental_role_importance.py'}
    if required-set(policy.get('evidence_sha256',{})):raise ValueError('Missing role implementation fingerprints')
    for name,digest in policy.get('evidence_sha256',{}).items():
        p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
            raise ValueError('Joint role policy evidence changed: '+name)
    base='analysis/results/joint-role-candidate-20261022/'
    for name,key in [('decision.json','mm_gate_passed'),('pm-decision.json','passed')]:
        if base+name not in policy.get('evidence_sha256',{}):raise ValueError('Missing role validation receipt')
        report=json.loads((root/base/name).read_text())
        if not report.get(key):raise ValueError('Joint role historical gate rejected')
    if float(json.loads((root/base/'decision.json').read_text())['selected_strength'])!=float(policy['strength']):
        raise ValueError('Policy differs from historically selected strength')
    return policy


def apply_assignment(frame,history,*,strength):
    """Return coherent MM marginals and the exact PM lineup distribution.

    This function accepts forecast inputs only. Outcomes are neither used nor
    needed; callers retain them separately for historical validation.
    """
    if frame.fixture_uuid.nunique()!=1 or frame.cutoff.nunique()!=1 or frame.season.nunique()!=1:
        raise ValueError('One forecast fixture/origin required')
    result=frame.copy();distributions={};audit=[]
    for team,g in frame.groupby('team_id',sort=True):
        g=g[~g.pos.isin(['GK','GKP'])]
        evidence=history.evidence(str(frame.season.iloc[0]),int(team),frame.cutoff.iloc[0])
        if evidence is None:
            audit.append(dict(team_id=int(team),applied=False,reason='no prior tactical history'))
            continue
        if abs(g.p.sum()-10)>1e-6:raise ValueError('B must supply ten outfield starts')
        if 'availability_cap' in g:
            caps=g.availability_cap.to_numpy(float)
        else:
            caps=np.ones(len(g));known=g.news_eligible.to_numpy(bool)
            chance=pd.to_numeric(g.news_chance,errors='coerce').to_numpy(float)
            usable=known&np.isfinite(chance);caps[usable]=chance[usable]/100
            caps[known&g.news_state.isin(['OUT','SUSPENDED']).to_numpy()]=0.
        # Stage is known before kickoff. Opponent/relative upcoming priority is
        # explicitly neutral until an available-before-cutoff calendar exists.
        target_importance=importance('prem',int(g.gw.iloc[0]),pd.Timestamp(frame.cutoff.iloc[0]).month,evidence['active_competitions'])
        states=evidence['states']
        players=[dict(player_uuid=str(r.player_uuid),base_p_start=float(r.p),
                      availability_cap=float(cap),**states.get(str(r.player_uuid),{}))
                 for r,cap in zip(g.itertuples(),caps)]
        lineups,p=build_role_distribution(players,evidence['formations'],target_importance,strength=strength)
        q=np.minimum(g.q.to_numpy(),np.divide(np.maximum(caps-p,0),1-p,out=np.zeros(len(p)),where=p<1))
        result.loc[g.index,'p']=p;result.loc[g.index,'q']=q
        result.loc[g.index,'x']=p*g.s.to_numpy()+(1-p)*q*g.c.to_numpy()
        distributions[int(team)]=lineups
        audit.append(dict(team_id=int(team),applied=True,strength=float(strength),
            importance=float(target_importance),importance_source='existing MI formula, normalized competition and known PL stage; neutral opponent/future-priority',
            prior_games=evidence['games'],max_known_at=evidence['max_known_at'],
            formation_weights={form:w/sum(evidence['formations'].values())for form,w in evidence['formations'].items()},
            lineup_components=len(lineups),
            representative_lineup=dict(formation=max(lineups,key=lambda r:r.weight).formation,
                players=list(max(lineups,key=lambda r:r.weight).players),roles=list(max(lineups,key=lambda r:r.weight).roles),
                selection_rule='largest component in the supported assignment mixture; not a calibrated modal XI')))
    return result,distributions,audit
