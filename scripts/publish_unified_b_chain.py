"""One sealed MM→PM forecast for every B view and private TS client."""
import json
from pathlib import Path
from b_chain_contract import VERSION,validate_forecast
from mm_candidate_forecast import seal_document
from export_joint_gk_preview import dump


def synchronize_audit(out,forecast):
    """Audit the canonical forecast, not the retained locked-PM reference."""
    from fpl_v1_1_model.forecast_snapshot import require_snapshot
    require_snapshot(forecast)
    out=Path(out);validate_forecast(forecast)
    rows=[x for p in forecast['players']for w in p['weeks']for x in w['fixtures']]
    if any(abs(sum(x['components'].values())-x['xpts'])>1e-8 for x in rows):
        raise ValueError('Unified point components do not reconcile')
    path=out/'pm-audit.json'
    if path.exists():
        before=json.loads(path.read_text())
        if before.get('model')!=VERSION:
            dump(out/'reference-locked-pm-audit.json',dict(scope='reference_only_not_current_forecast',audit=before))
    audit=dict(model=VERSION,forecast_sha256=forecast['forecast_sha256'],data_asof=forecast['data_asof'],
        minute_sampler=VERSION,MM_to_PM_mean_consistent=True,point_components_reconciled=True,
        max_analytic_minute_difference=max(abs(x['xmins']-x['pm_analytic_minutes'])for x in rows),
        draws_per_fixture=forecast['scenario_contract']['draws'],sample_means_are_finite_MC_estimates=True,
        production_changed=False)
    index=json.loads((out/'index.json').read_text());index['pm_audit_file']='pm-audit.json'
    index['pm_audit_sha256']=dump(path,audit);dump(out/'index.json',index)


def publish(root,forecast,distribution):
    root=Path(root);base=root/'app/mm-preview';out=base/'current'
    validate_forecast(forecast)
    gate=json.loads((root/'analysis/results/unified-b-chain-20261021/validation.json').read_text())
    if not gate['accepted']:raise ValueError('Unified B validation rejected publication')
    index=json.loads((out/'index.json').read_text())
    mm=json.loads((out/'mm.json').read_text())
    moments={(p['fixture_id'],p['player_id']):p for p in distribution['players']}
    for r in mm['players']:
        q=moments[r['fixture_id'],r['player_id']]
        r.update({k:q[k]for k in ['p_start','p_sub_given_not_start','start_minutes','sub_minutes','xmins','p_play','p_60_plus','p_90']})
    if forecast.get('role_assignment'):
        from joint_role_bridge import load_assignment_policy
        role_policy=load_assignment_policy(root,root/'analysis/results/joint-role-candidate-20261022/policy.json')
        evidence=root/'analysis/results/joint-role-candidate-20261022'
        gate={**gate,'joint_role_assignment':dict(policy=role_policy,
            mm=json.loads((evidence/'decision.json').read_text()),
            pm=json.loads((evidence/'pm-decision.json').read_text()))}
        keeper_ids={p['player_uuid']for p in forecast['players']if p['position']==1}
        for a in forecast['gk_team_fixtures']:
            role=a.get('outfield_role_assignment',{})
            if not role.get('applied'):continue
            xi=role['representative_lineup'];selected=dict(zip(xi['players'],xi['roles']))
            squad=[r for r in mm['players']if r['fixture_id']==a['fixture_uuid']and int(r['club_id'])==int(a['team'])]
            keepers=[r for r in squad if r['player_id']in keeper_ids]
            if not keepers:raise ValueError('Representative role XI lacks a known keeper')
            keeper=max(keepers,key=lambda r:r['p_start'])
            for r in squad:
                r['expected_xi']=r['player_id']in selected or r is keeper
                r['formation']=xi['formation'];r['xi_selection_rule']=xi['selection_rule']
                r['slot']=selected.get(r['player_id'],'GK'if r is keeper else None)
                r['slot_index']=xi['players'].index(r['player_id'])+1 if r['player_id']in selected else 0 if r is keeper else None
            for t in mm['teams']:
                if t['fixture_id']==a['fixture_uuid']and int(t['club_id'])==int(a['team']):
                    t.update(formation=xi['formation'],formation_distribution=role['formation_weights'],
                             last_role_known_at=role['max_known_at'],status='joint historical-role assignment distribution',
                             xi_selection_rule=xi['selection_rule'])
        mm['role_assignment']=forecast['role_assignment']
    mm.update(model_version=VERSION,data_at=forecast['data_asof'])
    mm=seal_document(mm)
    index.update(model=VERSION,minute_sampler=VERSION,forecast_sha256=forecast['forecast_sha256'],
        data_asof=forecast['data_asof'],chain_version=VERSION,
        forecast_file_sha256=dump(out/'forecast.json',forecast),mm_file_sha256=dump(out/'mm.json',mm))
    inputs=root/'work/current-B-inputs'
    from build_existing_b_app import source_data
    documents=source_data(json.loads((inputs/'bootstrap.json').read_text()),json.loads((inputs/'fixtures.json').read_text()),
        json.loads((inputs/'provenance.json').read_text()),forecast,mm)
    index['existing_app_data_sha256']=dump(out/'existing-app-data.json',dict(forecast_sha256=forecast['forecast_sha256'],documents=documents))
    index['chain_validation_file']='chain-validation.json'
    index['chain_validation_sha256']=dump(out/'chain-validation.json',gate)
    dump(out/'index.json',index)
    synchronize_audit(out,forecast)
