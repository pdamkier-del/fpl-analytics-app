#!/usr/bin/env python3
"""Export validated public GK evidence only; no private TS plan/state files."""
from pathlib import Path
import hashlib,json
import pandas as pd
from gk_joint_bridge import VERSION
from mm_locked_bridge import locked_sampler_expectation
from fpl_v1_1_model.forecast_snapshot import require_snapshot
ROOT=Path(__file__).resolve().parents[1]

def dump(path,value):
    b=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();path.write_bytes(b)
    return hashlib.sha256(b).hexdigest()


def selected_nonpenalty_evidence(root, policy):
    """Export the policy's exact decision, never an older similarly named fit."""
    root=Path(root).resolve()
    name=policy.get('decision','')
    path=(root/name).resolve()
    expected=policy.get('sha256',{}).get(name)
    if policy.get('approved') is not True or not path.is_relative_to(root) or not expected:
        raise ValueError('Missing selected NP decision receipt')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError('Selected NP historical decision checksum mismatch')
    decision=json.loads(path.read_text())
    if decision.get('passed') is not True:
        raise ValueError('Selected NP historical decision failed')
    return dict(policy=policy,historical=decision,historical_decision_file=name,
                historical_decision_sha256=expected,production_changed=False,
                predictive_accuracy_improvement_claimed=False)

def export():
    source=ROOT/'work/joint-gk-current';repeat=ROOT/'work/joint-gk-repeat';out=ROOT/'app/mm-preview/gk';out.mkdir(exist_ok=True)
    for file in ['forecast.json','gk-mm.json','gk-audit.json']:
        if (source/file).read_bytes()!=(repeat/file).read_bytes():raise ValueError('Joint GK repeat differs: '+file)
    forecast=json.loads((source/'forecast.json').read_text());require_snapshot(forecast)
    mm=json.loads((source/'gk-mm.json').read_text());audit=json.loads((source/'gk-audit.json').read_text())
    from b_chain_contract import VERSION as CHAIN_VERSION,validate_forecast
    unified=forecast['model']==CHAIN_VERSION
    if unified:validate_forecast(forecast)
    if forecast['model']not in (VERSION,CHAIN_VERSION) or not audit['point_components_reconciled']:raise ValueError('GK model gate failed')
    historical=json.loads((ROOT/'work/joint-gk-historical/summary.json').read_text())
    uncertainty=json.loads((ROOT/'work/joint-gk-historical/uncertainty.json').read_text())
    stages=json.loads((source/'stage-validation.json').read_text());ts=json.loads((source/'ts-validation.json').read_text())
    if not historical['all_team_gk_minutes_90'] or not stages['passed'] or not ts['ts_ran']:raise ValueError('GK validation missing')
    baseline=json.loads((source/'baseline-mm.json').read_text())['players']
    points=pd.read_csv(source/'paired-baseline.csv.gz').set_index(['fixture_uuid','player_uuid'])
    before=[]
    for r in baseline:
        k=(r['fixture_id'],r['player_id']);p=points.loc[k]
        before.append(dict(fixture_uuid=k[0],player_uuid=k[1],p=r['p_start'],xm=r['xmins'],pm=float(locked_sampler_expectation(r['p_start'],r['p_sub_given_not_start'],r['start_minutes'],r['sub_minutes'])),sampled_pm=float(p.minutes),xp=float(p.xpts)))
    index=dict(model=forecast['model'],forecast_sha256=dump(out/'forecast.json',forecast),mm_sha256=dump(out/'gk-mm.json',mm),before_sha256=dump(out/'before.json',dict(players=before)))
    role=json.loads((ROOT/'work/joint-gk-role-validation/summary.json').read_text())
    if not role['accepted']or not role['all_gk_team_minutes_90']or not role['pm_all_gk_minutes_90']:raise ValueError('Role correction validation gate failed')
    v1=json.loads((source/'before-v1.json').read_text())
    index['before_v1_sha256']=dump(out/'before-v1.json',dict(model='B-GK-joint-empirical-v1',**v1))
    index['evidence_sha256']=dump(out/'evidence.json',dict(role_validation=role,model=VERSION,v1_reference_historical=historical,v1_reference_uncertainty=uncertainty,stages=stages,ts=ts,
        deterministic_repeat=True,production_changed=False,intervals_independently_certified=False,
        official_sources=forecast['official_gk_evidence']))
    if forecast.get('role_assignment'):
        control=json.loads((source/'role-control.json').read_text())
        if not control['goalkeeper_marginals_unchanged']or not control['same_source_and_seeds']:
            raise ValueError('Joint role current comparison is not matched')
        index['role_control_sha256']=dump(out/'role-control.json',dict(forecast_sha256=forecast['forecast_sha256'],**control))
        evidence=ROOT/'analysis/results/joint-role-candidate-20261022'
        index['outfield_role_evidence_sha256']=dump(out/'outfield-role-evidence.json',dict(policy=forecast['role_assignment'],
            mm=json.loads((evidence/'decision.json').read_text()),pm=json.loads((evidence/'pm-decision.json').read_text()),
            model_source='same sealed B forecast; production unchanged'))
    if forecast.get('nonpenalty_goal_head'):
        control=json.loads((source/'nonpenalty-control.json').read_text())
        if not control['all_MM_marginals_unchanged']or not control['same_source_and_seeds']:raise ValueError('NP head current control missing')
        index['nonpenalty_control_sha256']=dump(out/'nonpenalty-control.json',dict(forecast_sha256=forecast['forecast_sha256'],**control))
        index['nonpenalty_evidence_sha256']=dump(out/'nonpenalty-evidence.json',selected_nonpenalty_evidence(ROOT,forecast['nonpenalty_goal_head']['policy']))
    dump(out/'index.json',index)
    if unified:
        from publish_unified_b_chain import publish
        publish(ROOT,forecast,mm)
    from integrate_desktop_probabilities import integrate
    integrate(ROOT)
    print(json.dumps(index,indent=2))
if __name__=='__main__':export()
