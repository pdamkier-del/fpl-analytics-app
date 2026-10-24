#!/usr/bin/env python3
"""One prespecified hierarchy alternative; report failures, never activate it.

Fit four anonymous role weights on 2024/25 only. Validate on the existing
2025/26 paired cohort, with exactly the same durations, PM and simulation seeds.
No player identities, Chelsea overrides or tuning on validation outcomes.
"""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from gk_joint_bridge import observations
from mm_locked_bridge import attach_mm
from individual_mm_evidence import load_frame
from run_vfinal_integrated import build_final_frame
import run_joint_gk_preview as engine
ROOT=Path(__file__).resolve().parents[1]
KEY=['fixture_uuid','player_uuid']


def role_groups(history,verified):
    obs=verified[verified.pos.eq('GK')].copy()
    obs['clock']=pd.to_datetime(obs.known_at,utc=True,format='mixed')
    obs['kick']=pd.to_datetime(obs.kickoff_at,utc=True,format='mixed')
    teams={(s,int(t)):g for (s,t),g in obs.groupby(['season','team_id'])}
    groups=[]
    for (season,fx,team),g in history[history.pos.eq('GK')].groupby(['season','fixture_uuid','team_id']):
        cut=pd.Timestamp(g.cutoff.iloc[0]);past=teams.get((season,int(team)))
        if past is None:continue
        past=past[past.clock.lt(cut)]
        if past.empty:continue
        last=past[past.kick.eq(past.kick.max())].set_index('player_uuid')
        roles=[]
        for pid in g.player_uuid:
            if pid not in last.index:roles.append(3);continue
            row=last.loc[pid]
            roles.append(0 if row.started==1 else 1 if row.minutes>0 else 2 if row.confirmed_squad else 3)
        # Role 3 includes the unrepresented outcome. It gets one group weight,
        # irrespective of how many registered keepers a club happens to have.
        roles=np.r_[roles,3];caps=np.r_[g.availability_cap.fillna(1).to_numpy(),1.]
        counts=np.bincount(roles,weights=(caps>0),minlength=4)
        truth=g.y.to_numpy();target=int(roles[np.argmax(truth)]) if truth.sum()==1 else None
        recent=past[past.started.eq(1)].sort_values('kick').tail(5)
        regular=recent.player_uuid.value_counts().index[0] if len(recent) else None
        cap_by=g.set_index('player_uuid').availability_cap
        regular_out=regular is not None and regular in cap_by and cap_by[regular]==0
        groups.append(dict(season=season,fixture=fx,team=int(team),cut=cut,rows=g,roles=roles,caps=caps,counts=counts,
            target=target,valid_label=target is not None and not any((truth>0)&(caps[:-1]==0)),regular_out=regular_out))
    return groups


def fit(groups):
    training=[g for g in groups if g['season']=='2024-25' and g['valid_label']]
    def loss(beta):
        value=.5*np.sum(beta*beta);grad=beta.copy()
        for g in training:
            p=np.exp(beta)*(g['counts']>0);p/=p.sum();y=g['target']
            value-=np.log(p[y]);grad+=p;grad[y]-=1
        return value,grad
    result=minimize(loss,np.zeros(4),jac=True,method='BFGS')
    if not result.success:raise ValueError('Hierarchy fit failed: '+result.message)
    return result.x,len(training)


def probabilities(group,beta):
    r,c,cap=group['roles'],group['counts'],group['caps']
    p=np.exp(beta)*(c>0);p/=p.sum()
    individual=np.divide(p[r],c[r],out=np.zeros(len(r)),where=c[r]>0)*(cap>0)
    individual=np.minimum(individual,cap)
    individual[-1]+=1-individual.sum()  # Preserve explicit availability caps.
    return individual


