#!/usr/bin/env python3
"""One opt-in current B -> locked PM -> private TS entry point.

All six GW targets must be produced at one origin. No retrospective per-GW
rows, synthetic profiles or legacy/vNext substitutions are accepted.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json
import numpy as np
import pandas as pd
from mm_candidate import FormationSelector,build_contract
from mm_candidate_forecast import infer_B,register
from mm_locked_bridge import attach_mm,run_current_ts,code_identity
from run_live_vfinal_joint_simulation import simulate
from build_live_vfinal_desktop import build


def run_pipeline(history,target,roles,provenance,pm,bootstrap,bps_audit,manager=None):
    from fpl_v1_1_model.forecast_snapshot import seal_forecast
    now=pd.Timestamp.now(tz='UTC')
    cut=pd.Timestamp(provenance['data_at'])
    if cut.tzinfo is None or cut>now or now-cut>pd.Timedelta(hours=24):
        raise ValueError('Current input freshness expired')
    deadline=pd.Timestamp(provenance['origin_deadline'])
    if deadline<=now:raise ValueError('Official forecast deadline expired')
    if not pd.to_datetime(target.cutoff,utc=True).eq(cut).all():raise ValueError('Feature cutoff mismatch')
    if set(target.season)!={'2026-27'}:raise ValueError('Wrong current season')
    event=next(e for e in bootstrap['events'] if e.get('is_next'))
    if pd.Timestamp(event['deadline_time'])!=deadline:raise ValueError('Official deadline mismatch')
    gws=list(range(int(event['id']),min(39,int(event['id'])+6)))
    if sorted(set(target.gw))!=gws:raise ValueError('Missing full six-GW target inputs')
    # Explicit source membership per fixture, not merely equal table lengths.
    official={int(p['id']):p for p in bootstrap['elements']}
    if pm.duplicated(['fixture_uuid','fpl_element']).any():raise ValueError('Duplicate FPL identity')
    for _,g in pm.groupby('fixture_uuid'):
        for tid,team in g.groupby('team_id'):
            expected={pid for pid,p in official.items() if int(p['team'])==int(tid)}
            if set(map(int,team.fpl_element))!=expected:raise ValueError('Incomplete current official fixture roster')
            if any(int(official[int(r.fpl_element)]['element_type'])!={'GK':1,'GKP':1,'DEF':2,'MID':3,'FWD':4}[r.pos] for r in team.itertuples()):
                raise ValueError('Official position mismatch')
    predicted,calibration=infer_B(history,target,provenance)
    doc=build_contract(predicted,FormationSelector(roles),scope='prospective_preview',
        source_hash=provenance['source_manifest_sha256'],model_data_at=provenance['data_at'])
    doc.update(origin_deadline=provenance['origin_deadline'],calibration=calibration,deadline_correct=False)
    joined=attach_mm(pm,predicted)
    if not joined.target_gw.eq(joined.gw).all():raise ValueError('PM target GW mismatch')
    xp,audit=simulate(joined)
    # Display/export exposure is B. Simulator propensities were calculated from
    # untouched PM controls; export must not falsely label those controls as B.
    display=joined.copy()
    for src,dest in [('v4_workload_start_p_start','control_p_start'),
                     ('v4_workload_start_xmins','control_xmins'),
                     ('v4_p_cameo_given_bench','p_cameo_given_bench')]:display[dest]=display[src]
    display['live_eligibility_applied']=display.v4_workload_start_p_start.eq(0)&display.v4_p_cameo_given_bench.eq(0)
    payload=build(display,xp,bootstrap,bps_audit)
    # Blank GWs are explicit zeros only for a club with no fixture at that GW.
    present={int(t):set(map(int,g.target_gw)) for t,g in pm.groupby('team_id')}
    for p in payload['players']:
        for gw in gws:
            if not any(w['gw']==gw for w in p['weeks']):
                if gw in present[p['team_id']]:raise ValueError('Missing player fixture forecast')
                p['weeks'].append(dict(gw=gw,xpts=0.,xmins=0.,p_play=0.,unavailable=False,fixtures=[]))
        p['weeks'].sort(key=lambda w:w['gw'])
    if {p['id'] for p in payload['players']}!=set(official):raise ValueError('Current player coverage incomplete')
    payload.update(model='B_locked_PM_preview',scope='prospective_preview',gws=gws,
        mm_version=doc['model_version'],parts={'mm':'diagnostic','pm_vfinal':'diagnostic'},
        source_workflow=provenance.get('source_workflow'),recommendations={'transfers':{'status':'Not Available: private manager state required'}})
    payload=seal_forecast(payload)
    plan=run_current_ts(payload,manager) if manager is not None else None
    return doc,payload,plan,audit


def main():
    p=argparse.ArgumentParser()
    for n in ['history','target','roles','provenance','pm-input','bootstrap','bps-audit','out']:
        p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--manager',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if a.manager and (a.out.resolve().is_relative_to(root/'app') or not a.out.resolve().is_relative_to(root/'work')):
        raise ValueError('Private plans must stay under untracked work/, never app/ or public evidence')
    doc,payload,plan,audit=run_pipeline(pd.read_csv(a.history),pd.read_csv(a.target),pd.read_csv(a.roles),
        json.loads(a.provenance.read_text()),pd.read_csv(a.pm_input),json.loads(a.bootstrap.read_text()),
        json.loads(a.bps_audit.read_text()),json.loads(a.manager.read_text()) if a.manager else None)
    a.out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('mm.json',doc),('forecast.json',payload),('pm-audit.json',audit)]:
        (a.out/name).write_text(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n')
    if plan is not None:
        # Private output deliberately lives outside public app/artifact paths.
        private=a.out/'private';private.mkdir(mode=0o700,exist_ok=True)
        (private/'plan.json').write_text(json.dumps(plan,allow_nan=False)+'\n')
        (private/'plan.json').chmod(0o600)
    print(json.dumps(register(doc,a.out/'preregistered')))
if __name__=='__main__':main()
