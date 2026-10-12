#!/usr/bin/env python3
"""Calendar-gap and recovery-time study, using unchanged archived MM history.

Accurately reconstruct interval from confirmed PREMIER LEAGUE kickoffs rather
than subtracting integer gameweeks. Excludes match observations not known by
target cutoffs; FPL deadline sources remain as-of strict.

Compare the PRIOR-selected medical return logit +0.8 candidate with changes
proportional to actual previous PL-match spacing (elapsed days). GW22-28 is
development, GW29-38 reserved later reuse-only diagnostic. Live GW5/6/7
dates are separately displayed without future outcomes.

Caveats: actual PL match gap is NOT physiologic recovery if internationals
or cup matches played in between. Workload already tracks observed club
fixtures but international duty is not known from FPL's PL archive.
"""
from __future__ import annotations
from pathlib import Path
import json,sys
import numpy as np,pandas as pd
from scipy.special import expit,logit
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from experiment_mm_absence_states import build,metrics
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
W=ROOT/'work/live-final-model'
OUT=W/'mm_actual_calendar_gap_ab.json'

def pl_calendar(model):
    # The provider's numeric team_code is NOT the archived FPL team_id
    # (e.g. provider Chelsea=8, FPL Chelsea=7). The match-id home/away
    # slugs plus the model's certified team name let us build a deterministic
    # cross-source identity bridge; no unsafe numeric team ID assumption.
    mapped=model[['team_id','team']].drop_duplicates()
    if mapped.duplicated('team_id').any() or mapped.duplicated('team').any():
        raise ValueError('Ambiguous historical FPL team labels')
    tid_by_slug=dict(zip(mapped.team.astype(str),mapped.team_id.astype(int)))
    fixtures=[];provider_bridge={}
    unmatched=set()
    for folder in sorted(RAW.glob('GW*')):
        df=pd.read_csv(folder/'matches.csv',low_memory=False)
        df=df[df.match_id.astype(str).str.contains('25-26-prem-')].copy()
        df=df[df.finished.astype(str).str.lower().isin(['true','1'])].copy()
        for v in df.itertuples(index=False):
            gw=int(v.gameweek);ko=pd.Timestamp(v.kickoff_time)
            if ko.tzinfo is None:ko=ko.tz_localize('UTC')
            mid=str(v.match_id)
            home,away=mid.removeprefix('25-26-prem-').split('-vs-',1)
            for slug,code in ((home,int(v.home_team)),(away,int(v.away_team))):
                if slug not in tid_by_slug:
                    unmatched.add(slug);continue
                if slug in provider_bridge and provider_bridge[slug]!=code:
                    raise ValueError('Provider numeric code changes for '+slug)
                provider_bridge[slug]=code
                fixtures.append(dict(match_id=mid,gw=gw,team_id=tid_by_slug[slug],ko=ko))
    if unmatched:raise ValueError('Unmapped historical club slugs: '+str(sorted(unmatched)))
    if len(provider_bridge)!=20:raise AssertionError('Expected exactly 20 verified cross-provider teams')
    f=pd.DataFrame(fixtures).drop_duplicates(['match_id','team_id'])
    if not 740<=len(f)<=770:raise AssertionError(f'Insufficient 2025/26 verified PL fixtures: {len(f)}')
    f['ko']=pd.to_datetime(f.ko,utc=True)
    return f.sort_values(['team_id','ko'])

