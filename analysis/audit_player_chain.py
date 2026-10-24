"""Read-only audit of every player; coherence is not forecast certification.

Keep current-input receipts separate from later display context. A different
input bundle is never silently substituted for the forecast's hashed inputs.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json

import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(forecast, mm, *, inputs=None, context=None, catalogue=None,
          penalty_evidence=None, policy_root=None):
    players = forecast['players']
    findings = []

    def issue(code, detail, **identity):
        findings.append(dict(code=code, detail=detail, **identity))

    ids = [p['id'] for p in players]
    uids = [p['player_uuid'] for p in players]
    if len(set(ids)) != len(ids) or len(set(uids)) != len(uids):
        issue('duplicate_player_identity', 'Player IDs must be unique.')
    official = {p['id']: p for p in catalogue or []}
    matches = {(p['player_uuid'], q['fixture_uuid']): (p, w, q)
               for p in players for w in p['weeks'] for q in w['fixtures']}
    raw_rows = sum(len(w['fixtures']) for p in players for w in p['weeks'])
    if raw_rows != len(matches):
        issue('duplicate_player_fixture', 'The same player/fixture occurs more than once.')
    mmkeys = [(p['player_id'], p['fixture_id']) for p in mm['players']]
    if len(set(mmkeys)) != len(mmkeys) or set(mmkeys) != set(matches):
        issue('MM_PM_identity_coverage', 'MM and PM must cover identical unique player/fixtures.')
    mmby = {(p['player_id'], p['fixture_id']): p for p in mm['players']}
    if len(matches) != forecast['player_fixture_rows']:
        issue('player_fixture_count', 'Declared player-fixture count differs from unique rows.')

    receipts = {}
    verified = bool(inputs) and bool(forecast.get('input_sha256'))
    for name, expected in forecast.get('input_sha256', {}).items():
        path = Path(inputs) / name if inputs else None
        actual = sha(path) if path is not None and path.is_file() else None
        receipts[name] = dict(expected=expected, actual=actual, matches=actual == expected)
        verified = verified and actual == expected
    if not verified:
        issue('current_input_evidence_unavailable',
              'The exact current input bundle is unavailable or mismatched; detailed feature checks are unknown.')
    target = pd.read_csv(Path(inputs)/'target.csv.gz', low_memory=False,
                         dtype={'player_uuid':str,'fixture_uuid':str}) if verified else None
    targetby = {(r.player_uuid, r.fixture_uuid): r for r in target.itertuples()} if verified else {}
    declared_scopes={}
    if verified:
        try:
            provenance=json.loads((Path(inputs)/'provenance.json').read_text())
            declared_scopes=provenance.get('source_scopes',{})
            if declared_scopes and declared_scopes.get('explicit_workload_and_last_start')!='Premier League only':
                issue('unreviewed_input_scope','Workload source scope changed; the audit and presentation contract require review.')
            if declared_scopes and declared_scopes.get('structured_coach_statements')!='not implemented':
                issue('unreviewed_input_scope','Coach-input scope changed; the audit and presentation contract require review.')
        except (ValueError,TypeError):
            issue('invalid_input_provenance','Hashed provenance is not a valid source declaration.')
    if verified and set(targetby) != set(matches):
        issue('input_target_identity_coverage', 'Verified target and published forecast identities differ.')
    if verified:
        cut=pd.to_datetime(target.cutoff,utc=True,format='mixed').min()
        history=pd.read_csv(Path(inputs)/'history.csv.gz',low_memory=False)
        if 'known_at' in history and pd.to_datetime(history.known_at,utc=True,format='mixed').ge(cut).any():
            issue('training_history_after_origin', 'Training outcomes include information not strictly before the origin.')
        for c in ['y','started','observed_minutes','actual_formation','outcome_known_at']:
            if c in target and target[c].notna().any():
                issue('target_outcome_leakage', 'Target input contains actual outcome data: '+c)
    role_hash = forecast.get('role_assignment', {}).get('role_input_sha256')
    role_path = Path(inputs)/'roles.csv.gz' if inputs else None
    role_verified = bool(role_hash and role_path is not None and role_path.is_file() and sha(role_path)==role_hash)
    roles = pd.read_csv(role_path,low_memory=False) if role_verified else None
    roleby = {uid:g for uid,g in roles.groupby('player_uuid')} if role_verified else {}
    goal_sources={}
    goal_head=forecast.get('nonpenalty_goal_head')
    goal_sources_verified=not bool(goal_head)
    if goal_head:
        base=Path(inputs).parents[1]/'data_v1_1/derived/live_locked_inputs/2026-27-v1' if inputs else None
        for name,expected in goal_head.get('source_sha256',{}).items():
            path=base/(name+'.csv.gz') if base is not None else None
            actual=sha(path) if path is not None and path.is_file() else None
            goal_sources[name]=dict(expected=expected,actual=actual,matches=expected==actual)
        goal_sources_verified=bool(goal_sources) and all(v['matches']for v in goal_sources.values())
        if not goal_sources_verified:
            issue('ordinary_goal_source_evidence_unavailable',
                  'The NP scorer head has additional hashed source tables; its PM input alone is not the complete derivation.')
    goal_derivation_verified=not bool(goal_head)
    if goal_head:
        expected=goal_head.get('goal_head_audit_sha256')
        path=Path(inputs).parent/'joint-gk-current/nonpenalty-goal-head.csv.gz' if inputs else None
        if expected and path is not None and path.is_file() and sha(path)==expected and goal_sources_verified and verified and policy_root:
            try:
                from nonpenalty_goal_bridge import calculate
                modelname=goal_head['policy']['model'];modelpath=Path(policy_root)/modelname
                if sha(modelpath)!=goal_head['policy']['sha256'][modelname]:
                    raise ValueError('Selected ordinary-goal model fingerprint differs')
                frame=pd.read_csv(Path(inputs)/'pm.csv.gz',low_memory=False)
                _,calculated,_=calculate(policy_root,frame,json.loads(modelpath.read_text()),source_root=Path(inputs).parents[1])
                original=pd.read_csv(path,low_memory=False)
                keys=['fixture_uuid','player_uuid'];a=original.set_index(keys).sort_index();b=calculated.set_index(keys).sort_index()
                goal_derivation_verified=(a.index.equals(b.index) and np.allclose(a.ordinary_goal_weight,b.ordinary_goal_weight,atol=1e-12,rtol=1e-12))
                if not goal_derivation_verified:raise ValueError('Ordinary scorer weights cannot be reproduced')
            except (ValueError,KeyError,OSError)as e:
                issue('ordinary_goal_derivation_mismatch',str(e))
        else:
            issue('ordinary_goal_derivation_evidence_unavailable','The published ordinary-goal weights are not linked to a recoverable exact derivation.')
    complete_inputs=verified and (role_verified or not forecast.get('role_assignment')) and goal_sources_verified and goal_derivation_verified

    evidence_ok = None
    if forecast.get('nonpenalty_goal_head') and penalty_evidence is not None:
        policy = forecast['nonpenalty_goal_head']['policy']
        relative = policy['decision']
        expected = policy['sha256'][relative]
        decision_path = Path(policy_root)/relative if policy_root else None
        if decision_path is not None and decision_path.is_file() and sha(decision_path) == expected:
            evidence_ok = (penalty_evidence.get('policy') == policy and
                           penalty_evidence.get('historical') == json.loads(decision_path.read_text()))
            if not evidence_ok:
                issue('published_validation_policy_mismatch',
                      'Published historical evidence differs from the decision pinned by the active policy.')
        else:
            issue('selected_policy_evidence_unavailable', 'Cannot verify the exact selected historical decision.')

    group_rows = defaultdict(list)
    result = []
    contextby = defaultdict(list)
    for r in (context or {}).get('rows', []):
        contextby[r['player_id']].append(r)
    for p in players:
        row = dict(id=p['id'], player_uuid=p['player_uuid'], name=p['name'],
                   team_id=p['team_id'], team=p['team'], position=p['position'],
                   input_evidence_verified=bool(complete_inputs), checks_passed=True,
                   calibration_independently_certified=False, fixtures=[],
                   source_scopes=dict(explicit_B_workload='PL only',
                                      tactical_role_history='verified all-competition starters',
                                      ordinary_goal_short_form='played PL nonpenalty xG only',
                                      assist_performance='existing all-competition performance features',
                                      structured_coach_statements='not implemented'))
        if p['id'] not in official and catalogue is not None:
            issue('catalogue_identity_missing', 'Player absent from the same-snapshot catalogue.', player_id=p['id'])
        elif p['id'] in official:
            o = official[p['id']]
            if int(o['team']) != int(p['team_id']) or int(o['element_type']) != int(p['position']):
                issue('catalogue_identity_mismatch', 'Club or position differs within the snapshot.', player_id=p['id'])
        for w in p['weeks']:
            if abs(w['xpts']-sum(q['xpts'] for q in w['fixtures'])) > 1e-8 or abs(w['xmins']-sum(q['xmins'] for q in w['fixtures'])) > 1e-8:
                issue('fixture_week_aggregation', 'Fixture values do not sum to the gameweek.', player_id=p['id'], gw=w['gw'])
            for q in w['fixtures']:
                key = (p['player_uuid'], q['fixture_uuid'])
                m = mmby.get(key)
                ok = m is not None
                if m is not None:
                    ok = all(abs(m[a]-q[b]) < 1e-7 for a,b in
                             [('xmins','xmins'),('p_start','p_start'),('p_60_plus','p_60_plus'),('p_90','p_90')])
                    mixture = m['p_start']*m['start_minutes']+(1-m['p_start'])*m['p_sub_given_not_start']*m['sub_minutes']
                    ok = ok and abs(mixture-q['xmins']) < 1e-7
                    probabilities=[m[k]for k in ['p_90','p_60_plus','p_play','p_start']]
                    ok = ok and min(probabilities)>=-1e-10 and max(probabilities)<=1+1e-10
                    ok = ok and m['p_90']<=m['p_60_plus']+1e-10 and m['p_60_plus']<=m['p_play']+1e-10
                    ok = ok and m['p_start']<=m['p_play']+1e-10
                if not ok:
                    issue('MM_PM_moment_mismatch', 'Minute probabilities or mixture do not reconcile.', player_id=p['id'], fixture=q['fixture_uuid'])
                row['checks_passed'] = row['checks_passed'] and ok
                if abs(sum(q['components'].values())-q['xpts']) > 1e-8:
                    issue('point_components_mismatch', 'Point components do not reconcile.', player_id=p['id'], fixture=q['fixture_uuid'])
                item = dict(gw=w['gw'], fixture=q['fixture_uuid'], xmins=q['xmins'],
                            p_start=q['p_start'], xp=q['xpts'], minute_contract_passed=ok)
                tr = targetby.get(key)
                if tr is not None:
                    if (hasattr(tr,'fpl_element') and int(tr.fpl_element)!=int(p['id']) or
                        hasattr(tr,'team_id') and int(tr.team_id)!=int(p['team_id']) or
                        hasattr(tr,'pos') and {'GK':1,'GKP':1,'DEF':2,'MID':3,'FWD':4}.get(tr.pos)!=int(p['position'])):
                        issue('input_forecast_identity_mismatch','Input identity/club/position differs from the published player.',player_id=p['id'],fixture=q['fixture_uuid'])
                    for clock in ['max_history_known_at','physical_last_known_at','role_max_known']:
                        value=getattr(tr,clock,None)
                        if value is not None and pd.notna(value) and pd.Timestamp(value)>=pd.Timestamp(tr.cutoff):
                            issue('feature_history_after_origin', 'Feature history is not strictly prior: '+clock,
                                  player_id=p['id'],fixture=q['fixture_uuid'])
                    cap=getattr(tr,'news_chance',None)
                    if getattr(tr,'news_eligible',False) and cap is not None and pd.notna(cap) and m is not None and m['p_play']>float(cap)/100+1e-6:
                        issue('availability_cap_exceeded','Appearance probability exceeds the known availability cap.',player_id=p['id'],fixture=q['fixture_uuid'])
                    item['PL_workload'] = {k: (float(getattr(tr,k)) if pd.notna(getattr(tr,k)) else None)
                                           for k in ['minutes_7d','minutes_14d','rest_days','last_started']}
                    cutoff = pd.Timestamp(tr.cutoff)
                    # This comparison describes completed games visible in the
                    # later display capture, NOT evidence of pre-cutoff ingestion.
                    past = [r for r in contextby[p['id']] if pd.Timestamp(r['kickoff']) < cutoff and r['minutes'] is not None]
                    nonpl = [r for r in past if r['competition'] != 'prem' and r['minutes'] > 0 and
                             pd.Timestamp(r['kickoff']) > cutoff-pd.Timedelta(days=14)]
                    item['non_PL_minutes_14d_in_context'] = sum(r['minutes'] for r in nonpl)
                    item['later_context_is_not_proof_of_model_consumption'] = True
                    item['context_records_first_captured_after_cutoff'] = sum(
                        pd.Timestamp(r['source_observed_at']) >= cutoff for r in nonpl)
                    row['recent_non_PL_minutes'] = max(row.get('recent_non_PL_minutes',0),item['non_PL_minutes_14d_in_context'])
                row['fixtures'].append(item)
                if tr is not None:
                    item['PL_role_history_n'] = float(tr.history_n) if pd.notna(tr.history_n) else None
                    past_roles = roleby.get(p['player_uuid'])
                    if past_roles is not None:
                        prior = past_roles[pd.to_datetime(past_roles.known_at,utc=True,format='mixed').lt(pd.Timestamp(tr.cutoff))]
                        played = prior[pd.to_datetime(prior.kickoff,utc=True,format='mixed').gt(pd.Timestamp(tr.cutoff)-pd.Timedelta(days=14))]
                        item['verified_other_competition_starter_minutes_14d'] = float(played.loc[played.competition.ne('prem'),'minutes'].sum())
                        item['all_competition_starter_ledger_verified'] = True
                group_rows[p['team_id'], q['fixture_uuid']].append((p,w,q))
        result.append(row)

    groups = []
    for (team, fixture), people in sorted(group_rows.items()):
        field = [(p,w,q) for p,w,q in people if p['position'] != 1]
        keepers = [(p,w,q) for p,w,q in people if p['position'] == 1]
        gk = next((g for g in forecast.get('gk_team_fixtures',[]) if int(g['team']) == int(team) and g['fixture_uuid']==fixture), {})
        startmass = sum(q['p_start'] for _,_,q in field)
        gkmass = sum(q['p_start'] for _,_,q in keepers)+gk.get('unlisted_start_probability',0)
        gkmins = sum(q['xmins'] for _,_,q in keepers)+gk.get('unlisted_expected_minutes',0)
        if abs(startmass-10)>1e-7 or abs(gkmass-1)>1e-7 or abs(gkmins-90)>1e-7:
            issue('joint_start_or_GK_coverage', 'Team starter mass or GK minutes are invalid.', team_id=team, fixture=fixture)
        fieldminutes = sum(q['xmins'] for _,_,q in field)
        entry = dict(team_id=team, fixture=fixture, outfield_start_mass=startmass,
                     goalkeeper_start_mass=gkmass, goalkeeper_minutes=gkmins,
                     expected_outfield_minutes=fieldminutes,
                     standard_90_minute_outfield_budget=900,
                     physical_removal_events_exported=False,
                     outfield_budget_reconciled=abs(fieldminutes-900)<1e-7)
        # Week samples are only unambiguous fixture samples in single fixtures.
        if all(len(w['fixtures'])==1 for _,w,_ in field):
            mins = np.asarray([w['scenarios']['minutes'] for _,w,_ in field],float)
            totals = mins.sum(axis=0)
            participants = (mins>0).sum(axis=0)
            entry.update(draws=len(totals), draws_not_900=int((totals!=900).sum()),
                         draws_over_900=int((totals>900).sum()),
                         draws_over_standard_five_sub_limit=int((participants>15).sum()),
                         max_outfield_participants=int(participants.max()),
                         minimum_total_minutes=float(totals.min()), maximum_total_minutes=float(totals.max()))
        else:
            entry['fixture_sample_check']='unavailable: gameweek contains multiple fixtures'
        if (not entry['outfield_budget_reconciled'] or entry.get('draws_not_900',0) or
                entry.get('draws_over_standard_five_sub_limit',0)):
            issue('outfield_physical_coherence', 'Outfield minutes/substitutions are not a joint physical process.', team_id=team, fixture=fixture)
        groups.append(entry)
    codes = Counter(r['code'] for r in findings)
    physical = {(g['team_id'],g['fixture']):(g['outfield_budget_reconciled'] and
                not g.get('draws_not_900',0) and not g.get('draws_over_standard_five_sub_limit',0))
                if 'draws' in g else None for g in groups}
    for row in result:
        states=[physical[row['team_id'],q['fixture']] for q in row['fixtures']]
        row['physical_team_minutes_verified'] = False if False in states else None if None in states or not states else True
        row['individual_numerical_checks_passed'] = not any(
            i.get('player_id')==row['id'] for i in findings)
        row['quality_status'] = 'not_independently_validated'
    structural = {'duplicate_player_identity','duplicate_player_fixture','MM_PM_identity_coverage','player_fixture_count',
                  'catalogue_identity_missing','catalogue_identity_mismatch','fixture_week_aggregation',
                  'MM_PM_moment_mismatch','point_components_mismatch','joint_start_or_GK_coverage',
                  'training_history_after_origin','target_outcome_leakage','feature_history_after_origin','availability_cap_exceeded'}
    structural.add('input_forecast_identity_mismatch')
    structural.update(['unreviewed_input_scope','invalid_input_provenance'])
    return dict(schema='B-all-player-chain-audit-v1', forecast_sha256=forecast['forecast_sha256'],
                auditor_code_sha256=sha(__file__),declared_input_scopes=declared_scopes,
                data_asof=forecast['data_asof'], reviewed_at=datetime.now(timezone.utc).isoformat(),
                players_audited=len(players), player_fixture_rows=len(matches),
                technical_moment_contract_passed=not bool(structural & codes.keys()),
                full_model_certification=False, source_input_evidence_verified=verified,
                all_competition_role_ledger_verified=role_verified,
                all_model_source_evidence_verified=bool(complete_inputs),
                ordinary_goal_source_evidence_verified=goal_sources_verified,
                ordinary_goal_derivation_verified=bool(goal_derivation_verified),
                source_linkage_passed=bool(complete_inputs and (evidence_ok is True if goal_head else True) and not(structural & codes.keys())),
                ordinary_goal_source_receipts=goal_sources,
                published_selected_historical_evidence_matches=evidence_ok,
                calibrated_player_probabilities_claimed=False,
                source_receipts=receipts, finding_counts=dict(codes), findings=findings,
                players=result, team_fixtures=groups,
                limitations=['Completed context captured after an origin cannot prove what that model knew.',
                             '900 outfield minutes and five substitutions assume a standard match without explicit removal/exception events.',
                             'No per-fixture sample check is inferred from aggregated double-gameweek samples.',
                             'Mathematical coherence is not statistical calibration or personal transfer-plan validation.'],
                production_changed=False, private_user_state_used=False)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--inputs',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--require-source-linkage',action='store_true')
    a=p.parse_args();load=lambda n:json.loads((a.capture/n).read_text())
    f=load('current/forecast.json');index=load('current/index.json')
    from fpl_v1_1_model.forecast_snapshot import require_snapshot
    from b_chain_contract import validate_forecast
    require_snapshot(f);validate_forecast(f)
    if index['forecast_sha256']!=f['forecast_sha256'] or sha(a.capture/'current/forecast.json')!=index['forecast_file_sha256']:
        raise ValueError('Capture does not match sealed index')
    if sha(a.capture/'current/mm.json')!=index['mm_file_sha256']:
        raise ValueError('MM checksum mismatch')
    if sha(a.capture/'current/existing-app-data.json')!=index['existing_app_data_sha256']:
        raise ValueError('Catalogue checksum mismatch')
    if load('current/existing-app-data.json')['forecast_sha256']!=f['forecast_sha256']:
        raise ValueError('Catalogue belongs to a different forecast')
    context=None
    if (a.capture/'match-context/index.json').exists():
        ci=load('match-context/index.json');file=a.capture/'match-context'/ci['file']
        if sha(file)!=ci['sha256']:raise ValueError('Context checksum mismatch')
        context=json.loads(file.read_text())
    evidence=load('gk/nonpenalty-evidence.json') if (a.capture/'gk/nonpenalty-evidence.json').exists() else None
    catalogue=load('current/existing-app-data.json')['documents']['current-players.json']['players']
    report=audit(f,load('current/mm.json'),inputs=a.inputs,context=context,catalogue=catalogue,
                 penalty_evidence=evidence,policy_root=Path(__file__).resolve().parents[1])
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (a.out/'index.json').write_text(json.dumps(dict(schema='B-all-player-chain-audit-index-v1',
        forecast_sha256=f['forecast_sha256'],file='audit.json',sha256=sha(a.out/'audit.json'),
        players=report['players_audited'],data_asof=f['data_asof']),sort_keys=True)+'\n')
    summary={k:v for k,v in report.items() if k not in ['players','team_fixtures','findings']}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (a.out/'players.csv').open('w') as h:
        cols=['id','name','team','position','input_evidence_verified','checks_passed','calibration_independently_certified','recent_non_PL_minutes']
        w=csv.DictWriter(h,fieldnames=cols,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(report['players'])
    print(json.dumps({k:report[k] for k in ['forecast_sha256','players_audited','player_fixture_rows','technical_moment_contract_passed','source_input_evidence_verified','finding_counts','full_model_certification']},indent=2))
    if a.require_source_linkage and not report['source_linkage_passed']:
        raise ValueError('Fresh player-source linkage gate failed; see input-audit findings')


if __name__=='__main__':main()
