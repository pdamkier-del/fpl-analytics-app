#!/usr/bin/env python3
"""Read-only application of *historical development-selected* medical-recovery
logit shift (0.8) to GW7 frozen MM. Only known earlier outcomes and predeadline
Team News can flag returners. NOT a full live re-fit, PM or TS recalculation.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit,logit
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
W=ROOT/'work/live-final-model'
MED={'OUT','SUSPENDED','DOUBT','MAJOR_DOUBT'}
READY={'AVAILABLE','RETURNED_AVAILABLE'}

def main():
    mm=pd.read_csv(W/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
    origin=int(mm.target_gw.min())
    mm=mm[mm.target_gw.eq(origin)].copy().reset_index(drop=True)
    training=pd.read_csv(B/'reconstructed_training_features.csv.gz',low_memory=False)
    historic=pd.read_csv(B/'player_fixture_observations.csv.gz',low_memory=False)
    current=mm[['fixture_uuid','team_id','player_uuid','fpl_element','player','team','pos','p_start','mm_q_sub','mm_sub_minutes','start_minutes_mean','xmins','team_news_state','team_news_availability_cap']].copy()
    if current.duplicated(['fixture_uuid','player_uuid']).any() or len(current)!=667:
        raise ValueError('Current diagnostic roster/fixture identity issue')
    prior_news={(int(r.gw),str(r.player_uuid)):str(r.team_news_state)
                for r in training.itertuples(index=False)}
    observed={}
    for pid,g in historic.groupby('player_uuid'):
        # One game per round; ambiguous future double GW sources ignored.
        m=g.groupby('gw').size()
        observed[str(pid)]={int(r.gw):dict(start=int(r.started),minutes=float(r.minutes))
           for r in g.itertuples(index=False) if m.loc[r.gw]==1 and int(r.gw)<origin}
    flagged=[];categories=[]
    for r in current.itertuples(index=False):
        key=str(r.player_uuid)
        past=observed.get(key,{})
        recent=past.get(origin-1);before=past.get(origin-2)
        historic_starts=sum(int(past.get(origin-j,{}).get('start',0)) for j in range(3,7))
        prev_news=prior_news.get((origin-2,key),'UNKNOWN')
        now=str(r.team_news_state)
        is_return=bool(recent and before and recent['start']==1 and
            before['minutes']==0 and historic_starts>=2 and prev_news in MED and now in READY)
        is_post_zero=(recent is not None and before is not None
                      and recent['start']==1 and before['minutes']==0)
        label=('RECOVERED_AFTER_CONFIRMED_UNAVAILABLE' if prev_news in {'OUT','SUSPENDED'} else
               'RECOVERED_AFTER_MEDICAL_DOUBT' if prev_news in {'DOUBT','MAJOR_DOUBT'} else
               'PREVIOUS_ABSENCE_NOT_MEDICALLY_DOCUMENTED') if is_post_zero else 'NO_RECENT_RETURN'
        flagged.append(is_return);categories.append(label)
    current['medical_returner']=flagged
    current['classification']=categories
    if sum(flagged)<1:raise AssertionError('No medically evidenced returning starters in current GW')
    c=current.team_news_availability_cap.to_numpy(float)
    old=current.p_start.to_numpy(float)
    baseline=project_exact_starters_with_caps(current,old,c)
    candidate=project_exact_starters_with_caps(current,
        expit(logit(np.clip(old,1e-8,1-1e-8))+.8*current.medical_returner.to_numpy(float)),c)
    current['base_pstart']=baseline
    current['medical_candidate_pstart']=candidate
    branch=current.mm_q_sub.to_numpy(float)*current.mm_sub_minutes.to_numpy(float)
    start=current.start_minutes_mean.to_numpy(float)
    oldxm=baseline*start+(1-baseline)*branch
    newxm=candidate*start+(1-candidate)*branch
    oldxm=np.where(c==0,0.,oldxm);newxm=np.where(c==0,0.,newxm)
    current['base_xmins']=oldxm;current['candidate_xmins']=newxm
    current['p_start_delta']=candidate-baseline
    current['xmins_delta']=newxm-oldxm
    maxerr=float(np.max(abs(oldxm-current.xmins.to_numpy(float))))
    # The zero substitute gate for hard-out is present in the final published
    # app PM inputs, not in this raw frozen MM, so non-hard rows must match.
    mask=c>0
    err_nonhard=float(np.max(abs(oldxm[mask]-current.xmins.to_numpy(float)[mask])))
    if err_nonhard>.1:raise AssertionError(f'Frozen reference mismatch: {err_nonhard}')
    assert np.isfinite(current[['base_xmins','candidate_xmins']].to_numpy(float)).all()
    assert ((current.candidate_xmins>=0)&(current.candidate_xmins<=90.001)).all()
    assert (current.groupby(['fixture_uuid','team_id']).medical_candidate_pstart.sum()-11).abs().max()<1e-6
    pid=165
    player=current[current.fpl_element.eq(pid)]
    if len(player)!=1:raise ValueError('Joao Pedro FPL ID missing in original GW checkpoint')
    jp=player.iloc[0]
    report=dict(classification='READ_ONLY_GW7_MEDICAL_RETURNER_PSTART_AB_NOT_PRODUCTION',
      origin_gw=origin,eligible_count=int(current.medical_returner.sum()),
      detected=[dict(id=int(x.fpl_element),player=x.player,team=x.team,
           cause=x.classification,pstart_before=round(float(x.base_pstart),4),
           pstart_candidate=round(float(x.medical_candidate_pstart),4),
           xmins_before=round(float(x.base_xmins),3),
           xmins_candidate=round(float(x.candidate_xmins),3))
           for x in current[current.medical_returner].itertuples(index=False)],
      joao_pedro=dict(id=pid,previous_gw=origin-1,missed_gw=origin-2,
           predeadline_gw5_status=prior_news.get((origin-2,str(jp.player_uuid)),'UNKNOWN'),
           current_state=jp.team_news_state,
           old_pstart=round(float(jp.base_pstart),6),
           adjusted_pstart=round(float(jp.medical_candidate_pstart),6),
           old_xmins=round(float(jp.base_xmins),6),
           adjusted_xmins=round(float(jp.candidate_xmins),6),
           note='Scenario, NOT a certified future prediction. Existing conditional starter duration unchanged.'),
      sum_xm_delta=round(float(current.xmins_delta.sum()),5),
      impacted_more_than_one_minute=int((abs(current.xmins_delta)>1).sum()),
      largest_xmin_changes=current.reindex(current.xmins_delta.abs().sort_values(ascending=False).index)[
          ['player','team','xmins_delta','base_xmins','candidate_xmins','p_start_delta']].head(20).round(4).to_dict('records'),
      unchanged_role_optimizer=True,news_scope_only_current_gw=True,
      base_reconstruction_nonhard_max_error=err_nonhard,
      full_model_changed=False,app_updated=False)
    W.joinpath('joao_pedro_medical_return_gw7_candidate.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('MM_MEDICAL_GW7_JOAO',json.dumps(report['joao_pedro'],ensure_ascii=False))
    print('MM_MEDICAL_GW7_COUNTS',json.dumps({k:report[k] for k in ['eligible_count','impacted_more_than_one_minute','base_reconstruction_nonhard_max_error']}))
    print('MM_MEDICAL_GW7_ELIGIBLE',json.dumps(report['detected'],ensure_ascii=False))
    print('MM_MEDICAL_GW7_TOP',json.dumps(report['largest_xmin_changes'],ensure_ascii=False))
if __name__=='__main__':main()
