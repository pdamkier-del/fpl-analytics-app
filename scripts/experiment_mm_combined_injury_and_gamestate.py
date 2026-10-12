#!/usr/bin/env python3
"""Read-only A/B of BOTH post-injury recovery and large-lead substitutions in full MM.

Actual 2025/26 starter event substitutions are scored at the exact score WHEN
substituted (FotMob event.homeScore/awayScore). Verified event IDs are linked
to the original PL lineup UUID roster; ONLY completed past fixtures may enter
future player features. A documented score >=3 and 55-83' is considered
possible tactical preservation, NOT proof of the coach's intention.

Builds unchanged MM via full_mm and runs actual original relative-XI optimizer,
residual and exact-11 constrained starter probabilities. The only modifications
are a medically documented returner prior before XI and a modest conditional
starter minute correction after XI. No permanent model changes.
GW6-15 train, GW16-21 select, GW6-21 refit, GW22-38 reused diagnostic.
"""
from __future__ import annotations
import json,sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit,logit
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from experiment_mm_big_lead_starter_substitution import fixtures,extract,scored
from experiment_mm_full_calendar_features import build_calendar,NEWS,RATINGS,POLICY
from run_mm_unified_official_roles import SOURCE,full_mm,compose,CLASSIFIED,read_all,base_identity
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_mm_v2_team_news_availability_experiment import policy_caps,RATING_CFG,L2
from fpl_v1_1_model.availability_projection import project_exact_starters_with_caps
from run_mm_v2_relative_rating_competition import add_relative_xi_features
from run_mm_v2_xi_rating_experiment import ASSIGN_FEATURES,fit_residual
OUT=ROOT/'work/live-final-model/mm_combined_medical_return_and_lead_substitution.json'

def score_metrics(frame,mask,p,q,sub,minutes):
    # Equivalent to original saved metrics, using conditional durations only.
    x=p*minutes+(1-p)*q*sub
    return metrics(frame,mask,p,q,x)

