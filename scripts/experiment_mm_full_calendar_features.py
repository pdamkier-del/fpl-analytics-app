#!/usr/bin/env python3
"""Compare complete locked-MM pipeline with genuine fixture-date features.

This is a frozen-MM RESEARCH experiment, never a production change.
Training: 2025/26 GW6-15; choose on GW16-21. Refit GW6-21;
reused 2025/26 GW22-38 as diagnostic (NOT independent holdout).

Unlike integer GW-lag sequence inputs, uses actual Premier League kickoffs
and outcomes available strictly prior to each target's FPL deadline, plus
the independently archived predeadline injury news. The future target match
kickoff is an allowed known schedule field; target actual outcomes never
enter calendar history.

Official non-PL matches remain represented in already existing workload
features. A long PL break does not certify a physical rest break because
internationals may be missing.
"""
from __future__ import annotations
import json,sys
from collections import defaultdict
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_mm_unified_official_roles import SOURCE
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_v2_team_news_availability_experiment import evaluate_news_variant
from audit_mm_real_calendar_gaps import pl_calendar

NEWS=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2'
RATINGS=ROOT/'data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz'
OUT=ROOT/'work/live-final-model/mm_full_calendar_feature_ab.json'
POLICY='soft_0.5_0.1'
CAL_GAP=['cal_team_since_pl_days','cal_player_since_start_days',
         'cal_player_since_appearance_days','cal_kickoff_delay_from_cutoff_days',
         'cal_never_started_prior']
CAL_RECENCY=['cal_appearances_decay14','cal_starts_decay14',
             'cal_minutes_decay14','cal_starts_weighted_share']
CAL_RECOVERY=['cal_medical_return_starter','cal_unexplained_return_starter',
              'cal_previous_zero_age_days']
CANDIDATES={
    'original':[],
    'calendar_gaps':CAL_GAP,
    'calendar_gaps_recency':CAL_GAP+CAL_RECENCY,
    'calendar_gaps_medical':CAL_GAP+CAL_RECOVERY,
    'calendar_full':CAL_GAP+CAL_RECENCY+CAL_RECOVERY,
}

