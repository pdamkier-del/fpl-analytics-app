#!/usr/bin/env python3
"""Validate the sole-established-GK correction; never tune to Penders.

Use the complete frozen 2025/26 GW6–38 MM cohort, including the early injury
transitions omitted by the narrower PM replay. PM is scored only where genuine
frozen PM inputs exist; unchanged match inputs reuse their exact v1 draws.
"""
from pathlib import Path
from dataclasses import replace
import json
import numpy as np
import pandas as pd
from gk_solo_role import load_policy
from gk_joint_bridge import DurationHistory,observations,prepare,UNKNOWN
from individual_mm_evidence import load_frame
from fpl_v1_1_model.joint_simulator import MatchSimInput,PlayerSimInput
from run_joint_gk_preview import ROOT,write,run
from run_vfinal_integrated import build_final_frame,make_vfinal_input
from mm_locked_bridge import attach_mm
KEY=['fixture_uuid','player_uuid']


def metrics(f,prefix):
    return dict(rows=len(f),fixtures=int(f.fixture_uuid.nunique()),start_brier=float(((f[prefix+'_p']-f.actual_start)**2).mean()),
        minute_mae=float(abs(f[prefix+'_minutes']-f.actual_minutes).mean()),minute_bias=float((f[prefix+'_minutes']-f.actual_minutes).mean()),
        p60_brier=float(((f[prefix+'_p60']-f.actual_minutes.ge(60))**2).mean()),p90_brier=float(((f[prefix+'_p90']-f.actual_minutes.eq(90))**2).mean()))


