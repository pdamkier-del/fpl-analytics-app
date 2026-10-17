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
from mm_candidate_forecast import infer_B,register,seal_document
from mm_locked_bridge import attach_mm,run_current_ts,code_identity,locked_sampler_expectation
from run_live_vfinal_joint_simulation import simulate
from build_live_vfinal_desktop import build


def run_pipeline(history,target,roles,provenance,pm,bootstrap,bps_audit,manager=None,*,fixtures,minute_sampler='locked'):
    from fpl_v1_1_model.forecast_snapshot import seal_forecast
    if minute_sampler not in ('locked','candidate_B'):
        raise ValueError('Unknown MM-to-PM sampler')
    if minute_sampler!='locked' and manager is not None:
        raise ValueError('Unvalidated candidate minute sampler cannot create personal TS recommendations')
    now=pd.Timestamp.now(tz='UTC')
    cut=pd.Timestamp(provenance['data_at'])
    if cut.tzinfo is None or cut>now or now-cut>pd.Timedelta(hours=24):
        raise ValueError('Current input freshness expired')
    deadline=pd.Timestamp(provenance['origin_deadline'])
    if deadline<=now:raise ValueError('Official forecast deadline expired')
    if not pd.to_datetime(target.cutoff,utc=True).eq(cut).all():raise ValueError('Feature cutoff mismatch')
    for name,obj in [('bootstrap',bootstrap),('fixtures',fixtures)]:
        digest=hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if provenance.get(name+'_sha256')!=digest:raise ValueError('Official source checksum mismatch: '+name)
        observed=pd.Timestamp(provenance[name+'_observed_at'])
        if observed.tzinfo is None or observed>=cut:raise ValueError('Official source observed after cutoff')
    if set(target.season)!={'2026-27'}:raise ValueError('Wrong current season')
    event=next(e for e in bootstrap['events'] if e.get('is_next'))
    if pd.Timestamp(event['deadline_time'])!=deadline:raise ValueError('Official deadline mismatch')
    gws=list(range(int(event['id']),min(39,int(event['id'])+6)))
    if sorted(set(target.gw))!=gws:raise ValueError('Missing full six-GW target inputs')
    if (target.gw.gt(gws[0])&target.news_eligible).any():raise ValueError('Current GW news cap reused in future GW')
    schedule={f'live-2026-27-fpl-{int(f["id"])}':f for f in fixtures if f.get('event') in gws}
    if set(pm.fixture_uuid)!=set(schedule):raise ValueError('Official six-GW fixture coverage mismatch')
    for fx,g in pm.groupby('fixture_uuid'):
        f=schedule[fx]
        if f.get('started') or not f.get('kickoff_time'):raise ValueError('Started/undated target fixture')
        if not g.gw.eq(f['event']).all() or not g.home_team_id.eq(f['team_h']).all() or not g.away_team_id.eq(f['team_a']).all():
            raise ValueError('Official fixture identity mismatch')
        if not pd.to_datetime(g.target_kickoff,utc=True).eq(pd.Timestamp(f['kickoff_time'])).all():
            raise ValueError('Official kickoff mismatch')
    # Explicit source membership per fixture, not merely equal table lengths.
    official={int(p['id']):p for p in bootstrap['elements']}
    if pm.duplicated(['fixture_uuid','fpl_element']).any():raise ValueError('Duplicate FPL identity')
    mapping=pm[['fpl_element','player_uuid']].drop_duplicates()
    if mapping.fpl_element.duplicated().any() or mapping.player_uuid.duplicated().any():raise ValueError('Ambiguous FPL/UUID mapping')
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
    ids=pm[['player_uuid','fpl_element']].drop_duplicates().set_index('player_uuid').fpl_element.to_dict()
    names={int(t['id']):t['name'] for t in bootstrap['teams']}
    for row in doc['players']:
        pid=int(ids[row['player_id']]);row.update(fpl_element=pid,name=official[pid]['web_name'],club=names[row['club_id']])
    root=Path(__file__).resolve().parents[1]
    doc['code_sha256']=code_identity(root)
    for name in ['mm_candidate.py','mm_candidate_forecast.py','research_individual_mm_refinement.py','mm_locked_bridge.py','run_mm_locked_preview.py']:
        doc['code_sha256']['scripts/'+name]=hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest()
    doc=seal_document(doc)
    joined=attach_mm(pm,predicted)
    if not joined.target_gw.eq(joined.gw).all():raise ValueError('PM target GW mismatch')
    xp,audit=simulate(joined,minute_sampler=minute_sampler)
    # Analytical expectation must correspond to the selected duration kernel.
    if minute_sampler=='candidate_B':
        means=joined.v4_workload_start_xmins.to_numpy(float).copy()
    else:
        means=locked_sampler_expectation(joined.v4_workload_start_p_start,joined.v4_p_cameo_given_bench,
            joined.v4_start_minutes_mean,joined.v4_cameo_minutes_mean)
    audit['MM_to_PM_mean_max_abs_difference']=float(np.max(np.abs(means-joined.v4_workload_start_xmins)))
    audit['MM_to_PM_mean_consistent']=bool(audit['MM_to_PM_mean_max_abs_difference']<=1e-6)
    audit['MM_to_PM_mean_basis']='exact B conditional PMF' if minute_sampler=='candidate_B' else 'original clipped Gaussian'
    # Display/export exposure is B. Simulator propensities were calculated from
    # untouched PM controls; export must not falsely label those controls as B.
    display=joined.copy()
    for src,dest in [('v4_workload_start_p_start','control_p_start'),
                     ('v4_workload_start_xmins','control_xmins'),
                     ('v4_p_cameo_given_bench','p_cameo_given_bench')]:display[dest]=display[src]
    # The unchanged desktop exporter names the prediction column with _sim
    # when a source expectation exists. Make that contract explicit rather
    # than depending on an incidental upstream column.
    display['expected_minutes']=display.control_xmins
    display['live_eligibility_applied']=display.v4_workload_start_p_start.eq(0)&display.v4_p_cameo_given_bench.eq(0)
    payload=build(display,xp,bootstrap,bps_audit)
    payload['minute_sampler_audit']={k:v for k,v in audit.items() if k.startswith('MM_to_PM_')}
    payload['minute_sampler_audit']['sampler']=minute_sampler
    if minute_sampler!='locked':
        payload['blockers'].append('Experimental candidate B minute distribution: historical calibration gate not passed; no live TS activation.')
    if minute_sampler=='locked' and not audit['MM_to_PM_mean_consistent']:
        payload['blockers'].append('Locked PM rounded/clipped duration sampler does not preserve B conditional means; integration remains diagnostic. No silent PM sampler replacement.')
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
    if pd.Timestamp.now(tz='UTC')>=deadline:raise ValueError('Deadline passed during computation; discard result')
    return doc,payload,plan,audit


def main():
    p=argparse.ArgumentParser()
    for n in ['history','target','roles','provenance','pm-input','bootstrap','fixtures','bps-audit','out']:
        p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--manager',type=Path)
    p.add_argument('--minute-sampler',choices=['locked','candidate_B'],default='locked')
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if a.manager and (a.out.resolve().is_relative_to(root/'app') or not a.out.resolve().is_relative_to(root/'work')):
        raise ValueError('Private plans must stay under untracked work/, never app/ or public evidence')
    doc,payload,plan,audit=run_pipeline(pd.read_csv(a.history),pd.read_csv(a.target),pd.read_csv(a.roles),
        json.loads(a.provenance.read_text()),pd.read_csv(a.pm_input),json.loads(a.bootstrap.read_text()),
        json.loads(a.bps_audit.read_text()),json.loads(a.manager.read_text()) if a.manager else None,fixtures=json.loads(a.fixtures.read_text()),minute_sampler=a.minute_sampler)
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