def attach(a,f):
    x=a.copy()
    # Each PL team target in scored MM group can be mapped by league GW and
    # team code; double fixtures require accounting for separate kickoffs.
    schedules=f.groupby(['team_id','gw']).ko.agg(list).to_dict()
    old=pd.read_csv(H,usecols=['gw','team_id','player_uuid','y','minutes','outcome_known_at'],low_memory=False)
    old['gw']=old.gw.astype(int)
    old['outcome_known_at']=pd.to_datetime(old.outcome_known_at,utc=True)
    histories={}
    for pid,g in old.groupby('player_uuid'):
        rows=[]
        for v in g.itertuples(index=False):
            dates=schedules.get((int(v.team_id),int(v.gw)),[])
            if len(dates)!=1:continue
            rows.append((dates[0],v.outcome_known_at,float(v.minutes),int(v.y)))
        rows.sort(key=lambda z:z[0])
        histories[str(pid)]=rows
    teamg={team:list(g.itertuples(index=False)) for team,g in f.groupby('team_id')}
    rows=[]
    no_current=0
    for r in x.itertuples(index=False):
        gw=int(r.gw);tid=int(r.team_id);pid=str(r.player_uuid)
        dates=schedules.get((tid,gw),[])
        if len(dates)!=1:
            no_current+=1
            rows.append((np.nan,np.nan,np.nan,np.nan,np.nan))
            continue
        ko=dates[0]
        # CUTOFF comes from same archived MM player forecast row; join from
        # original source with key and never use a later actual for features.
        prior=[z for z in histories.get(pid,[]) if z[1]<ko and z[0]<ko]
        prevteam=[g.ko for g in teamg.get(tid,[]) if g.ko<ko]
        prevteam.sort()
        team_gap=float((ko-prevteam[-1]).total_seconds()/86400) if prevteam else np.nan
        last_minutes=[z for z in prior if z[2]>0]
        last_app=float((ko-last_minutes[-1][0]).total_seconds()/86400) if last_minutes else np.nan
        prev_zero=[z for z in prior if z[2]==0]
        last_zero=float((ko-prev_zero[-1][0]).total_seconds()/86400) if prev_zero else np.nan
        since_known=float((ko-prior[-1][0]).total_seconds()/86400) if prior else np.nan
        # Real span covering medical-zero GW-2 to next started GW-1.
        medical_zero_dates=schedules.get((tid,gw-2),[])
        resume_dates=schedules.get((tid,gw-1),[])
        if len(medical_zero_dates)==1 and len(resume_dates)==1:
            break_to_return=float((resume_dates[0]-medical_zero_dates[0]).total_seconds()/86400)
        else:break_to_return=np.nan
        rows.append((team_gap,last_app,last_zero,since_known,break_to_return))
    names=['gap_since_team_last_pl_days','gap_since_player_last_minutes_days',
           'gap_since_last_zero_pl_days','gap_since_prior_observation_days',
           'gap_between_zero_and_return_days']
    for i,c in enumerate(names):x[c]=[v[i] for v in rows]
    return x,dict(missing_current_fixture_team_rows=no_current,available_rows=int(x.gap_since_team_last_pl_days.notna().sum()),
                  historical_match_side_rows=int(len(f)))

def news_summaries(x):
    report={}
    for metric in ['gap_since_team_last_pl_days','gap_since_player_last_minutes_days','gap_between_zero_and_return_days']:
        q=x[metric].to_numpy(float);valid=np.isfinite(q)
        report[metric]=dict(n=int(valid.sum()),p10=round(float(np.nanquantile(q,.1)),3),
            median=round(float(np.nanmedian(q)),3),p90=round(float(np.nanquantile(q,.9)),3),
            over_14days=int(np.sum(q>=14)),over_20days=int(np.sum(q>=20)))
    def band(days):
        if pd.isna(days):return 'unknown'
        if days<6:return 'under6'
        if days<10:return '6to10'
        if days<15:return '10to15'
        return '15plus'
    x['team_gap_band']=[band(g) for g in x.gap_since_team_last_pl_days]
    x['zero_to_return_band']=[band(g) for g in x.gap_between_zero_and_return_days]
    ret=x[x.medical_recovered|x.unexplained_recovered].copy()
    for typ,col in [('medical',ret.medical_recovered),('unexplained',ret.unexplained_recovered)]:
        r=ret[col]
        stats=[]
        for name,g in r.groupby('zero_to_return_band'):
            if len(g)>=3:
                stats.append(dict(interval=name,**metrics(g,'mm_p_start','mm_xmins')))
        report[typ+'_returns_by_zero_to_return_gap']=stats
    report['all_starters_by_team_gap']=[
        dict(gap=g,**metrics(z,'mm_p_start','mm_xmins'))
        for g,z in x.groupby('team_gap_band') if len(z)>20]
    return report

def candidate(x,beta):
    frame=x.copy()
    p=np.clip(frame.mm_p_start.to_numpy(float),1e-8,1-1e-8)
    days=frame.gap_between_zero_and_return_days.to_numpy(float)
    # Specific medical recovery state only. No blanket "more rest = healthy".
    # Bump 0.8 at 7 days; beta interaction uses log2 of 7-day equivalents.
    lag=np.where(np.isfinite(days),days,7.)
    delta=np.clip(np.log2(np.clip(lag,1.,60.)/7.),-1.5,2.)
    bump=(.8+beta*delta)*frame.medical_recovered.to_numpy(float)
    guess=expit(logit(p)+bump)
    cap=frame.cap.to_numpy(float)
    fixed=project_exact_starters_with_caps(frame,guess,cap)
    frame['p_candidate']=fixed
    frame['xm_candidate']=np.where(cap==0,0.,fixed*frame.start_mu+(1-fixed)*frame.bench_mu)
    assert (frame.groupby(['fixture_uuid','team_id']).p_candidate.sum()-11).abs().max()<1e-6
    return frame