def main():
    out=ROOT/'work/joint-gk-role-validation';out.mkdir(exist_ok=True)
    h=pd.read_csv(ROOT/'work/current-B-inputs/history.csv.gz',low_memory=False);policy=load_policy(ROOT,h);obs=observations(ROOT)
    b=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz')
    b=b[b.season.eq('2025-26')&b['mode'].eq('B')].copy()
    fields=h[['season']+KEY+['pos','availability_cap','news_state']].rename(columns={'news_state':'verified_news_state'})
    b=b.merge(fields,on=['season']+KEY,validate='one_to_one');gk=b[b.pos.eq('GK')].copy()
    cache={};records=[];case_audit=[];all_coverage=[]
    for fx,g in gk.groupby('fixture_uuid',sort=True):
        cut=str(g.cutoff.iloc[0])
        if cut not in cache:cache[cut]=DurationHistory(obs,cut)
        teams=sorted(g.team_id.astype(str).unique())
        if len(teams)!=2:raise ValueError('Incomplete historical fixture')
        players=tuple(PlayerSimInput(r.player_uuid,str(r.team_id),'GK',float(r.p),float(r.q),float(r.s),float(r.c),is_keeper=True)for r in g.itertuples())
        inp=MatchSimInput(teams[0],teams[1],1.,1.,players)
        _,old,_=prepare(inp,g,cache[cut])
        _,new,audit=prepare(inp,g,cache[cut],role_policy=policy,season='2025-26')
        for a in audit:
            applied=a['role_allocation']['applied'];all_coverage.append(abs(a['analytic_gk_minutes']-90)<1e-8)
            if applied:case_audit.append(dict(fixture_uuid=fx,gw=int(g.gw.iloc[0]),**a))
        changed_teams={a['team']for a in audit if a['role_allocation']['applied']}
        for r in g.itertuples():
            pid=r.player_uuid;records.append(dict(fixture_uuid=fx,player_uuid=pid,team_id=int(r.team_id),gw=int(r.gw),actual_start=float(r.y),actual_minutes=float(r.minutes),
                role_applied=str(r.team_id)in changed_teams,**{arm+'_'+name:detail[pid][source]for arm,detail in [('v1',old),('v2',new)]for name,source in [('p','p'),('minutes','x'),('p60','p60'),('p90','p90')]}))
    result=pd.DataFrame(records);result.to_csv(out/'paired-mm.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    mm={name:{arm:metrics(part,arm)for arm in ['v1','v2']}for name,part in [('all',result),('affected',result[result.role_applied])]if len(part)}
    # Matched PM cohort and identical seeds/rates. Only simulate changed inputs.
    pm=build_final_frame();pm['season']='2025-26';pm=pm[pm.gw.between(22,38)].copy()
    subset=b.merge(pm[KEY],on=KEY,validate='one_to_one');frame=attach_mm(pm,subset)
    prior=pd.read_csv(ROOT/'work/joint-gk-historical/paired-gk.csv.gz');xp_rows=[];changed_fx=[];pm_audit=[]
    offsets={fx:i for i,fx in enumerate(sorted(frame.fixture_uuid.unique()))}
    for fx,g in frame.groupby('fixture_uuid',sort=True):
        cut=str(g.cutoff.iloc[0])
        if cut not in cache:cache[cut]=DurationHistory(obs,cut)
        inp,_=make_vfinal_input(g);inp=replace(inp,bps_rules='2025-26');rows=subset[subset.fixture_uuid.eq(fx)]
        before,_,_=prepare(inp,rows,cache[cut]);after,_,audit=prepare(inp,rows,cache[cut],role_policy=policy,season='2025-26')
        pm_audit.extend(audit)
        if before.players==after.players:continue
        changed_fx.append(fx)
    if changed_fx:
        chosen=frame[frame.fixture_uuid.isin(changed_fx)];chosen_pred=subset[subset.fixture_uuid.isin(changed_fx)]
        simulated,_,_,_=run(chosen,chosen_pred,obs,season='2025-26',role_policy=policy,offsets=offsets)
        xp_rows=simulated.set_index(KEY).xpts_fixture
    before_xp=[];after_xp=[]
    for r in prior.itertuples():
        before_xp.append(r.after_xp)
        after_xp.append(float(xp_rows.loc[(r.fixture_uuid,r.player_uuid)])if r.fixture_uuid in changed_fx else r.after_xp)
    pm_metrics={}
    for name,values in [('v1',before_xp),('v2',after_xp)]:
        e=np.asarray(values)-prior.total_points.to_numpy();pm_metrics[name]=dict(rows=len(prior),fixtures=int(prior.fixture_uuid.nunique()),xp_mae=float(abs(e).mean()),xp_bias=float(e.mean()))
    accepted=mm['all']['v2']['start_brier']<=mm['all']['v1']['start_brier'] and mm['all']['v2']['minute_mae']<=mm['all']['v1']['minute_mae']and pm_metrics['v2']['xp_mae']<=pm_metrics['v1']['xp_mae'] and all(all_coverage)
    report=dict(model='B-GK-role-aware-v2',accepted=bool(accepted),production_changed=False,fit=policy.receipt,mm_metrics=mm,pm_metrics=pm_metrics,
        role_applied_team_fixtures=len(case_audit),all_gk_team_minutes_90=all(all_coverage),pm_changed_fixtures=len(changed_fx),pm_all_gk_minutes_90=all(abs(a['analytic_gk_minutes']-90)<1e-8 for a in pm_audit),
        cases=case_audit,validation_season='2025-26',gws=sorted(result.gw.unique().astype(int).tolist()),
        limitations=['Reused research period, not independent certification.','Sole-candidate validation subgroup is small; retain explicit posterior/model uncertainty.',
        'PM point metrics cover GW22–38 only; if no role-change cases fall in this window, unchanged xP is regression evidence, not proof of better takeover points.',
        'Historical known-at inherits existing kickoff-delay proxies. Future injury recovery is not inferred.'])
    write(out/'summary.json',report);print(json.dumps(report,indent=2),flush=True)
    if not accepted:raise ValueError('Sole-role correction failed historical gate')
if __name__=='__main__':main()