def build_calendar(frame):
    f=frame.reset_index(drop=True).copy()
    games=pl_calendar(f)
    sched={}
    for (team,gw),g in games.groupby(['team_id','gw']):
        if len(g)==1:sched[(int(team),int(gw))]=pd.Timestamp(g.ko.iloc[0])
    # Teams have no observed activity until *outcomes* are known, irrespective of kickoff.
    ids={key:i for i,key in enumerate(zip(f.team_id.astype(int),f.gw.astype(int)))}
    del ids
    k=[sched.get((int(t),int(g)),pd.NaT) for t,g in zip(f.team_id,f.gw)]
    ko=pd.to_datetime(pd.Series(k),utc=True)
    cutoff=pd.to_datetime(f.cutoff,utc=True,errors='raise')
    known=pd.to_datetime(f.outcome_known_at,utc=True,errors='raise')
    if (known<=ko).any():raise ValueError('Historical target outcome available before kickoff')
    if len(f)!=len(ko):raise AssertionError('Kickoff join changed rows')
    teamhist=defaultdict(list)
    for idx,r in f[['team_id','fixture_uuid']].drop_duplicates().iterrows():
        # Lookup original index because team-specific fixture IDs are unique.
        t=int(r.team_id)
        group=f[(f.team_id==t)&f.fixture_uuid.eq(r.fixture_uuid)]
        targetko=ko.iloc[group.index[0]]
        release=known.iloc[group.index[0]]
        if pd.notna(targetko):teamhist[t].append((targetko,release))
    playerhist=defaultdict(list)
    for i,r in enumerate(f.itertuples(index=False)):
        if pd.notna(ko.iloc[i]):
            playerhist[str(r.player_uuid)].append((ko.iloc[i],known.iloc[i],int(r.y),
                            float(r.minutes),int(r.gw)))
    for hist in teamhist.values():hist.sort(key=lambda x:x[0])
    for hist in playerhist.values():hist.sort(key=lambda x:x[0])
    medical_states=dict(((int(r.gw),str(r.player_uuid)),str(r.team_news_state))
        for r in f[['gw','player_uuid','team_news_state']].drop_duplicates().itertuples(index=False))
    out=[]
    missing=0
    example=[]
    for i,r in enumerate(f.itertuples(index=False)):
        target_ko=ko.iloc[i]
        cut=cutoff.iloc[i]
        if pd.isna(target_ko):
            missing+=1
            out.append([0.,28.,28.,0.,1.,0.,0.,0.,0.,0.,0.,28.])
            continue
        if target_ko<cut:raise ValueError('Fixture was kicked off before pre-target deadline')
        # Must satisfy BOTH earlier kickoff and release prior to target deadline.
        t=[g for g in teamhist[int(r.team_id)] if g[0]<target_ko and g[1]<cut]
        h=[g for g in playerhist[str(r.player_uuid)] if g[0]<target_ko and g[1]<cut]
        app=[x for x in h if x[3]>0]
        starts=[x for x in h if x[2]==1]
        last_team=(target_ko-t[-1][0]).total_seconds()/86400 if t else 28.
        last_app=(target_ko-app[-1][0]).total_seconds()/86400 if app else 28.
        last_start=(target_ko-starts[-1][0]).total_seconds()/86400 if starts else 28.
        delay=(target_ko-cut).total_seconds()/86400
        assert delay>=0
        decays=[2**(-(target_ko-z[0]).total_seconds()/86400/14.) for z in h]
        startmass=sum(w*z[2] for w,z in zip(decays,h))
        appmass=sum(w*(z[3]>0) for w,z in zip(decays,h))
        minmass=sum(w*z[3] for w,z in zip(decays,h))
        share=startmass/sum(decays) if decays else 0.
        prior_by_gw={z[4]:z for z in h}
        last=prior_by_gw.get(int(r.gw)-1)
        missed=prior_by_gw.get(int(r.gw)-2)
        status=medical_states.get((int(r.gw)-2,str(r.player_uuid)),'UNKNOWN')
        is_return=(last is not None and missed is not None and last[2]==1
                   and missed[3]==0. and sum(z[2] for z in h if int(r.gw)-6<=z[4]<=int(r.gw)-3)>=2)
        medical=(is_return and status in {'OUT','DOUBT','MAJOR_DOUBT'})
        unexplained=(is_return and status in {'AVAILABLE','RETURNED_AVAILABLE','UNKNOWN'})
        age_zero=float((target_ko-missed[0]).total_seconds()/86400) if missed is not None and missed[3]==0 else 28.
        v=[min(last_team,56.),min(last_start,56.),min(last_app,56.),min(delay,14.),
           float(not bool(starts)),appmass,startmass,minmass/90.,share,
           float(medical),float(unexplained),min(age_zero,56.)]
        out.append(v)
        if len(example)<5 and medical:
            example.append(dict(player=str(r.player),gw=int(r.gw),gap=round(last_team,3),days_since_zero=round(age_zero,3)))
    fields=CAL_GAP+CAL_RECENCY+CAL_RECOVERY
    result=pd.DataFrame(out,columns=fields,index=f.index)
    if len(f)!=len(result) or not np.isfinite(result.to_numpy(float)).all():
        raise ValueError('Calendar feature construction malformed')
    for c in fields:
        if c in f:raise ValueError('Calendar feature collision: '+c)
        f[c]=result[c]
    coverage=dict(total_rows=len(f),unresolved_matchday_rows=missing,
                  resolved_matchday_rows=len(f)-missing,
                  resolved_fraction=round((len(f)-missing)/len(f),4),
                  medical_return_rows=int(f.cal_medical_return_starter.sum()),
                  unexplained_return_rows=int(f.cal_unexplained_return_starter.sum()),
                  sample_medical=example)
    if coverage['resolved_fraction']<.90:raise AssertionError('Fixture kickoff coverage too weak')
    return f,coverage

def score_subset(frame,target,news_output):
    f,locked,locked_x,pre,p,qx,q,sub,met=news_output
    return dict(total=dict(n=int(target.sum()),state_logloss=float(met['state_log_loss']),
        xmins_mae=float(met['xmins_mae']),xmins_rmse=float(met['xmins_rmse'])),
        medical=dict(n=int((target&(frame.cal_medical_return_starter>0)).sum())),
        long_gap=dict(n=int((target&(frame.cal_team_since_pl_days>=14)).sum())),
        p=p,x=qx)