def load_game_events(frame):
    ff=fixtures()
    collected=[];err={};exclusions=0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures={ex.submit(extract,f):f for f in ff}
        for k,t in enumerate(as_completed(futures),1):
            f=futures[t]
            z,e=t.result()
            if e:err[str(f['id'])]=e
            elif z.get('discard') is not None:exclusions+=1
            else:collected.extend(z['rows'])
            if k%100==0:print('FULL_COMBINED_MATCH_EVENTS',json.dumps(dict(done=k,all=len(ff),accepted_sides=len(collected)//11,errors=len(err))),flush=True)
    matches=len(set(z['match_id'] for z in collected))
    if matches<300:raise ValueError(f'Coverage insufficient: {matches} verified matches')
    # ID bridge anchored in original MM's PL confirmed XI archive, not fuzzy
    # resemblance of player names or team numerical provider IDs.
    classified=pd.read_csv(CLASSIFIED,low_memory=False)
    lines=read_all('lineups')
    lines,team_codes=base_identity(lines,classified)
    # The archived FPL-core player_id is NOT the FotMob matchDetails
    # player ID: they have different namespaces. Match only on the same
    # CONFIRMED 11-player sheet, home/away side and UNIQUE normalized
    # surname. The first initial must match as an additional safety guard.
    # Ambiguous surnames are discarded, never guessed.
    import re,unicodedata
    def tokens(name):
        q=unicodedata.normalize('NFKD',str(name))
        q=''.join(z for z in q if not unicodedata.combining(z))
        return re.findall(r'[a-z]+',q.lower())
    def last(name):
        t=tokens(name)
        return t[-1] if t else ''
    def initial(name):
        t=tokens(name)
        return t[0][0] if t else ''
    pl=lines[lines.match_id.astype(str).str.contains('25-26-prem-')&
             lines.player_uuid.notna()&
             lines.is_starting.astype(str).str.lower().isin(['true','1','yes'])].copy()
    pl['surname']=pl.player_name.map(last)
    pl['first_initial']=pl.player_name.map(initial)
    pl['team_id']=pl.team_code.map(team_codes)
    unique=pl[['match_id','team_side','surname','first_initial','player_uuid','team_id']].drop_duplicates()
    unique=unique[unique.surname.ne('')&unique.team_id.notna()]
    unique=unique[~unique.duplicated(['match_id','team_side','surname'],keep=False)]
    z=pd.DataFrame(collected)
    z['team_side']=np.where(z.home,'home','away')
    z['surname']=z.name.map(last)
    z['first_initial']=z.name.map(initial)
    z=z[z.surname.ne('')]
    z=z[~z.duplicated(['match_id','team_side','surname'],keep=False)]
    z=z.merge(unique,on=['match_id','team_side','surname'],how='inner',
              validate='one_to_one',suffixes=('_event','_lineup'))
    z=z[z.first_initial_event.eq(z.first_initial_lineup)].copy()
    z['team_id']=z.team_id.astype(int)
    z['kickoff']=pd.to_datetime(z.kickoff,utc=True)
    if z.duplicated(['match_id','player_uuid']).any():raise ValueError('Ambiguous event lineup identity')
    # For a full MM test, we need high coverage before proceeding, but never
    # relax identity safety to chase that coverage.
    if len(z)<4500:raise ValueError(f'Insufficient unique event-to-UUID starter mapping: {len(z)}')
    return z,dict(provider_matches=len(ff),verified_used_matches=matches,
                  events_matched_to_uuid=len(z),role_lineup_name_anchors=len(unique),
                  provider_errors=len(err),excluded_matches=exclusions,errors_sample=dict(list(err.items())[:5]))

def attach_game_state(f,events):
    # For target row, only games with kickoff+3hr < original pre-deadline
    # can provide signal. Team fixtures inferred via same verified match IDs
    # as the lineup identities. Past >=4/5 starts needed to identify a star.
    f=f.copy().reset_index(drop=True)
    cutoff=pd.to_datetime(f.cutoff,utc=True)
    games=events[['match_id','team_id','kickoff']].drop_duplicates().sort_values('kickoff')
    teamhist={int(t):g.to_dict('records') for t,g in games.groupby('team_id')}
    playerhist={str(pid):g.to_dict('records') for pid,g in events.groupby('player_uuid')}
    for p in playerhist:playerhist[p].sort(key=lambda v:v['kickoff'])
    delta=[];prior_lead=[];last_lead=[];star=[];nb=[];leak=0
    for i,row in enumerate(f.itertuples(index=False)):
        c=cutoff.iloc[i];tid=int(row.team_id);pid=str(row.player_uuid)
        beforeteam=[g for g in teamhist.get(tid,[]) if g['kickoff']+pd.Timedelta(hours=3)<c]
        beforeteam=beforeteam[-5:]
        ids={g['match_id'] for g in beforeteam}
        before=[z for z in playerhist.get(pid,[]) if
                z['team_id']==tid and z['match_id'] in ids and
                z['kickoff']+pd.Timedelta(hours=3)<c]
        before.sort(key=lambda v:v['kickoff'])
        is_star=(len(beforeteam)==5 and len(before)>=4 and
                 np.mean([z['minutes'] for z in before])>=75)
        last3=before[-3:]
        m=[v for v in last3 if v['substituted'] and not v['injured_sub'] and
           55<=v['minutes']<=83 and v['lead_at_sub'] is not None and v['lead_at_sub']>=3]
        # Only a documented prior game state can correct a single past
        # substitution; do not apply a blanket 85-minute assumption.
        correct=(scored(last3,row,'impute85')-scored(last3,row,'original')) if is_star and m else 0.
        delta.append(float(np.clip(correct,0,15)))
        prior_lead.append(bool(is_star and m))
        last_lead.append(bool(is_star and last3 and last3[-1] in m))
        star.append(bool(is_star))
        nb.append(len(before))
    f['blowout_duration_delta']=delta
    f['prior_blowout_eligible']=prior_lead
    f['last_game_blowout_eligible']=last_lead
    f['established_star_at_cutoff']=star
    return f,dict(events=len(events),star_rows=int(sum(star)),
        eligible_target_rows=int(sum(prior_lead)),last_match_eligible_rows=int(sum(last_lead)),
        max_duration_delta=float(max(delta)),rows=len(f))

def run_arm(frame,train,base,q,sub,caps,medical_strength,lead_strength):
    # Identical pipeline for baseline and all candidate arms. Only returner
    # P(start) prior and scorer-verified past conditional start duration vary.
    m=frame.cal_medical_return_starter.to_numpy(float)
    pre=project_exact_starters_with_caps(frame,base,caps)
    if medical_strength:
        pre=project_exact_starters_with_caps(frame,
            expit(logit(np.clip(pre,1e-8,1-1e-8))+medical_strength*m),caps)
    feat=add_relative_xi_features(frame,pre,RATING_CFG)
    pfit,_=fit_residual(feat,pre,train,ASSIGN_FEATURES,L2)
    p=project_exact_starters_with_caps(feat,pfit,caps)
    if (pd.DataFrame({'key':feat.fixture_uuid.astype(str)+'#'+feat.team_id.astype(str),
                      'p':p}).groupby('key').p.sum()-11).abs().max()>1e-6:
        raise AssertionError('XI start sum no longer 11')
    # Candidate duration only increases the frozen starter conditional mean
    # for players whose prior match actually qualifies. Never inflate >90.
    duration=np.clip(frame.start_minutes_mean.to_numpy(float)+
                     lead_strength*frame.blowout_duration_delta.to_numpy(float),0.,90.)
    xm=p*duration+(1-p)*q*sub
    if not np.isfinite(xm).all():raise AssertionError('NaN xM')
    return p,duration,xm

def metrics_slices(f,mask,p,q,sub,duration):
    slices={'all':mask,
        'medical_return':mask & f.cal_medical_return_starter.ge(.5).to_numpy(),
        'established_star':mask & f.established_star_at_cutoff.to_numpy(bool),
        'after_big_lead_sub':mask & f.prior_blowout_eligible.to_numpy(bool),
        'last_big_lead_sub':mask & f.last_game_blowout_eligible.to_numpy(bool),
        'other':mask & ~f.prior_blowout_eligible.to_numpy(bool) &
                ~f.cal_medical_return_starter.ge(.5).to_numpy(bool)}
    out={}
    for key,z in slices.items():
        if z.sum()>=1:
            o=score_metrics(f,z,p,q,sub,duration)
            out[key]=dict(n=int(z.sum()),state_log_loss=round(float(o['state_log_loss']),6),
                  start_brier=round(float(o['state_brier']),6),
                  xmins_mae=round(float(o['xmins_mae']),6),
                  xmins_rmse=round(float(o['xmins_rmse']),6),
                  xmins_bias=round(float(o['xmins_bias']),6))
        else:out[key]=None
    return out

def main():
    f=add_sequence_features(pd.read_csv(SOURCE,low_memory=False).reset_index(drop=True))
    f=add_perf_features(f,build_perf_ledger())
    f=build_rating_features(f,pd.read_csv(RATINGS))
    f=build_strict_team_news_features(f,read_split_gzip_jsonl(NEWS,'predeadline_strict.jsonl.gz'))
    f,cal=build_calendar(f)
    events,evt=load_game_events(f)
    f,features=attach_game_state(f,events)
    print('FULL_MM_EVENT_LINKAGE',json.dumps(dict(source=evt,features=features,
      subs_with_valid_leads=int(events.lead_at_sub.ge(3).sum()),
      match_starters_identified=int(events.player_uuid.nunique()),
      sample_medical=int(f.cal_medical_return_starter.sum()))),flush=True)
    if features['eligible_target_rows']<8:raise ValueError('Too few documented historical prior big leads: '+str(features))
    known=pd.to_datetime(f.outcome_known_at,utc=True)
    configs=[
      ('original',0.,0.),('medical_0.4',.4,0.),('medical_0.8',.8,0.),
      ('lead_0.5',0.,.5),('lead_1.0',0.,1.),
      ('combined_0.4_0.5',.4,.5),('combined_0.4_1.0',.4,1.),
      ('combined_0.8_1.0',.8,1.)]
    dev=f.gw.between(16,21).to_numpy()
    tr=(f.gw.between(6,15)&known.lt(pd.to_datetime(f.loc[dev,'cutoff'],utc=True).min())).to_numpy()
    base,q,sub,_,_=full_mm(f.copy(),tr)
    caps=policy_caps(f,POLICY)
    scores={}
    predictions={}
    for name,medical,lead in configs:
        p,d,x=run_arm(f,tr,base,q,sub,caps,medical,lead)
        scored=metrics_slices(f,dev,p,q,sub,d)
        scores[name]=scored
        if name=='original':predictions['dev_original']=(p,d)
        print('FULL_MM_COMBINED_DEV',json.dumps(dict(variant=name,results=scored),ensure_ascii=False),flush=True)
    orig=scores['original']['all']
    eligible=[]
    for name,m,l in configs[1:]:
        a=scores[name]['all']
        affected=scores[name]['after_big_lead_sub']
        affected0=scores['original']['after_big_lead_sub']
        med=scores[name]['medical_return'];med0=scores['original']['medical_return']
        # Select only on chronological development, with population errors
        # not worse and positive evidence for at least one affected slice.
        if (a['xmins_mae']<=orig['xmins_mae']+.01 and
            a['xmins_rmse']<=orig['xmins_rmse']+.01 and
            a['state_log_loss']<=orig['state_log_loss']+.0005 and
            ((affected and affected0 and affected['n']>=8 and
              affected['xmins_mae']<affected0['xmins_mae']-.1) or
             (med and med0 and med['n']>=10 and
              med['xmins_rmse']<med0['xmins_rmse']-.1))):
            eligible.append(name)
    selected=min(eligible,key=lambda k:(
        scores[k]['all']['xmins_rmse'],scores[k]['all']['xmins_mae'])) if eligible else 'original'
    test=f.gw.between(22,38).to_numpy()
    tr2=(f.gw.between(6,21)&known.lt(pd.to_datetime(f.loc[test,'cutoff'],utc=True).min())).to_numpy()
    base2,q2,sub2,_,_=full_mm(f.copy(),tr2)
    tests={}
    for name,medical,lead in configs:
        if name not in ('original',selected):continue
        p,d,x=run_arm(f,tr2,base2,q2,sub2,caps,medical,lead)
        tests[name]=metrics_slices(f,test,p,q2,sub2,d)
        print('FULL_MM_COMBINED_TEST',json.dumps(dict(variant=name,results=tests[name]),ensure_ascii=False),flush=True)
    report=dict(classification='READ_ONLY_FULL_MM_MEDICAL_AND_SCORE_STATE_COMBINED_AB',
      underlying_model='exact original full_mm performance, qsub, sub duration and XI role competition',
      data_sources=dict(calendars=cal,event_provider=evt,affected=features),
      train_select='GW6-15 fit, GW16-21 development selection only',
      validation='GW6-21 fit, GW22-38 reused diagnostic not independent',
      candidates={n:dict(medical_logit=m,early_blowout_duration_scale=l) for n,m,l in configs},
      dev=scores,selected_on_dev=selected,
      test_reused=tests,qualification='Reused 2025/26 historical diagnostic, not an independent season. No model or app change.',
      exact_expected_11=True,production_changed=False,app_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('FULL_MM_COMBINED_FINAL',json.dumps(dict(selected=selected,
          event_coverage=evt,affected=features,
          original_test=tests['original'],
          chosen_test=tests[selected]),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
