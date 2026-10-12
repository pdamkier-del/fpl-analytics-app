#!/usr/bin/env python3
"""Compare unchanged frozen MM at original as-of workload vs deadline-projected workload.

Do not alter original MM training, source availability, minutes functions,
model coefficients or live/app artifacts. This changes ONLY known historical
workload decay reference from the snapshot time to each future official
GW deadline, with no future match outcomes or unavailable news.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_current_locked_inputs import readjl
from fpl_v1_1_model.workload import WorkloadHistory,WORKLOAD_FEATURES
from run_locked_live_mm_inference import infer
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
W=ROOT/'work/live-final-model'

def main():
    hist=pd.read_csv(BASE/'reconstructed_training_features.csv.gz',low_memory=False)
    base=pd.read_csv(BASE/'v2_baseline_feature_matrix.csv.gz',low_memory=False)
    orig=pd.read_csv(W/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
    assert len(base)==len(orig)==4002
    assert not base.duplicated(['fixture_uuid','player_uuid']).any()
    official=json.loads((W/'bootstrap.json').read_text())
    deadlines={int(e['id']):pd.Timestamp(e['deadline_time']) for e in official['events']}
    origin=int(base.gw.iloc[0]);observed=pd.Timestamp(base.cutoff.iloc[0])
    games=readjl(W/'match_actuals.jsonl.gz');events=readjl(W/'player_match_events.jsonl.gz')
    assert all(pd.Timestamp(g['available_at'])<observed for g in games)
    bymatch={}
    for v in events:
        if not v.get('player_uuid') or v.get('minutes_played') is None:continue
        bymatch.setdefault((v['match_id'],int(v['team_id'])),{})[str(v['player_uuid'])]=dict(
            started=bool(v['started']),minutes=float(v['minutes_played']))
    wh=WorkloadHistory()
    for m in games:
        keys=[key for key in bymatch if key[0]==m['match_id']]
        for mid,team in keys:
            p=bymatch[(mid,team)]
            wh.add_game(team,mid,pd.Timestamp(m['kickoff_time']),pd.Timestamp(m['available_at']),m['tournament'],
                         p,len(p)>=11)
    assert wh.games and min(deadlines)>0
    original_reference={}
    adjusted_reference={}
    for team in sorted(set(base.team_id.astype(int))):
        original_reference[team]=wh.state(team,observed)
        for gw in sorted(set(base.target_gw.astype(int))):
            deadline=deadlines[gw]
            if deadline<=observed:raise ValueError('Target deadline is already past')
            # No future outcomes: only historical games in CURRENT verified
            # source snapshot are in the workload ledger.
            adjusted_reference[(team,gw)]=wh.state(team,deadline)
    candidate=base.copy()
    original_rows=[]
    future_rows=[]
    for v in base.itertuples():
        team=int(v.team_id);uid=str(v.player_uuid);gw=int(v.target_gw)
        prev,prevbase,_=original_reference[team]
        nextst,nextbase,_=adjusted_reference[(team,gw)]
        one=prev.get(uid,prevbase);two=nextst.get(uid,nextbase)
        original_rows.append(one);future_rows.append(two)
    a=pd.DataFrame(original_rows,index=base.index)
    nextvals=pd.DataFrame(future_rows,index=base.index)
    assert set(WORKLOAD_FEATURES).issubset(set(a)) and set(WORKLOAD_FEATURES).issubset(set(nextvals))
    for c in WORKLOAD_FEATURES:
        val=base[c].to_numpy(float)
        old=a[c].to_numpy(float)
        if not np.allclose(val,old,atol=1e-4,rtol=0):
            err=float(np.max(np.abs(val-old)))
            if err>0.10:raise AssertionError(f'Historical workload reconstruction mismatch {c}: {err}')
        candidate[c]=nextvals[c].to_numpy(float)
    assert all(c in candidate for c in WORKLOAD_FEATURES)
    jo=base[base.player.astype(str).str.contains('João Pedro',case=False,regex=False)]
    jo=jo[jo.team.astype(str).str.lower().eq('chelsea')]
    if len(jo)!=6:raise ValueError('Joao Pedro not uniquely identified across all six GW')
    # The frozen input has no hypothetical future match outcomes.
    assert not candidate[['actual_start','actual_minutes']].notna().any().any()
    updated,qa=infer(hist,candidate)
    baseline=orig[['fixture_uuid','player_uuid','target_gw','fpl_element','player','team','p_start','xmins','start_minutes_mean','mm_q_sub','mm_sub_minutes']].copy()
    new=updated[['fixture_uuid','player_uuid','p_start','xmins','start_minutes_mean','mm_q_sub','mm_sub_minutes']].copy()
    paired=baseline.merge(new,on=['fixture_uuid','player_uuid'],suffixes=('_old','_new'),validate='one_to_one')
    assert len(paired)==len(base)
    paired['d_xmins']=paired.xmins_new-paired.xmins_old
    result=[]
    for v in paired[paired.fpl_element.isin(jo.fpl_element)].sort_values('target_gw').itertuples():
        row=candidate[(candidate.fixture_uuid==v.fixture_uuid)&(candidate.player_uuid==v.player_uuid)].iloc[0]
        o=base[(base.fixture_uuid==v.fixture_uuid)&(base.player_uuid==v.player_uuid)].iloc[0]
        result.append(dict(gw=int(v.target_gw),old_xmins=round(float(v.xmins_old),4),candidate_xmins=round(float(v.xmins_new),4),
                    old_pstart=round(float(v.p_start_old),5),candidate_pstart=round(float(v.p_start_new),5),
                    old_rest_days=round(float(o.work_player_rest_days),3),candidate_rest_days=round(float(row.work_player_rest_days),3),
                    old_work_minutes_7d=round(float(o.work_minutes_7d),2),new_work_minutes_7d=round(float(row.work_minutes_7d),2),
                    gw_deadline=str(deadlines[int(v.target_gw)])))
    top=paired.sort_values('d_xmins',key=lambda v:v.abs(),ascending=False).drop_duplicates('fpl_element').head(25)
    out=dict(classification='ISOLATED_WORKLOAD_REFERENCE_TIME_AB_NOT_LOCKED_MM_PROMOTION',
        historic_observations_used=len(events),observed_snapshot=str(observed),
        compares='only original vs future-deadline workload features changed; training and MM code are identical',
        no_future_target_outcomes=True,origin_gw=origin,
        rows=int(len(paired)),average_delta_xmins=float(paired.d_xmins.mean()),
        max_abs_delta_xmins=float(paired.d_xmins.abs().max()),
        fraction_changed_1min=float((paired.d_xmins.abs()>1).mean()),
        joao_pedro=result,top_changed_players=top[['player','team','target_gw','xmins_old','xmins_new','d_xmins','p_start_old','p_start_new']].round(5).to_dict('records'),
        model_promotion=False,independent_validation_completed=False)
    (W/'joao_mm_workload_deadline_ab.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('JOAO_WORKLOAD_AB_SUMMARY',json.dumps({k:v for k,v in out.items() if k not in ('top_changed_players','joao_pedro')},ensure_ascii=False))
    print('JOAO_WORKLOAD_AB_PLAYER',json.dumps(result,ensure_ascii=False))
    print('JOAO_WORKLOAD_AB_TOP',json.dumps(out['top_changed_players'],ensure_ascii=False))
if __name__=='__main__':main()