def run():
    frame=add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    frame=build_strict_team_news_features(frame,read_split_gzip_jsonl(NEWS,'predeadline_strict.jsonl.gz'))
    frame,coverage=build_calendar(frame)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)
    def split(gws,train_end):
        v=frame.gw.isin(gws).to_numpy()
        cut=pd.to_datetime(frame.loc[v,'cutoff'],utc=True).min()
        tr=(frame.gw.le(train_end)&known.lt(cut)).to_numpy()
        return tr,v
    tr,dev=split(range(16,22),15)
    te_train,test=split(range(22,39),21)
    assert tr.sum()>3000 and dev.sum()>2500 and test.sum()>12000
    results={}
    def evaluate(train,mask,features):
        feat,locked,locked_x,pre,ps,xm,q,sub,met=evaluate_news_variant(
            frame,train,mask,POLICY,extra_base_features=features)
        grouped={}
        for name,band in [('medical_returner',frame.cal_medical_return_starter.gt(.5).to_numpy()),
                          ('long_gap14',frame.cal_team_since_pl_days.ge(14).to_numpy()),
                          ('standard_gap',frame.cal_team_since_pl_days.lt(14).to_numpy())]:
            select=mask&band
            if select.sum()>=10:
                grouped[name]=metrics(feat,select,ps,q,xm)
        return dict(n=int(mask.sum()),overall=met,groups=grouped,
            mean_calendar_pl_break_days=float(frame.loc[mask,'cal_team_since_pl_days'].mean()))
    for label,features in CANDIDATES.items():
        results[label]=dict(dev=evaluate(tr,dev,features))
        stats=results[label]
        print('CAL_MM_FULL_CANDIDATE',json.dumps({'variant':label,
           'dev':{k:stats['dev']['overall'][k] for k in ['state_log_loss','xmins_mae','xmins_rmse']}},ensure_ascii=False),flush=True)
    base=results['original']['dev']['overall']
    keys=['state_log_loss','xmins_mae','xmins_rmse']
    accepted=[]
    for label in CANDIDATES:
        if label=='original':continue
        rec=results[label]['dev']['overall']
        if (rec['xmins_rmse']<base['xmins_rmse'] and
            rec['xmins_mae']<=base['xmins_mae']+.025 and
            rec['state_log_loss']<=base['state_log_loss']+.001):
            accepted.append(label)
    selected=min(accepted,key=lambda k:(results[k]['dev']['overall']['xmins_rmse'],
          results[k]['dev']['overall']['state_log_loss'])) if accepted else 'original'
    # Reused diagnostic is evaluated AFTER development-only selection.
    # Other exploratory variants are never cherry-picked from this stage.
    for label in ['original']+([selected] if selected!='original' else []):
        results[label]['reused_test']=evaluate(te_train,test,CANDIDATES[label])
        q=results[label]['reused_test']['overall']
        print('CAL_MM_FULL_REUSED',json.dumps(dict(variant=label,n=results[label]['reused_test']['n'],
            state_log_loss=q['state_log_loss'],xmins_mae=q['xmins_mae'],xmins_rmse=q['xmins_rmse'])),flush=True)
    report=dict(classification='RESEARCH_REFIT_OF_FULL_2025_26_MM_WITH_CALENDAR_TIME_FEATURES',
        coverage=coverage,features=CANDIDATES,results=results,
        selected_development_only=selected,
        selection_rule='dev xMins RMSE improvement with MAE <=+0.025 and state logloss <=+0.001',
        baseline_locked='soft_0.5_0.1 strict predeadline team news, XI roles, p-start residual, same original conditional-minute components',
        train_dev='GW6-15 -> GW16-21',train_reused='GW6-21 -> GW22-38',
        caveat='The latter is a reused diagnostic, never independent season proof',
        policy='Only selected on GW16-21; all production MM/PM/TS remain unchanged',
        app_model_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
    print('CAL_MM_FULL_SELECTION',json.dumps(dict(selected=selected,coverage=coverage,
        baseline=results['original'],choice=results[selected]),ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':run()