def main():
    out=ROOT/'work/joint-gk-hierarchy';out.mkdir(exist_ok=True)
    h=pd.read_csv(ROOT/'work/current-B-inputs/history.csv.gz',low_memory=False)
    verified=pd.read_csv(ROOT/'work/current-B-role-training/verified_observations.csv.gz',low_memory=False)
    groups=role_groups(h,verified);beta,n=fit(groups)
    test=[g for g in groups if g['season']=='2025-26' and int(g['rows'].gw.iloc[0])>=22]
    mapping={};cohorts={};roles={}
    for g in test:
        p=probabilities(g,beta)
        for pid,v,role in zip(g['rows'].player_uuid,p,g['roles']):
            mapping[(g['fixture'],pid)]=float(v);cohorts[(g['fixture'],pid)]=g['regular_out'];roles[(g['fixture'],pid)]=int(role)
    pm=build_final_frame();pm['season']='2025-26';pm=pm[pm.gw.between(22,38)].copy()
    frozen=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz')
    b=frozen[frozen.season.eq('2025-26')&frozen['mode'].eq('B')&frozen.gw.between(22,38)].copy()
    b=b.merge(pm[KEY+(['pos'] if 'pos'not in b else[])],on=KEY,validate='one_to_one')
    original=engine.prepare
    application={'candidate_team_fixtures':0,'fallback_team_fixtures':0}
    def candidate(inp,rows,duration,**kwargs):
        fx=rows.fixture_uuid.iloc[0] if 'fixture_uuid'in rows else active[0]
        # Missing history falls back to v1, rather than silently dropping rows.
        if not all((fx,p.player_id)in mapping for p in inp.players if p.is_keeper):
            application['fallback_team_fixtures']+=2
            return original(inp,rows,duration,**kwargs)
        application['candidate_team_fixtures']+=2
        new=rows.copy();new['new_p_start']=[mapping.get((fx,p),0.)for p in new.player_uuid]
        keepers={p.player_id for p in inp.players if p.is_keeper}
        players=tuple(replace(p,p_start=mapping[(fx,p.player_id)])if p.player_id in keepers else p for p in inp.players)
        return original(replace(inp,players=players),new,duration,incomplete_teams=(inp.home_team,inp.away_team))
    # run() provides one fixture at a time, retaining its exact seed offset.
    active=[None]
    # Obtain fixture identity without inferring it from player identity or time.
    # Add it to raw rows before the existing engine removes its index level.
    b['research_fixture_uuid']=b.fixture_uuid
    def wrapped(inp,rows,duration,**kwargs):
        active[0]=rows.research_fixture_uuid.iloc[0]
        return candidate(inp,rows,duration,**kwargs)
    engine.prepare=wrapped
    try:xp,details,audit,_=engine.run(attach_mm(pm,b),b,observations(ROOT),season='2025-26')
    finally:engine.prepare=original
    result=pd.read_csv(ROOT/'work/joint-gk-historical/paired-gk.csv.gz')
    candidate_xp=xp.set_index(KEY).xpts_fixture
    for name in ['p','minutes','xp']:result['candidate_'+name]=0.
    for i,row in result.iterrows():
        key=(row.fixture_uuid,row.player_uuid);d=details[key]
        result.loc[i,['candidate_p','candidate_minutes','candidate_xp']]=[d['p'],d['x'],candidate_xp.loc[key]]
    result['recent_regular_out']=[cohorts.get((r.fixture_uuid,r.player_uuid),False)for r in result.itertuples()]
    result['replacement_last_match']=[roles.get((r.fixture_uuid,r.player_uuid))==1 for r in result.itertuples()]
    metrics={}
    for label,part in [('all',result),('recent_regular_out',result[result.recent_regular_out]),('replacement_last_match',result[result.replacement_last_match])]:
        metrics[label]={}
        for arm,prefix in [('published_v1','after'),('hierarchy_candidate','candidate')]:
            error=part[prefix+'_xp']-part.total_points
            metrics[label][arm]=dict(rows=len(part),fixtures=int(part.fixture_uuid.nunique()),start_brier=float(((part[prefix+'_p']-part.actual_start)**2).mean())if len(part)else None,
                minute_mae=float(abs(part[prefix+'_minutes']-part.actual_minutes).mean())if len(part)else None,
                xp_mae=float(abs(error).mean())if len(part)else None,xp_bias=float(error.mean())if len(part)else None)
    # The prespecified alternative must improve starts and minutes without a
    # deterioration in point MAE. It is evidence, never automatic activation.
    old=metrics['all']['published_v1'];new=metrics['all']['hierarchy_candidate']
    supported=new['start_brier']<old['start_brier'] and new['minute_mae']<old['minute_mae'] and new['xp_mae']<=old['xp_mae']
    result.to_csv(out/'paired-gk.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    report=dict(candidate='Anonymous latest-squad role weights; one fixed specification, no validation tuning',training_season='2024-25',training_team_fixtures=n,
        validation_season='2025-26',validation_gws=list(range(22,39)),role_order=['last_starter','last_used_reserve','last_unused_bench','other_or_unlisted'],
        fitted_log_weights=beta.tolist(),application=application,metrics=metrics,supported=supported,activated=False,production_changed=False,
        limitations=['Reused research period, not independent certification.','Recent regular out means most frequent starter in prior five starts has a predeadline zero availability cap; not all injuries are captured.',
        'The last-match replacement subgroup is small; no reliable standalone injury-takeover calibration.',
        'Candidates sharing the same observed role share group mass; coach statements and cup selection are not quantitatively calibrated.'],
        decision='Retain published v1; candidate must not replace it.' if not supported else 'Candidate needs separate integration validation before activation.',
        all_team_gk_minutes_90=all(abs(a['analytic_gk_minutes']-90)<1e-8 for a in audit))
    engine.write(out/'summary.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
