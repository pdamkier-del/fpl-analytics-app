#!/usr/bin/env python3
"""Publish cutoff-matched frozen vs optional MM-vNext comparison ONLY.

This is an experimental MM shadow forecast. The original final-vFinal
xP, TS, and publicly certified indicators remain 100% untouched.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
W=ROOT/'work/live-final-model'
APP=ROOT/'app'

def main():
    manifest=json.loads((W/'source_manifest.json').read_text())
    receipt=json.loads((W/'mm_inference_vnext_experimental_six_gw.json').read_text())
    if receipt.get('classification')!='EXPERIMENTAL_MEDICAL_RETURN_MM_VNEXT_NOT_FINAL':
        raise ValueError('Not an experimental MM vNext source')
    if receipt.get('medical_return_logit')!=0.4 or receipt.get('live_certified') is not False:
        raise ValueError('Unverified experimental configuration')
    original=pd.read_csv(W/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
    candidate=pd.read_csv(W/'mm_vnext_experimental_six_gw.csv.gz',low_memory=False)
    keys=['fixture_uuid','player_uuid','target_gw','team_id','fpl_element']
    if original.duplicated(keys).any() or candidate.duplicated(keys).any():
        raise ValueError('Nonunique MM player fixture rows')
    if not set(keys).issubset(original) or not set(keys).issubset(candidate):
        raise ValueError('Missing forecast identities')
    if len(original)!=len(candidate):raise ValueError('MM forecast cardinality mismatch')
    join=original.merge(candidate,on=keys,validate='one_to_one',suffixes=('_locked','_vnext'),indicator=True)
    if not join._merge.eq('both').all():raise ValueError('MM identity join mismatch')
    if not join.target_gw.between(int(manifest['target_gw']),int(manifest['target_gw'])+5).all():
        raise ValueError('Mismatch with official forecast horizon')
    if join.target_gw.nunique()!=6:raise ValueError('Incomplete six GW comparison')
    if len(join)!=667*6:raise ValueError('Missing live-roster forecast rows')
    if (join.groupby('target_gw').fpl_element.nunique()!=667).any():
        raise ValueError('Incomplete per-round player IDs')
    for tag in ['locked','vnext']:
        probability=join['p_start_'+tag].to_numpy(float)
        minutes=join['xmins_'+tag].to_numpy(float)
        if not np.isfinite(probability).all() or not np.isfinite(minutes).all():
            raise ValueError('Nonfinite probabilities/minutes')
        if (probability<-1e-8).any() or (probability>1+1e-8).any() or (minutes<-1e-8).any() or (minutes>90.01).any():
            raise ValueError('MM predicted minutes/probability out of bounds')
        pergroup=join.groupby(['target_gw','fixture_uuid','team_id'])['p_start_'+tag].sum()
        if float((pergroup-11).abs().max())>1e-6:
            raise ValueError('Exact XI expectation failed: '+tag)
    flagged=join.medical_return_vnext.fillna(False).astype(bool)
    if int(flagged.sum())!=6*int(receipt['medically_documented_returner_count']):
        raise ValueError('Inconsistent medical-return flags across six-GW horizon')
    if (join['team_news_state_vnext'][join.target_gw!=int(manifest['target_gw'])]!='UNKNOWN').any():
        raise ValueError('Current GW source news illegally copied into future')
    # Strict no-hard-out xM rule is already respected by checkpoint original;
    # this comparison also refuses to publish a positive xM for a hard-out player.
    current=join.target_gw.eq(int(manifest['target_gw']))
    hard=current & join.team_news_state_locked.isin(['OUT','SUSPENDED'])
    if (join.loc[hard,'xmins_vnext']>1e-9).any():
        raise ValueError('Hard-out player forecast minutes must be zero')
    rows=[]
    for r in join.itertuples(index=False):
        rows.append(dict(
            gw=int(r.target_gw),id=int(r.fpl_element),name=str(r.player_locked),
            team=str(r.team_locked),team_id=int(r.team_id),
            role=str(r.expected_role_locked),
            medical_return=bool(r.medical_return_vnext),
            current_available=str(r.team_news_state_locked),
            locked_p_start=round(float(r.p_start_locked),6),
            vnext_p_start=round(float(r.p_start_vnext),6),
            locked_xmins=round(float(r.xmins_locked),4),
            vnext_xmins=round(float(r.xmins_vnext),4),
            delta_xmins=round(float(r.xmins_vnext-r.xmins_locked),4)
        ))
    changed=[r for r in rows if abs(r['delta_xmins'])>=1]
    jp=[r for r in rows if int(r['id'])==165]
    latest=json.loads((APP/'vfinal-diagnostic.json').read_text())
    if latest['data_asof']!=manifest['observed_at']:
        raise ValueError('Original xP and vNext source timestamps differ')
    result=dict(
        classification='EXPERIMENTAL_MEDICAL_RETURN_MM_VNEXT_COMPARE_NOT_FINAL',
        model_math_changed=True,
        locked_model_active=False,
        final_chain_certified=False,
        production_xp_unchanged=True,
        current_xp_from_original_frozen_vfinal=True,
        medical_return_logit=0.4,
        source_observed_at=manifest['observed_at'],
        baseline_model='unchanged locked original MM',
        model='MM-vNext medical recovery before exact-XI selection',
        origin_gw=int(manifest['target_gw']),
        gws=sorted(map(int,join.target_gw.unique())),
        players_per_gw=667,
        player_week_rows=len(rows),
        medically_returned_players=int(receipt['medically_documented_returner_count']),
        medically_returned_ids=receipt['medically_documented_returner_fpl_ids'],
        impacted_player_weeks_at_least_1_min=len(changed),
        joao_pedro=jp,
        restrictions=['Only medical return +0.4 logit tested in development and chosen before historical diagnostic',
                      'No unverified tactical-substitution exception integrated',
                      'Original PM xP and TS remain unchanged; MM vNext is a diagnostic comparison',
                      'Future GWs use the origin known-return evidence; no future return/match results are invented',
                      'This does not certify live historical reconstruction or season-independent improvement'],
        rows=rows)
    APP.joinpath('mm-vnext-6gw.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False))
    print('MM_VNEXT_SHADOW_RELEASE',json.dumps(dict(gws=result['gws'],rows=len(rows),returned_ids=result['medically_returned_ids'],
         affected=len(changed),joao=jp,source=result['source_observed_at']),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
