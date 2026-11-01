"""Fitted B assist-allocation candidate; no MM or event-count changes.

This interface only replaces PlayerSimInput.assist_weight after MM/PhysicalKernel.
Activation requires an accepted, content-linked assist policy. No named players.
"""
from dataclasses import replace
import numpy as np

def assist_features(m,p):
    # Existing pregame role + expected exposure; the offset already includes minutes.
    return np.array([p.position=='DEF',p.position=='FWD',p.is_keeper,(p.position=='FWD')*float(m.get('baseline_xm',0))/90,m.get('tactical_role')in ['q_RW_slow','q_LW_slow','q_RAM_slow','q_LAM_slow','q_CAM_slow','q_SS_slow']],float)


def apply(inp,dist,meta,policy,arm):
    if arm=='baseline':return inp,dist
    if arm!='assist':raise ValueError('This branch owns assist calibration only; MM candidates are excluded')
    beta=np.array(policy['assist']['coef']);players=[]
    for p in inp.players:
        factor=float(np.exp(np.clip(assist_features(meta.get(p.player_id,{}),p)@beta,-np.log(2),np.log(2))))
        players.append(replace(p,assist_weight=p.assist_weight*factor))
    return replace(inp,players=tuple(players)),dist

def load_accepted(root,path):
    import hashlib,json
    from pathlib import Path
    root=Path(root);manifest=json.loads(Path(path).read_text())
    if manifest.get('approved')is not True or manifest.get('version')!='B-assist-calibration-v1':raise ValueError('Assist calibration is not approved')
    for name,digest in manifest['sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Assist calibration evidence/source changed: '+name)
    policy=json.loads((root/manifest['candidate']).read_text());decision=json.loads((root/manifest['decision']).read_text())
    digest=hashlib.sha256(json.dumps(policy['assist'],sort_keys=True).encode()).hexdigest()
    if decision.get('accepted')is not True or digest!=decision['policy_assist_sha256']or not decision['same_MM_and_goal_samples']or not decision['team_assist_budget_unchanged']:raise ValueError('Assist calibration predictive/structural gate failed')
    return dict(**policy,receipt=dict(version=manifest['version'],policy_file=str(Path(path).relative_to(root))if Path(path).is_absolute()else str(path),policy_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),decision=manifest['decision'],paired_FWD_Brier_delta95=decision['paired_FWD_assist_Brier_delta95'],all_MM_marginals_unchanged=True,extra_goal_or_assist_events=False,no_independent_accuracy_claim=True))

def attach_to_kernel(inp,kernel,moments,frame,policy):
    """An event-weight-only view of the same physical ensemble.

    Owns no p/q/s/c or exit/entry rule. Safe for a reviewed MM implementation
    exposing input/moments/sample. A combined MM change requires revalidation.
    """
    import copy
    from fpl_v1_1_model.role_event_priors import QCOLS
    meta={};by=frame.set_index('player_uuid')
    for p in inp.players:
        if p.player_id not in by.index:continue
        row=by.loc[p.player_id];values=np.array([row.get(c,np.nan)for c in QCOLS],float);role=QCOLS[int(np.argmax(values))]if np.isfinite(values).all()and values.sum()>0 else'Not Available'
        meta[p.player_id]=dict(baseline_xm=moments[p.player_id]['x'],tactical_role=role)
    new,_=apply(inp,{},meta,policy,'assist')
    if any(replace(a,assist_weight=b.assist_weight)!=b for a,b in zip(new.players,inp.players)):raise AssertionError('Assist calibration changed a minute/goal input')
    updated=copy.copy(kernel);updated.input=new;updated.audit=dict(kernel.audit)
    return new,updated
