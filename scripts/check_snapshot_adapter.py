"""The shared TS file differs from the frozen source ONLY at three input gates."""
import hashlib
from pathlib import Path

FROZEN='608fb3e18a59e89dea9476e6a403c7fc9c9cf63a80635b83a9859d7fb169678b'


def check(text):
    edits=[
        ('def run(payload,raw,include_chips=False,tc_samples=None,*,snapshot_at=None):',
         'def run(payload,raw,include_chips=False,tc_samples=None):'),
        ('    if snapshot_at is not None:\n        from b_snapshot_policy import validate_snapshot\n        validate_snapshot(payload,raw,snapshot_at)\n',''),
        ("    if snapshot_at is None and payload.get('freshness_limit_hours') is not None:",
         "    if payload.get('freshness_limit_hours') is not None:"),
        ("    state=parse_state(raw,meta,gw,payload['data_asof'] if snapshot_at is None else snapshot_at)",
         "    state=parse_state(raw,meta,gw,payload['data_asof'])"),
    ]
    for current,original in edits:
        if text.count(current)!=1:raise ValueError('Unreviewed snapshot adapter change')
        text=text.replace(current,original)
    if hashlib.sha256(text.encode()).hexdigest()!=FROZEN:
        raise ValueError('Default TS source differs from the frozen mathematics')
    return True


if __name__=='__main__':
    check((Path(__file__).resolve().parent/'run_live_locked_ts.py').read_text())
    print('Frozen TS mathematics/default validation unchanged; explicit B snapshot gates only')
