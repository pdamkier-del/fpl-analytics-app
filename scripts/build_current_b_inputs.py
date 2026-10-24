#!/usr/bin/env python3
"""Official current snapshot -> original PR4 role model -> PR8 -> PR9 NUM.

This is an input producer, not a legacy/vNext relabel. It fits the existing
selected bands_h42.0_C1.0 model and applies the existing PR8 carry/cap rules.
The first prospective role ledger has no fabricated pre-injury latent state.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,os,subprocess
import numpy as np
import pandas as pd
from individual_mm_evidence import load_frame
from pr4_individual_mm import role_features,fit_role
from audit_mm_components import prefix_features
from experimental_role_injury_mm import carry_normal_role,bounded_news,medical_fields
from research_individual_mm_refinement import NUM
from current_b_features import prior_features
from fpl_v1_1_model.team_news_history import normalize_team_news
from build_current_mm_roster import build as roster_build,canonical
from capture_mm_prospective import capture
from assemble_current_b_roster import assemble
from audit_capture_io import write_frame

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
WORK=ROOT/'work/live-final-model'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def historical_B_training():
    base=load_frame(ROOT/'work/mm-integration-source/results/predictions.npz')
    base=base[base['mode'].eq('role_chance_return_duration')].copy()
    f=pd.read_csv(ROOT/'analysis/results/individual-mm-refinement-20261016/prior_only_features.csv.gz',float_precision='round_trip')
    key=['season','fixture_uuid','player_uuid'];extra=[c for c in f if c not in base or c in key]
    base=base.merge(f[extra],on=key,validate='one_to_one')
    base['known_at']=pd.to_datetime(base.kickoff_at,utc=True,format='mixed')+pd.to_timedelta(np.where(base.season.eq('2024-25'),4,3),unit='h')
    return base


def current_observations(cut,bootstrap):
    obs=pd.read_csv(BASE/'player_fixture_observations.csv.gz')
    obs['known']=pd.to_datetime(obs.available_at,utc=True);obs['known_at']=obs.known
    obs['kickoff_at']=pd.to_datetime(obs.kickoff_at,utc=True)
    obs=obs[obs.known.lt(cut)].copy()
    obs['pos']=obs.fpl_position.replace({'GKP':'GK','G':'GK'})
    # Exact confirmed provider squad UUIDs; zero-minute roster registrations
    # outside these lineups are not silently interpreted as available benches.
    lu=pd.read_csv(ROOT/'data_v1_1/raw/all-competitions-2026-27/lineups.csv')
    games=[json.loads(x) for x in gzip.open(WORK/'match_actuals.jsonl.gz','rt')]
    game_by_id={g['match_id']:g for g in games if g['tournament']=='prem'}
    # Fixture joins are verified through the canonical current source events.
    event_to_fixture={}
    for mid,g in game_by_id.items():
        teams=lu[lu.match_id.eq(mid)]
        for side,team in teams.groupby('team_side'):
            starters=team[team.is_starting.astype(str).str.lower().isin(['true','1'])]
            if len(starters)!=11 or starters.player_uuid.nunique()!=11:continue
            ids=set(starters.player_uuid.astype(str))
            candidates=obs[obs.player_uuid.isin(ids)&obs.started.eq(1)&obs.kickoff_at.eq(pd.Timestamp(g['kickoff_time']))]
            if len(candidates)!=11 or candidates.fixture_uuid.nunique()!=1:continue
            event_to_fixture[(mid,side)]=candidates.fixture_uuid.iloc[0]
    confirmed=set()
    for (mid,side),fixture in event_to_fixture.items():
        for pid in lu.loc[lu.match_id.eq(mid)&lu.team_side.eq(side),'player_uuid'].dropna():confirmed.add((fixture,str(pid)))
    obs['confirmed_squad']=[(r.fixture_uuid,str(r.player_uuid)) in confirmed for r in obs.itertuples()]
    obs['verified_available']=obs.confirmed_squad|obs.minutes.gt(0)|obs.started.eq(1)
    obs['role_available']=obs.verified_available
    # PR9 uses prior sourced hard-state conflicts to exclude contradictory role
    # evidence. Archived source facts are checked against exact season/GW IDs.
    archive={}
    for path in (WORK/'predeadline_2026_archives').glob('gw*.json'):
        data=json.loads(path.read_text());gw=int(data['evidence']['gw'])
        seen=pd.Timestamp(data['evidence']['snapshot_at_utc'])
        if seen>=cut:continue
        archive[gw]={int(p['id']):p for p in data['players']}
    for i,r in obs.iterrows():
        p=archive.get(int(r.gw),{}).get(int(r.fpl_element))
        if p is not None and int(p['team'])==int(r.team_id):
            state=normalize_team_news(p.get('status'),p.get('news'),p.get('chance_next'))
            if state in ['OUT','SUSPENDED'] and (r.started==1 or r.minutes>0):obs.loc[i,'role_available']=False
            elif state in ['AVAILABLE','RETURNED_AVAILABLE']:obs.loc[i,'role_available']=True
    return obs


def build(out,role_cache,ledger_path=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    role_cache=Path(role_cache)
    meta=json.loads((role_cache/'manifest.json').read_text())
    for name,digest in meta['outputs_sha256'].items():
        if sha(role_cache/name)!=digest:raise ValueError('Role training cache checksum mismatch')
    if not meta['reference_parity_passed']:raise ValueError('Original PR4 role reference not reproduced; cannot call this authentic B')
    feature_gate=json.loads((role_cache/'feature-parity.json').read_text())
    if not feature_gate.get('passed') or feature_gate.get('implementation_sha256')!=sha(ROOT/'scripts/current_b_features.py'):
        raise ValueError('Current NUM feature implementation has not passed the frozen PR9 regression')
    manifest=json.loads((WORK/'source_manifest.json').read_text())
    cut=pd.Timestamp(manifest['observed_at']);origin=int(manifest['target_gw'])
    bootstrap=json.loads((WORK/'bootstrap.json').read_text());fixtures=json.loads((WORK/'fixtures.json').read_text())
    # Collection receipt is the source witness; PM inputs must be from that same
    # completed original rebuild, not a stale forecast paired with new players.
    pm=pd.read_csv(BASE/'vfinal_live_full_simulator_input.csv.gz',low_memory=False,float_precision='round_trip')
    if not pd.to_datetime(pm.cutoff,utc=True).eq(cut).all():raise ValueError('PM source cutoff mismatch')
    pm['gw']=pm.target_gw.astype(int)
    fixture_sources=[s for s in manifest['sources'] if str(s.get('url','')).endswith('/fixtures/')]
    if not fixture_sources:raise ValueError('Missing actual fixture acquisition receipt')
    fixture_at=fixture_sources[-1]['observed_at']
    receipt_at=max(pd.Timestamp(manifest['bootstrap_observed_at']),pd.Timestamp(fixture_at))
    workflow='local-input-rebuild-not-CI-witnessed'
    if os.environ.get('GITHUB_RUN_ID'):
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        workflow=f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}@{revision}"
    receipt=capture(bootstrap,fixtures,observed_at=receipt_at.isoformat(),workflow=workflow)
    skeleton=roster_build(bootstrap,fixtures,receipt,cutoff=cut.isoformat())
    mapping=pm[['fpl_element','player_uuid']].drop_duplicates()
    target=pm[['season','gw','target_gw','fixture_uuid','player_uuid','team_id','pos','cutoff','fpl_element','target_kickoff',
        'p_start','mm_q_sub','start_minutes_mean','mm_sub_minutes','team_news_state','team_news_availability_cap']].copy()
    for dest,src in [('new_p_start','p_start'),('new_start_minutes','start_minutes_mean'),('new_q_sub','mm_q_sub'),('new_sub_minutes','mm_sub_minutes')]:target[dest]=target[src]
    obs=current_observations(cut,bootstrap)
    target=prefix_features(target,obs)
    historic=pd.read_csv(role_cache/'verified_observations.csv.gz',low_memory=False)
    for c in ['known','known_at']:historic[c]=pd.to_datetime(historic[c],utc=True,format='mixed')
    for c in ['known','known_at']:obs[c]=pd.to_datetime(obs[c],utc=True,format='mixed')
    target,_=role_features(target,pd.concat([historic,obs],ignore_index=True),42.)
    train=pd.read_csv(role_cache/'role_training.csv.gz',low_memory=False,float_precision='round_trip')
    train=train[pd.to_datetime(train.outcome_known_at,utc=True,format='mixed').lt(cut)]
    target['p']=fit_role(train,target,1.,'bands');target['p_role']=target.p
    for dest,src in [('s','new_start_minutes'),('q','new_q_sub'),('c','new_sub_minutes')]:target[dest]=target[src]
    official={int(p['id']):p for p in bootstrap['elements']}
    target['news_eligible']=target.gw.eq(origin)
    target['news_state']=[normalize_team_news(official[int(r.fpl_element)].get('status'),official[int(r.fpl_element)].get('news'),official[int(r.fpl_element)].get('chance_of_playing_next_round')) if r.news_eligible else 'UNKNOWN' for r in target.itertuples()]
    target['news_chance']=[official[int(r.fpl_element)].get('chance_of_playing_next_round') if r.news_eligible else np.nan for r in target.itertuples()]
    target['news_effective_at']=np.where(target.news_eligible,manifest['bootstrap_observed_at'],None)
    target['news_medical_out']=[bool(r.news_eligible and medical_fields(dict(raw_news=official[int(r.fpl_element)].get('news'),raw_status=official[int(r.fpl_element)].get('status')))['confirmed_medical_out']) for r in target.itertuples()]
    old=pd.read_csv(ledger_path,low_memory=False) if ledger_path and Path(ledger_path).exists() else target.iloc[:0].copy()
    if len(old):old=old[pd.to_datetime(old.cutoff,utc=True,format='mixed').lt(cut)]
    # Only origin rows update latent availability state. Future fixture rows have
    # UNKNOWN news and must never establish a fictitious known-healthy role.
    target['upstream_s']=target.s
    origin_rows=target[target.gw.eq(origin)].copy()
    if origin_rows.duplicated(['player_uuid','team_id']).any() and (origin_rows.news_eligible&origin_rows.news_state.eq('SUSPENDED')).any():
        raise ValueError('Fixture-scoped suspension evidence required for current DGW')
    raw_old=old.copy()
    if len(raw_old):
        raw_old['p']=raw_old.p_role
        raw_old['s']=raw_old.upstream_s
    # The known current-origin news controls the latent episode. Future UNKNOWN
    # rows must not become the first row of a lexical fixture-ID group.
    carried=carry_normal_role(pd.concat([raw_old,origin_rows],ignore_index=True),True).iloc[len(raw_old):].reset_index(drop=True)
    fields=['normal_role_p','normal_role_s','normal_role_asof']
    normal=carried[['player_uuid','team_id']+fields].drop_duplicates(['player_uuid','team_id'])
    target=target.merge(normal,on=['player_uuid','team_id'],how='left',validate='many_to_one')
    by_key=carried.set_index(['fixture_uuid','player_uuid'])
    for i,row in target[target.gw.eq(origin)].iterrows():
        target.loc[i,'s']=float(by_key.loc[(row.fixture_uuid,row.player_uuid),'s'])
    target=bounded_news(target,chance=True,project=True)
    if target.projection_infeasible.any():raise ValueError('Current availability cannot support a legal expected XI')
    target=target.drop(columns=[c for c in ['history_n','last_started','team_rest_days','minutes_14d'] if c in target])
    target=prior_features(target,obs,old)
    provenance=dict(upstream_variant='role_chance_return_duration',features=NUM,data_at=cut.isoformat(),
        origin_deadline=manifest['deadline'],bootstrap_observed_at=manifest['bootstrap_observed_at'],
        fixtures_observed_at=fixture_at,bootstrap_sha256=hashlib.sha256(canonical(bootstrap)).hexdigest(),
        fixtures_sha256=hashlib.sha256(canonical(fixtures)).hexdigest(),
        source_manifest_sha256=sha(WORK/'source_manifest.json'),source_workflow=receipt['workflow'],
        role_model='PR4 bands_h42.0_C1.0',role_reference_parity=meta['reference_parity'],
        missing_preinjury_latent_state=not len(old),
        source_scopes={'explicit_workload_and_last_start':'Premier League only',
                       'detailed_tactical_role_ledger':'verified all-competition starters',
                       'structured_coach_statements':'not implemented'},
        limitations=['Historical postmatch times retain documented kickoff+3/4h proxies.',
            'Only verified PL histories enter B workload; other-competition load remains outside this fixed model.',
            'First current-season ledger has no invented prior forecast state; unobserved pre-injury duration remains unavailable.'])
    # PM's sources were captured over the collection interval. The completion
    # timestamp can equal cutoff; it is a pre-computation source receipt, not a
    # later information acquisition. Declare its actual earlier fixture fetch.
    # A source must precede cutoff strictly, never manufacture an earlier clock.
    if pd.Timestamp(provenance['fixtures_observed_at'])>=cut:
        raise ValueError('Need actual fixture acquisition clock before cutoff')
    target=assemble(skeleton,mapping,target,provenance)
    history=historical_B_training();history=history[pd.to_datetime(history.known_at,utc=True).lt(cut)]
    for name,frame in [('target.csv.gz',target),('history.csv.gz',history),('pm.csv.gz',pm)]:write_frame(out/name,frame)
    classified=pd.read_csv(BASE/'classified_starters.csv.gz');games={g['match_id']:g for g in [json.loads(x) for x in gzip.open(WORK/'match_actuals.jsonl.gz','rt')]}
    classified['season']='2026-27';classified['fixture_uuid']=classified.match_id;classified['kickoff']=classified.match_id.map(lambda x:games[x]['kickoff_time'])
    classified['competition']=classified.match_id.map(lambda x:games[x]['tournament'])
    classified['round_name']=classified.match_id.map(lambda x:games[x]['round_name'])
    # Preserve actual all-competition minutes and receipt clocks for the
    # separate joint-role candidate. The existing PR4/PR8/PR9 input is unchanged.
    role_events=pd.DataFrame([json.loads(x)for x in gzip.open(WORK/'player_match_events.jsonl.gz','rt')])
    role_events=role_events[role_events.started.eq(True)][['match_id','team_id','player_uuid','minutes_played','available_at']]
    if role_events.duplicated(['match_id','team_id','player_uuid']).any():raise ValueError('Duplicate observed starter event')
    classified=classified.merge(role_events,on=['match_id','team_id','player_uuid'],how='left',validate='one_to_one',suffixes=('','_event'))
    classified=classified.rename(columns={'minutes_played':'minutes'})
    classified['known_at']=pd.concat([pd.to_datetime(classified.available_at,utc=True),pd.to_datetime(classified.available_at_event,utc=True)],axis=1).max(axis=1).astype(str)
    write_frame(out/'roles.csv.gz',classified)
    for name,obj in [('provenance.json',provenance),('bootstrap.json',bootstrap),('fixtures.json',fixtures),('bps-audit.json',json.loads((WORK/'live_bps_source_audit.json').read_text()))]:
        (out/name).write_text(json.dumps(obj,allow_nan=False,indent=2)+'\n')
    ledger_cols=['season','fixture_uuid','player_uuid','team_id','gw','cutoff','pos','p','p_role','upstream_s','s','q','c','x','news_eligible','news_state','news_chance','news_medical_out','news_effective_at']
    ledger=pd.concat([old.reindex(columns=ledger_cols),target[target.gw.eq(origin)][ledger_cols]],ignore_index=True)
    write_frame(out/'role-ledger.csv.gz',ledger)
    report=dict(rows=len(target),players=target.player_uuid.nunique(),fixtures=target.fixture_uuid.nunique(),gws=sorted(target.gw.unique().tolist()),cutoff=cut.isoformat(),upstream_variant=provenance['upstream_variant'],locked_model_active=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'work/current-B-inputs');p.add_argument('--role-cache',type=Path,default=ROOT/'work/current-B-role-training');p.add_argument('--role-ledger',type=Path);a=p.parse_args();build(a.out,a.role_cache,a.role_ledger)
