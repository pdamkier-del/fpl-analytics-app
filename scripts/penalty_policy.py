"""Fail-closed opt-in promotion of historically validated B penalty arithmetic."""
import hashlib,json
from pathlib import Path


def load(root,path):
    root=Path(root);policy=json.loads(Path(path).read_text())
    if policy.get('version')!='conditional-penalties-v1' or policy.get('approved')is not True:
        raise ValueError('Penalty policy not approved')
    if policy.get('nonpenalty_scorer_correction')is not False:
        raise ValueError('Nonpenalty scorer correction has not passed promotion gates')
    for name,expected in policy['sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise ValueError('Penalty policy checksum mismatch: '+name)
    decision=json.loads((root/policy['decision']).read_text())
    protocol=json.loads((root/policy['protocol']).read_text())
    if decision.get('passed')is not True or decision.get('fixtures')!=501 or decision.get('baseline_max_xp_error')!=0:
        raise ValueError('Penalty historical gate failed')
    if protocol.get('conditional_only')is not True or protocol.get('conditional_penalties')is not True:
        raise ValueError('Wrong penalty candidate evidence')
    return policy
