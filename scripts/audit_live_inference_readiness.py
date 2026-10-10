#!/usr/bin/env python3
"""Verify live 2026/27 data against ALL frozen MM model feature requirements.

Diagnoses source vs actual inference readiness, without fabricating inputs,
touching the frozen MM, or promoting a partial source checkpoint as a forecast.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
from collections import Counter
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from build_reproducible_role_benchmark import BASE_FEATURES,ROLE_FEATURES
from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from fpl_v1_1_model.minutes_decomposition import FEATURES as MINUTE_COMPONENT_FEATURES
from run_v4_three_state_sequence_experiment import BASE_Q_FEATURES,SEQ_FEATURES
from run_v4_performance_rating_experiment import FAMILIES as PERF_FAMILIES
from run_mm_v2_xi_rating_experiment import ASSIGN_FEATURES
from fpl_v1_1_model.rating_history import RATING_FEATURES
from fpl_v1_1_model.role_classifier import ROLES
FILE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/source_feature_matrix.csv.gz'
OUT=ROOT/'work/live-final-model/live_inference_readiness.json'
def audit():
    if not FILE.exists():raise FileNotFoundError('Restore checksum-verified source checkpoint first')
    data=pd.read_csv(FILE,low_memory=False)
    if data.empty:raise ValueError('Empty source features')
    if data.duplicated(['fixture_uuid','player_uuid']).any():
        raise ValueError('Duplicate current roster fixture/player')
    expected=[
        ('start_base',BASE_FEATURES+ROLE_FEATURES+WORKLOAD_FEATURES),
        ('start_performance',PERF_FAMILIES['last']),
        ('cameo_probability',BASE_Q_FEATURES+SEQ_FEATURES),
        ('conditional_duration',MINUTE_COMPONENT_FEATURES+WORKLOAD_FEATURES+SEQ_FEATURES),
        ('relative_XI_rating',ASSIGN_FEATURES),
        ('timing_availability',['team_news_state','team_news_availability_cap',
           'team_news_scoped_chance','cutoff','team_news_source_cutoff']),
        ('conditional_minutes',['start_minutes_mean','cameo_minutes_mean',
                               'p_cameo_given_bench']),
        ('identities',['fixture_uuid','player_uuid','team_id','fpl_element',
                       'gw','target_gw','pos','expected_role']),
    ]
    available=set(data.columns)
    result={'classification':'STRICT_LIVE_MM_FEATURE_READINESS_ONLY','live_certified':False,
        'season':'2026-27','source':str(FILE.relative_to(ROOT)),
        'rows':len(data),'unique_players':int(data.player_uuid.nunique()),
        'fixture_sides':int(data[['fixture_uuid','team_id']].drop_duplicates().shape[0]),
        'gws':sorted(int(x) for x in data.target_gw.dropna().unique()),
        'feature_groups':{},'issues':[]}
    for label,features in expected:
        feats=sorted(set(features))
        missing=sorted(set(feats)-available)
        numeric=[x for x in feats if x in available and x not in {
            'team_news_state','cutoff','team_news_source_cutoff',
            'fixture_uuid','player_uuid','expected_role','pos'}]
        nonfinite={}
        for k in numeric:
            col=pd.to_numeric(data[k],errors='coerce')
            miss=int((~np.isfinite(col)).sum())
            if miss:nonfinite[k]=miss
        result['feature_groups'][label]={'required_columns':len(feats),
            'missing_columns':missing,'nonfinite_columns':nonfinite,
            'complete_for_live':not missing and not nonfinite}
        if missing:result['issues'].append(f'{label}: missing {len(missing)} columns: '+', '.join(missing[:12]))
        if nonfinite:result['issues'].append(f'{label}: nonfinite values: '+', '.join(f'{k}={n}' for k,n in list(nonfinite.items())[:10]))
    # Validate exact frozen assumption: more than 11 possible players per fixture/team
    cohort=data.groupby(['fixture_uuid','team_id']).size()
    weak=cohort[cohort<=11]
    result['cohorts_at_most_11']=len(weak)
    if len(weak):result['issues'].append(f'Insufficient XI cohort sizes: {len(weak)}')
    if 'expected_role' in data:
        result['unknown_expected_role_rows']=int(data.expected_role.astype(str).eq('UNKNOWN').sum())
    if 'team_news_state' in data:
        result['hard_unavailable_rows']=int(data.team_news_state.isin(['OUT','SUSPENDED']).sum())
    # Never confuse target (future, unknown) outcome labels with available historical outcomes.
    if 'y' in data and data.y.notna().any():
        result['issues'].append('Future target contains non-null outcome labels')
    historical=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
    result['historical_training_features_exist']=historical.is_file()
    actual=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz'
    if actual.exists():
        past=pd.read_csv(actual)
        result['actual_completed_player_fixture_rows']=len(past)
        result['actual_completed_gws']=sorted(int(x) for x in past.gw.dropna().unique())
    # Classification is truthful: even complete source features would still need
    # a fitted MM inference run and the downstream frozen PM/TS/chip adapters.
    result['feature_inputs_complete']=not result['issues']
    result['full_frozen_MM_inference_ran']=False
    result['locked_PM_TS_chips_ran']=False
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('LIVE MM FEATURE READINESS',json.dumps({
        'rows':result['rows'],'players':result['unique_players'],
        'gws':result['gws'],'source_complete':result['feature_inputs_complete'],
        'blocks':result['issues'],'groups':{
            k:{'missing':v['missing_columns'],'nonfinite':v['nonfinite_columns']}
            for k,v in result['feature_groups'].items()}
    },ensure_ascii=False),flush=True)
    return result
if __name__=='__main__':audit()
