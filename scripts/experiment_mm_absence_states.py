#!/usr/bin/env python3
"""Three-way, cutoff-safe absence / return diagnostic on existing frozen MM forecasts.

Three mutually exclusive prior-absence evidence types: CONFIRMED_UNAVAILABLE,
MEDICAL_DOUBT, and AVAILABLE_BUT_UNEXPLAINED. The last is NOT asserted to be
tactical; FPL pre-deadline AVAILABLE does not prove the player was on the bench.

For prospectively scored historical targets GW22-38, assign only from *earlier*
match outcomes and strict pre-deadline archived FPL status. Small logit offsets
for subsequent returning starters tested on GW22-28, evaluated on GW29-38.
Unavailability caps and exact-11 projection applied IDENTICALLY to both arms.
Source MM+PM+TS remain unchanged. This 2025/26 period has been reused already;
this is not an independent prospective held-out season.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit,logit
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl, validate_strict_projection, strict_state_cap

P=ROOT/'analysis/results/mm-unified-official-roles-20261006-v1/reused_diagnostic_predictions.csv.gz'
H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
N=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2'
OUT=ROOT/'work/live-final-model/mm_absence_states_and_return_calibration.json'

medical={'OUT','DOUBT','MAJOR_DOUBT'}
ready={'AVAILABLE','RETURNED_AVAILABLE'}
def metrics(df,pcol,xcol):
    n=len(df)
    if not n:return None
    p=np.clip(df[pcol].to_numpy(float),1e-8,1-1e-8)
    y=df.y.to_numpy(float);xm=df[xcol].to_numpy(float);mins=df.minutes.to_numpy(float)
    return dict(n=n,observed_start=round(float(y.mean()),5),predicted_start=round(float(p.mean()),5),
                start_brier=round(float(np.mean((p-y)**2)),7),
                start_logloss=round(float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),7),
                minute_mae=round(float(np.mean(np.abs(xm-mins))),5),
                minute_rmse=round(float(np.sqrt(np.mean((xm-mins)**2))),5),
                minute_bias=round(float(np.mean(xm-mins)),5),
                predicted_xM=round(float(xm.mean()),5),actual_minutes=round(float(mins.mean()),5))
def safe_float(x):return float(x) if np.isfinite(x) else None

def build():
    a=pd.read_csv(P,low_memory=False)
    h=pd.read_csv(H,usecols=['fixture_uuid','gw','player_uuid','y','minutes'],low_memory=False)
    strict=validate_strict_projection(read_split_gzip_jsonl(N,'predeadline_strict.jsonl.gz'))
    # Inspect evidence strictly as it was available BEFORE each GW.
    states={(int(v.gw),str(v.player_uuid)):str(v.normalized_availability_state)
            for v in strict.itertuples(index=False)}
    h['gw']=h.gw.astype(int)
    h=h[h.gw.ge(6)].copy()
    if h.duplicated(['fixture_uuid','player_uuid']).any():raise AssertionError('Duplicate historical target')
    # Fixture outcomes may have multiple games in a double GW; if so, using
    # them as single-round exposure is ambiguous and must not manufacture zero.
    counts=h.groupby(['player_uuid','gw']).size()
    duplicates=set(counts[counts>1].index)
    evidence={}
    for player,g in h.groupby('player_uuid'):
        g=g.sort_values(['gw','fixture_uuid'])
        evidence[str(player)]={int(row.gw):(int(row.y),float(row.minutes))
                     for row in g.itertuples(index=False) if (str(player),int(row.gw)) not in duplicates}
    a['gw']=a.gw.astype(int)
    assert len(a)>=13000 and a.gw.min()==22 and a.gw.max()==38
    assert not a.duplicated(['fixture_uuid','player_uuid']).any()
    fields=['mm_p_start','mm_xmins','mm_q_sub','mm_sub_minutes','y','minutes']
    for col in fields:a[col]=pd.to_numeric(a[col],errors='raise')
    tags=[];prev_states=[]
    for r in a.itertuples(index=False):
        player=str(r.player_uuid);gw=int(r.gw)
        ps=evidence.get(player,{})
        past=[ps.get(gw-i) for i in range(1,7)]
        current=states.get((gw,player),'UNKNOWN')
        status1=states.get((gw-1,player),'UNKNOWN')
        status2=states.get((gw-2,player),'UNKNOWN')
        def st(row):return row is not None and row[0]==1
        def z(row):return row is not None and row[1]==0.
        anchors=sum(st(t) for t in past[2:6])
        pre_anchors=sum(st(t) for t in past[1:5])
        if current=='SUSPENDED':label='currently_suspended'
        elif current=='OUT':label='currently_medically_unavailable'
        elif current in ('DOUBT','MAJOR_DOUBT'):label='currently_doubtful'
        elif z(past[0]) and pre_anchors>=2:
            if status1=='SUSPENDED':label='immediate_return_after_suspension'
            elif status1=='OUT':label='immediate_return_from_confirmed_unavailable'
            elif status1 in ('DOUBT','MAJOR_DOUBT'):label='immediate_return_after_medical_doubt'
            elif status1 in ready:label='return_after_available_zero_unexplained'
            else:label='immediate_return_zero_unknown_status'
        elif st(past[0]) and z(past[1]) and anchors>=2:
            if status2=='SUSPENDED':label='recovered_starter_after_suspension'
            elif status2=='OUT':label='recovered_starter_after_confirmed_unavailable'
            elif status2 in ('DOUBT','MAJOR_DOUBT'):label='recovered_starter_after_medical_doubt'
            elif status2 in ready:label='recovered_starter_after_available_zero_unexplained'
            else:label='recovered_starter_after_zero_unknown_status'
        elif current in ready:label='other_current_available'
        else:label='other_unknown'
        tags.append(label)
        prev_states.append(dict(current_status=current,status_last=status1,status_two_ago=status2,
                                last_minutes=None if past[0] is None else past[0][1],
                                two_ago_minutes=None if past[1] is None else past[1][1],
                                prior_starts_3_6=anchors,
                                predeadline_current_status_is_verified=(gw,player) in states))
    a['absence_class']=tags
    a['current_news_state']=[x['current_status'] for x in prev_states]
    a['prior_news_state']=[x['status_last'] for x in prev_states]
    a['prior2_news_state']=[x['status_two_ago'] for x in prev_states]
    a['last_minutes']=[x['last_minutes'] for x in prev_states]
    a['two_ago_minutes']=[x['two_ago_minutes'] for x in prev_states]
    a['predeadline_news_verified']=[x['predeadline_current_status_is_verified'] for x in prev_states]
    a['medical_recovered']=a.absence_class.isin([
         'recovered_starter_after_confirmed_unavailable','recovered_starter_after_medical_doubt',
         'immediate_return_from_confirmed_unavailable','immediate_return_after_medical_doubt'
    ])
    a['unexplained_recovered']=a.absence_class.isin([
         'recovered_starter_after_available_zero_unexplained','return_after_available_zero_unexplained'
    ])
    # Audit saved original conditional start + substitute minutes. Formula may
    # show +/-tiny floating error, but values outside [0,90] are quarantined.
    p=np.clip(a.mm_p_start.to_numpy(float),1e-6,1-1e-6)
    sub=a.mm_q_sub.to_numpy(float)*a.mm_sub_minutes.to_numpy(float)
    start=(a.mm_xmins.to_numpy(float)-(1-p)*sub)/p
    bad=((start<-1e-3)|(start>90.001)) | ~np.isfinite(start)
    if int(bad.sum()):
        sample=a.loc[bad,['gw','player','mm_xmins','mm_p_start']].head(5)
        print('ABSENCE_DURATION_QUARANTINE',json.dumps(dict(n=int(bad.sum()),examples=sample.to_dict('records'))),flush=True)
    if bad.mean()>.01:raise ValueError('Too many invalid saved duration components')
    a['start_mu']=np.clip(start,0,90)
    a['bench_mu']=np.clip(sub,0,90)
    # Current hard eligibility is deterministic. All arms use the exact same
    # verified caps, and no OUT player receives substitute minutes.
    a['cap']=[strict_state_cap(state,None,doubt_cap=.5,major_doubt_cap=.1)
              for state in a.current_news_state]
    assert (a.cap>=0).all() and (a.cap<=1).all()
    return a,strict

def project(a,medical_bump,unexplained_bump):
    x=a.copy()
    base=np.clip(x.mm_p_start.to_numpy(float),1e-7,1-1e-7)
    z=logit(base)
    bump=(medical_bump*x.medical_recovered.to_numpy(float)+
          unexplained_bump*x.unexplained_recovered.to_numpy(float))
    bumped=expit(z+bump)
    p=project_exact_starters_with_caps(x,bumped,x.cap.to_numpy(float))
    x['p_model']=p
    x['x_model']=p*x.start_mu.to_numpy(float)+(1-p)*x.bench_mu.to_numpy(float)
    x.loc[x.cap.eq(0),'x_model']=0.
    if x.p_model.lt(-1e-8).any() or x.p_model.gt(1+1e-8).any():raise ValueError('Invalid P(start)')
    err=(x.groupby(['fixture_uuid','team_id']).p_model.sum()-11).abs().max()
    if err>1e-6:raise ValueError('Failed exact 11 starter projection')
    return x

def main():
    a,strict=build()
    classes={key:dict(**metrics(g,'mm_p_start','mm_xmins'),
                      target_state_counts=g.current_news_state.value_counts().to_dict(),
                      current_news_verified_fraction=round(float(g.predeadline_news_verified.mean()),4))
             for key,g in a.groupby('absence_class')}
    dev=a[a.gw.between(22,28)]
    test=a[a.gw.between(29,38)]
    medical_n=int(a.medical_recovered.sum())
    unknown_n=int(a.unexplained_recovered.sum())
    candidates=[(0.,0.),(.2,0.),(.4,0.),(.6,0.),(.8,0.),(.4,.2),(.6,.2),(0.,.2)]
    scores={}
    tested={}
    baseline_dev=project(dev,0,0)
    baseline_test=project(test,0,0)
    def by_slice(d):
        o={'overall':metrics(d,'p_model','x_model'),
           'medical_recovered':metrics(d[d.medical_recovered],'p_model','x_model'),
           'unexplained_recovered':metrics(d[d.unexplained_recovered],'p_model','x_model'),
           'other':metrics(d[~(d.medical_recovered|d.unexplained_recovered)],'p_model','x_model')}
        return o
    base_d=by_slice(baseline_dev);base_t=by_slice(baseline_test)
    for m,u in candidates:
        key=f'medical_{m:.1f}_unexplained_{u:.1f}'
        v=project(dev,m,u)
        scores[key]=by_slice(v)
    # Candidate must improve medically-evidenced subgroup and not materially
    # harm global log loss/MAE/RMSE. If too few medically-evidenced rows,
    # report insufficient evidence, not an optimal magic offset.
    eligible=[]
    for key,rec in scores.items():
        med=rec['medical_recovered']
        if not med or not base_d['medical_recovered'] or med['n']<20:continue
        if (rec['overall']['start_logloss']<=base_d['overall']['start_logloss']+.0001 and
            rec['overall']['minute_rmse']<=base_d['overall']['minute_rmse']+.015 and
            rec['overall']['minute_mae']<=base_d['overall']['minute_mae']+.015 and
            med['minute_rmse']<base_d['medical_recovered']['minute_rmse'] and
            med['start_brier']<=base_d['medical_recovered']['start_brier']+.003):
            eligible.append(key)
    best=min(eligible,key=lambda k:(scores[k]['medical_recovered']['minute_rmse'],
                                     scores[k]['overall']['start_logloss'])) if eligible else None
    if best:
        w=best.split('_')
        selected_m=float(w[1]);selected_u=float(w[3])
        chosen=project(test,selected_m,selected_u)
        chosen_results=by_slice(chosen)
        paired=baseline_test[['fixture_uuid','player_uuid','medical_recovered','minutes','y','p_model','x_model']].merge(
            chosen[['fixture_uuid','player_uuid','p_model','x_model']],
            on=['fixture_uuid','player_uuid'],how='inner',validate='one_to_one',suffixes=('_base','_candidate'))
        matched=paired[paired.medical_recovered].copy()
        def bootstrap(group):
            if len(group)<10:return None
            group=group.copy()
            group['sq_old']=(group.x_model_base-group.minutes)**2
            group['sq_new']=(group.x_model_candidate-group.minutes)**2
            group['abs_old']=abs(group.x_model_base-group.minutes)
            group['abs_new']=abs(group.x_model_candidate-group.minutes)
            def ll(y,p):
                p=np.clip(p,1e-9,1-1e-9)
                return -(y*np.log(p)+(1-y)*np.log(1-p))
            group['log_old']=ll(group.y,group.p_model_base)
            group['log_new']=ll(group.y,group.p_model_candidate)
            cases=group.groupby('fixture_uuid').agg(n=('y','size'),s0=('sq_old','sum'),s1=('sq_new','sum'),
                a0=('abs_old','sum'),a1=('abs_new','sum'),
                l0=('log_old','sum'),l1=('log_new','sum'))
            array=cases.to_numpy(float);num=len(cases);rng=np.random.default_rng(20261012)
            sample=rng.integers(0,num,size=(3000,num))
            sampled=array[sample].sum(axis=1)
            counts=sampled[:,0]
            rmse=np.sqrt(sampled[:,2]/counts)-np.sqrt(sampled[:,1]/counts)
            mae=(sampled[:,4]-sampled[:,3])/counts
            loss=(sampled[:,6]-sampled[:,5])/counts
            return dict(player_rows=len(group),distinct_matches=num,
                delta_minute_rmse_ci95=list(map(lambda v:round(float(v),5),np.quantile(rmse,[.025,.975]))),
                delta_minute_mae_ci95=list(map(lambda v:round(float(v),5),np.quantile(mae,[.025,.975]))),
                delta_start_logloss_ci95=list(map(lambda v:round(float(v),6),np.quantile(loss,[.025,.975]))),
                note='Match-cluster resampling, not a new independent season.')
        uncertainty=bootstrap(matched)
    else:chosen_results=None;uncertainty=None
    out=dict(classification='READ_ONLY_PREDEADLINE_ABSENCE_STATES_2025_26_REUSED_MM_DIAGNOSTIC',
        sample_rows=len(a),strict_news_rows=len(strict),
        training_windows=dict(development='2025/26 GW22-28',validation='2025/26 GW29-38 (same previously used diagnostic season)'),
        labels=dict(confirmed_unavailable='Previous GW OUT and 0 minutes (historical, pre-target); distinct from suspension',
                    suspension='Previous GW SUSPENDED and 0 minutes; excluded from injury return offset',
                    medical_doubt='Previous GW DOUBT/MAJOR_DOUBT and 0 minutes (not confirmed injured)',
                    unexplained_zero='Previous GW 0 minutes but officially AVAILABLE; this is NOT verified tactical bench',
                    recovered='Player started in most recent GW, had a medically tagged or unexplained 0 two GWs ago'),
        sources='Historical GW outcomes only before target + strict verified FPL predeadline snapshots',
        subgroup_classes=classes,
        dev_counts=dict(medical_recovered=int(dev.medical_recovered.sum()),
                        unexplained_recovered=int(dev.unexplained_recovered.sum())),
        test_counts=dict(medical_recovered=int(test.medical_recovered.sum()),
                         unexplained_recovered=int(test.unexplained_recovered.sum())),
        original_saved_model_overall=metrics(a,'mm_p_start','mm_xmins'),
        equal_caps_development_baseline=base_d,
        equal_caps_validation_baseline=base_t,
        development_candidates=scores,
        selected_on_dev_only=best,
        validation_selected_if_eligible=chosen_results,
        validation_returner_match_bootstrap=uncertainty,
        important_limitations=[
            'Tactical bench membership is not in FPL Team News; AVAILABLE and zero is unclassified, not tactical proof',
            'The saved original MM predictions precede strict news availability in this proxy; both arms receive equal caps',
            'This does not refit role XI competition on a changed player prior',
            'Small medical subgroup and reused 2025/26 diagnostic exclude final model promotion'],
        model_math_changed=False,promoted_to_app=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    for label,v in [('COUNTS',dict(sample_rows=len(a),medical_n=medical_n,unexplained_n=unknown_n,dev=out['dev_counts'],test=out['test_counts'])),
                    ('CLASS_METRICS',classes),('DEV_BASE',base_d),
                    ('TEST_BASE',base_t),('CANDIDATES',scores),
                    ('SELECTED',dict(selected=best,validated=chosen_results,uncertainty=uncertainty))]:
        print('ABSENCE_MODEL_'+label,json.dumps(v,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
