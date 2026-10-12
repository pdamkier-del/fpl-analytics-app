#!/usr/bin/env python3
"""Experiment: replace GW-count proxy for conditional start duration with
calendar-time-weighted observed starts. Read-only against original locked MM.

Original MM P(start), conditional bench appearance, opponent, news and
XI are unchanged. Only the conditional starter duration is blended with
a cutoff-safe exponentially decayed *starter-only* historical mean.

Selection GW22-28, evaluation GW29-38 (REUSED prior MM diagnostic, not
independent certification). Historical fixture kickoff joins 20 team
identities by grounded match slugs, not provider numeric codes.

For a current forecast, NO outcomes after its saved pre-deadline cutoff
are inspected; rows at or after cutoff are never used for features.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_mm_real_calendar_gaps import pl_calendar
from experiment_mm_absence_states import build,metrics

H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
OUT=ROOT/'work/live-final-model/mm_time_decayed_conditional_starts_ab.json'

def main():
    base,_=build()
    games=pl_calendar(base)
    by_team_gw=games.groupby(['team_id','gw']).ko.agg(list).to_dict()
    raw=pd.read_csv(H,usecols=['fixture_uuid','player_uuid','team_id','gw','y','minutes','outcome_known_at','cutoff'],low_memory=False)
    raw['outcome_known_at']=pd.to_datetime(raw.outcome_known_at,utc=True)
    raw['cutoff']=pd.to_datetime(raw.cutoff,utc=True)
    raw['gw']=raw.gw.astype(int)
    evidence={}
    malformed=0
    for v in raw.itertuples(index=False):
        ko=by_team_gw.get((int(v.team_id),int(v.gw)),[])
        if len(ko)!=1:
            malformed+=1
            continue
        evidence.setdefault(str(v.player_uuid),[]).append(
            (ko[0],v.outcome_known_at,int(v.y),float(v.minutes)))
    for rows in evidence.values():rows.sort(key=lambda v:v[0])
    target_cuts=(raw[['fixture_uuid','player_uuid','cutoff']]
                 .drop_duplicates(['fixture_uuid','player_uuid']))
    if target_cuts.duplicated(['fixture_uuid','player_uuid']).any():raise AssertionError('Duplicate target cutoff')
    base=base.merge(target_cuts,on=['fixture_uuid','player_uuid'],how='left',validate='one_to_one')
    assert base.cutoff.notna().mean()>.99
    basemu=base.start_mu.to_numpy(float)
    offset=base.mm_p_start.to_numpy(float)
    bench=base.bench_mu.to_numpy(float)
    med=base.medical_recovered.to_numpy(bool)
    gw=base.gw.to_numpy(int)
    priors=[[],[]] # placeholder assigned below
    rows=[]
    badcut=0
    for v in base.itertuples(index=False):
        dates=by_team_gw.get((int(v.team_id),int(v.gw)),[])
        if len(dates)!=1 or pd.isna(v.cutoff):
            rows.append((np.nan,[],[]));continue
        target=dates[0];cut=pd.Timestamp(v.cutoff)
        if target<=cut:badcut+=1;rows.append((np.nan,[],[]));continue
        # Only exact historical starts known before saved ORIGINAL deadline.
        hist=[z for z in evidence.get(str(v.player_uuid),[])
              if z[0]<target and z[1]<cut and z[2]==1 and z[3]>0]
        hist=hist[-8:]
        ages=[(target-z[0]).total_seconds()/86400. for z in hist]
        mins=[z[3] for z in hist]
        rows.append((float(min(ages)) if ages else np.nan,ages,mins))
    if badcut>0:raise AssertionError('Target kicks off before archived predeadline cutoff')
    ages=[r[1] for r in rows]
    minutes=[r[2] for r in rows]
    samples=np.array([len(z) for z in minutes])
    def pred_duration(half):
        ret=np.zeros(len(base),float)
        for i,(a,m) in enumerate(zip(ages,minutes)):
            if len(m)<2:
                ret[i]=np.nan;continue
            w=np.exp2(-np.asarray(a,float)/half)
            if w.sum()<1e-12:ret[i]=np.nan;continue
            ret[i]=float(np.dot(w,np.asarray(m,float))/w.sum())
        return ret
    candidates={'baseline':basemu}
    for half in [7.,14.,28.,56.]:
        durations=pred_duration(half)
        for alpha in [.15,.30,.50]:
            # Do not increase the starter duration above physiological 90 min.
            val=np.clip(basemu+alpha*np.nan_to_num(durations-basemu,nan=0.),0.,90.)
            candidates[f'halflife_{int(half)}_blend_{alpha:.2f}']=val
    cols={}
    valid=np.isfinite(basemu)&np.isfinite(offset)&np.isfinite(bench)
    assert valid.all()
    for name,d in candidates.items():
        x=offset*d+(1-offset)*bench
        x=np.where(base.cap.eq(0).to_numpy(),0.,x)
        cols[name]=x
    frames={}
    for name,x in cols.items():
        z=base.copy()
        z['p_fit']=offset
        z['xm_fit']=x
        frames[name]=z
    dev=base.gw.between(22,28).to_numpy()
    test=base.gw.between(29,38).to_numpy()
    results={}
    for name,f in frames.items():
        results[name]=dict(dev_all=metrics(f[dev],'p_fit','xm_fit'),
                           dev_medical=metrics(f[dev & med],'p_fit','xm_fit'),
                           test_all=metrics(f[test],'p_fit','xm_fit'),
                           test_medical=metrics(f[test & med],'p_fit','xm_fit'),
                           test_players_with_two_starts=metrics(f[test & (samples>=2)],'p_fit','xm_fit'))
    ref=results['baseline']['dev_all']
    eligible=[]
    for name,r in results.items():
        if name=='baseline':continue
        v=r['dev_all']
        if (v['minute_rmse']<ref['minute_rmse'] and
            v['minute_mae']<ref['minute_mae'] and
            r['dev_medical']['minute_rmse']<=results['baseline']['dev_medical']['minute_rmse']+.5):
            eligible.append(name)
    selected=min(eligible,key=lambda k:(results[k]['dev_all']['minute_rmse'],
                                       results[k]['dev_all']['minute_mae'])) if eligible else 'baseline'
    out=dict(classification='READ_ONLY_CALENDAR_WEIGHTED_STARTER_MINUTES_EXPERIMENT',
         coverage=dict(historical_observation_rows=len(raw),history_unmapped_non_single_team_gw=malformed,
                       scored_rows=len(base),scored_rows_with_two_known_starts=int((samples>=2).sum()),
                       median_age_of_last_start_days=safe_median([x[0] for x in rows]),
                       target_predeadline_rows=int(base.cutoff.notna().sum())),
         formula='start_duration_candidate=(1-alpha)*frozen_duration + alpha*exp2(-days_since_observed_start/half_life) weighted prior-start-minute mean',
         unchanged=['P(start)','bench cameo probability','bench duration','original strict injury caps','original XI role assignment'],
         selected_on_dev=selected,
         all_candidate_scores=results,
         selected_test=results[selected],
         baseline_test=results['baseline'],
         decision='No production change: historical diagnostics reused, choose only if development MAE and RMSE improve',
         prospective_policy='Need independent fixture-chronological MM replay and verified national-team data before certification',
         promoted=False,production_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('CALENDAR_DURATION_COVERAGE',json.dumps(out['coverage']))
    print('CALENDAR_DURATION_SELECTED',json.dumps(dict(selected=selected,dev=results[selected]['dev_all'],
                 holdout=results[selected]['test_all'],reference_holdout=results['baseline']['test_all'],
                 selected_medical=results[selected]['test_medical'],
                 baseline_medical=results['baseline']['test_medical'])))
    print('CALENDAR_DURATION_DEV_SCORES',json.dumps({
         k:dict(mae=v['dev_all']['minute_mae'],rmse=v['dev_all']['minute_rmse']) for k,v in results.items()}))
def safe_median(v):
    z=np.asarray(v,float);z=z[np.isfinite(z)]
    return round(float(np.median(z)),3) if len(z) else None
if __name__=='__main__':main()