def compare(x):
    dev=x[x.gw.between(22,28)].copy()
    test=x[x.gw.between(29,38)].copy()
    assert len(dev)>5000 and len(test)>7000
    choices=[-.4,-.2,0.,.2,.4,.6]
    d={}
    for beta in choices:
        y=candidate(dev,beta)
        d[str(beta)]={'overall':metrics(y,'p_candidate','xm_candidate'),
                      'medical':metrics(y[y.medical_recovered],'p_candidate','xm_candidate')}
    base=d['0.0']
    # Select only if BOTH minutes metrics improve on medical subgroup,
    # with globally safe loss and minutes bounds, never based on test.
    eligible=[b for b in choices if b!=0 and
        d[str(b)]['medical']['minute_rmse']<base['medical']['minute_rmse'] and
        d[str(b)]['medical']['minute_mae']<base['medical']['minute_mae'] and
        d[str(b)]['overall']['start_logloss']<=base['overall']['start_logloss']+.00005 and
        d[str(b)]['overall']['minute_mae']<=base['overall']['minute_mae']+.005]
    best=min(eligible,key=lambda b:(d[str(b)]['medical']['minute_rmse'],d[str(b)]['medical']['minute_mae'])) if eligible else 0.
    bt=candidate(test,0.)
    gt=candidate(test,best)
    t=dict(selected_beta=best,dev=d,
        test_original_selected_medical=dict(
            reference=metrics(bt[bt.medical_recovered],'p_candidate','xm_candidate'),
            candidate=metrics(gt[gt.medical_recovered],'p_candidate','xm_candidate')),
        test_original_selected_overall=dict(
            reference=metrics(bt,'p_candidate','xm_candidate'),
            candidate=metrics(gt,'p_candidate','xm_candidate')))
    return t

def joao_2026_calendar():
    b=json.loads((W/'bootstrap.json').read_text())
    fixtures=json.loads((W/'fixtures.json').read_text())
    jo=[p for p in b['elements'] if int(p['id'])==165]
    assert len(jo)==1 and 'pedro' in str(jo[0]['web_name']).lower()
    tid=int(jo[0]['team'])
    matches=sorted([dict(gw=int(v['event']),kickoff_at=v['kickoff_time'],finished=bool(v['finished']),
           home=bool(v['team_h']==tid),id=int(v['id']))
           for v in fixtures if v.get('event') in (4,5,6,7) and (v['team_h']==tid or v['team_a']==tid)],
           key=lambda v:(v['gw'],v['kickoff_at']))
    gaps=[]
    for k,v in enumerate(matches):
        if k:
            elapsed=(pd.Timestamp(v['kickoff_at'])-pd.Timestamp(matches[k-1]['kickoff_at'])).total_seconds()/86400
            gaps.append(dict(from_gw=matches[k-1]['gw'],to_gw=v['gw'],calendar_days=round(elapsed,4)))
    return dict(player_id=165,team_id=tid,matches=matches,gaps=gaps)

def main():
    a,_=build()
    f=pl_calendar(a)
    a,coverage=attach(a,f)
    if coverage['available_rows']<len(a)*.80:
        print('CALENDAR_MM_MAPPING_DIAGNOSTIC',
              json.dumps(dict(model_teams=a[['team_id','team']].drop_duplicates().to_dict('records'),
                 fixtures_teams=sorted(map(int,f.team_id.unique())),
                 missing_by_model_team=a.groupby(['team_id','team']).gap_since_team_last_pl_days.apply(lambda z:round(float(z.notna().mean()),3)).reset_index(name='mapped_fraction').to_dict('records'))),
              flush=True)
        raise AssertionError(f'Team fixture mapping weak: {coverage}')
    slices=news_summaries(a)
    scores=compare(a)
    jp=joao_2026_calendar()
    out=dict(classification='READ_ONLY_CALENDAR_AWARE_MM_AVAILABILITY_DIAGNOSTIC',
        coverage=coverage,gap_statistics=slices,
        model_ab=scores,joao_2026_calendar=jp,
        caveats=['Team and previous PL fixture kickoffs, not arbitrary GW counts',
                 'Match gaps do not prove no cup/international match for player',
                 '2025/26 GW29-38 reused historical diagnostic only, not independent promotion',
                 'Historical test model uses reconstructed existing MM outcomes and archived predeadline status',
                 'No future GW outcomes used for forecast features'],promoted=False,production_unchanged=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    for key,val in [('COVERAGE',coverage),('GAP',slices),('DEVELOPMENT',scores['dev']),
                    ('SELECTED',dict(selected_beta=scores['selected_beta'],
                       selected_test=scores['test_original_selected_medical'],
                       total_test=scores['test_original_selected_overall'])),
                    ('JOAO_2026',jp)]:
        print('CALENDAR_MM_'+key,json.dumps(val,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
