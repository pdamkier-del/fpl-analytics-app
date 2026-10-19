#!/usr/bin/env python3
"""Isolated empirical-GK B→PM preview and historical paired replay.

Does not change a production configuration, manager state, or locked PM/TS.
"""
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone
import argparse,hashlib,json
import numpy as np
import pandas as pd
from gk_joint_bridge import DurationHistory,observations,prepare,VERSION,UNKNOWN
from mm_candidate_forecast import infer_B,seal_document
from mm_locked_bridge import attach_mm
from run_vfinal_integrated import make_vfinal_input
from run_live_vfinal_joint_simulation import POINT_COMPONENTS
from fpl_v1_1_model.joint_simulator import simulate_many
from pm_preview_distributions import simulate_with_distributions
from fpl_v1_1_model.forecast_snapshot import seal_forecast
ROOT=Path(__file__).resolve().parents[1]
KEY=['fixture_uuid','player_uuid']


def run(frame,predicted,obs,*,season,draws=400,incomplete_teams=(),seed=93000000,paired=False,offsets=None,role_policy=None,paired_v1=None,distributions=False):
    rows=[];baseline=[];details={};audit=[]
    raw=predicted.set_index(KEY)
    caches={}
    for i,(fx,g) in enumerate(frame.groupby('fixture_uuid',sort=True)):
        cut=str(g.cutoff.iloc[0]);history=caches.setdefault(cut,None)
        if history is None:history=DurationHistory(obs,cut);caches[cut]=history
        inp,_=make_vfinal_input(g)
        inp=replace(inp,bps_rules=season)
        if paired:
            base=simulate_many(inp,n=draws,seed=seed+(offsets[fx] if offsets is not None else i))
            for pid,s in base.items():baseline.append(dict(fixture_uuid=fx,player_uuid=pid,xpts=s['xPts'],minutes=s['expected_minutes']))
        mm=raw.loc[fx].reset_index()
        original_inp=inp
        inp,moments,teams=prepare(inp,mm,history,incomplete_teams=incomplete_teams,role_policy=role_policy,season=season)
        for team in teams: audit.append(dict(fixture_uuid=fx,**team,history_rows=history.rows,last_label_known_at=history.latest,cutoff=cut))
        sim=(simulate_with_distributions if distributions else simulate_many)(inp,n=draws,seed=seed+(offsets[fx] if offsets is not None else i))
        if paired_v1 is not None:
            old,old_moments,_=prepare(original_inp,mm,history,incomplete_teams=incomplete_teams)
            old_sim=sim if old.players==inp.players else simulate_many(old,n=draws,seed=seed+(offsets[fx] if offsets is not None else i))
            for p in original_inp.players:
                if p.is_keeper:
                    d=old_moments[p.player_id]
                    paired_v1.append(dict(fixture_uuid=fx,player_uuid=p.player_id,p=d['p'],xm=d['x'],pm=d['x'],p60=d['p60'],p90=d['p90'],xp=old_sim[p.player_id]['xPts']))
        if i%10==0:print('Joint GK fixture',i+1,'/',frame.fixture_uuid.nunique(),fx,flush=True)
        for pid,s in sim.items():
            if not np.isclose(sum(s[k]for k in POINT_COMPONENTS),s['xPts'],atol=1e-8):raise AssertionError('Unreconciled points')
            if pid.startswith(UNKNOWN):continue
            if (fx,pid) in raw.index and str(raw.loc[(fx,pid),'pos'])in('GK','GKP'):
                details[(fx,pid)]=moments[pid]
            rows.append(dict(fixture_uuid=fx,player_uuid=pid,gw=int(g.gw.iloc[0]),xpts_fixture=s['xPts'],expected_minutes=s['expected_minutes'],
                **{k:s[k] for k in POINT_COMPONENTS},penalty_miss_points=s['penalty_miss_points'],**({'distribution':s['distribution']} if distributions else {})))
        for team in (inp.home_team,inp.away_team):
            keepers=[p for p in inp.players if p.team==team and p.is_keeper]
            if abs(sum(sim[p.player_id]['expected_minutes'] for p in keepers)-90)>1e-8:raise AssertionError('Sampled GK coverage failure')
    return pd.DataFrame(rows),details,audit,pd.DataFrame(baseline)


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')


def current(inputs,out,*,paired=True):
    from build_live_vfinal_desktop import build
    inputs=Path(inputs);out=Path(out)
    h=pd.read_csv(inputs/'history.csv.gz',low_memory=False);t=pd.read_csv(inputs/'target.csv.gz',low_memory=False)
    prov=json.loads((inputs/'provenance.json').read_text());bootstrap=json.loads((inputs/'bootstrap.json').read_text())
    if datetime.now(timezone.utc)-datetime.fromisoformat(prov['data_at'])>pd.Timedelta(hours=24):raise ValueError('Not Available: stale current inputs')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(prov['origin_deadline'].replace('Z','+00:00')):raise ValueError('Expired deadline')
    evidence_path=ROOT/'work/gk-official-evidence/evidence.json'
    evidence=json.loads(evidence_path.read_text())
    fresh=json.loads((evidence_path.parent/'fpl_bootstrap.json').read_text())
    old={p['id']:p for p in bootstrap['elements']};new={p['id']:p for p in fresh['elements']}
    if set(old)!=set(new): raise ValueError('Official roster changed: rebuild original current B inputs')
    for pid in old:
        for key in ['now_cost','team','element_type','status','news','chance_of_playing_next_round']:
            if old[pid].get(key)!=new[pid].get(key):raise ValueError('Official catalogue/news changed: rebuild current B inputs: '+str(pid)+' '+key)
    if datetime.now(timezone.utc)-datetime.fromisoformat(evidence['observed_at'])>pd.Timedelta(hours=24):raise ValueError('Stale squad evidence')
    incomplete=(evidence['team_id'],) if evidence['unlisted_competitors'] else ()
    from gk_solo_role import mark_horizon_absences
    pred,_=infer_B(h,t,prov);pred=mark_horizon_absences(pred,fresh);pm=pd.read_csv(inputs/'pm.csv.gz',low_memory=False);joined=attach_mm(pm,pred)
    from gk_solo_role import load_policy
    policy=load_policy(ROOT,h);v1=[] if paired else None
    role_evidence=policy.squads.sort_values(['season','team_id','kick','player_uuid']).to_csv(index=False).encode()
    policy.receipt['squad_evidence_sha256']=hashlib.sha256(role_evidence).hexdigest()
    import gzip
    out.mkdir(parents=True,exist_ok=True)
    (out/'role-squad-evidence.csv.gz').write_bytes(gzip.compress(role_evidence,mtime=0))
    xp,details,audit,baseline=run(joined,pred,observations(ROOT),season='2026-27',incomplete_teams=incomplete,paired=paired,role_policy=policy,paired_v1=v1,distributions=True)
    if paired:write(out/'before-v1.json',dict(players=v1))
    display=joined.copy();updated=pred.copy();mmrows=[]
    for index,r in updated.iterrows():
        key=(r.fixture_uuid,r.player_uuid)
        if key not in details:continue
        d=details[key]
        for name in ['p','q','s','c','x']:updated.loc[index,name]=d[name]
        ix=display.fixture_uuid.eq(r.fixture_uuid)&display.player_uuid.eq(r.player_uuid)
        for name,col in [('p','control_p_start'),('q','p_cameo_given_bench'),('x','control_xmins')]:display.loc[ix,col]=d[name]
        mass=np.array(d['pmf']);lo=int(np.searchsorted(np.cumsum(mass),.1));hi=int(np.searchsorted(np.cumsum(mass),.9))
        mmrows.append(dict(fixture_id=r.fixture_uuid,player_id=r.player_uuid,team_id=int(r.team_id),gw=int(r.gw),
            p_start=d['p'],xmins=d['x'],p_60_plus=d['p60'],p_90=d['p90'],p_play=d['p_play'],
            start_minutes=d['s'],p_sub_given_not_start=d['q'],sub_minutes=d['c'],minute_pmf=d['pmf'],
            interval80=[lo,hi],interval_status='empirical model distribution; independent coverage calibration not certified'))
    # Existing locked exporter reads original controls for outfield players.
    for col,src in [('control_p_start','v4_workload_start_p_start'),('p_cameo_given_bench','v4_p_cameo_given_bench'),('control_xmins','v4_workload_start_xmins')]:
        non=~display.pos.isin(['GK','GKP']);display.loc[non,col]=display.loc[non,src]
    display['expected_minutes']=display.control_xmins
    aligned=pred.set_index(KEY).reindex(pd.MultiIndex.from_frame(display[KEY]))
    display['live_eligibility_applied']=(aligned.news_eligible&aligned.news_state.isin(['OUT','SUSPENDED'])).to_numpy()
    payload=build(display,xp,bootstrap,json.loads((inputs/'bps-audit.json').read_text()))
    distributions=xp.set_index(KEY)['distribution'].to_dict()
    for p in payload['players']:
        for w in p['weeks']:
            for f in w['fixtures']:
                f['distribution']=distributions[(f['fixture_uuid'],p['player_uuid'])]
                d=details.get((f['fixture_uuid'],p['player_uuid']))
                if d:
                    f.update(p_60_plus=d['p60'],p_90=d['p90'],pm_analytic_minutes=d['x'],goalkeeper_model=VERSION)
    payload.update(goalkeeper_role_fit=policy.receipt,gk_horizon_absences=[{k:p.get(k)for k in ['id','web_name','news']}for p in fresh['elements']if p['id']in set(pred.loc[pred.role_horizon_absence,'fpl_element'])],official_gk_status={str(p['id']):{k:p.get(k) for k in ['status','news','chance_of_playing_next_round']} for p in fresh['elements'] if p['element_type']==1},data_asof=max(prov['data_at'],evidence['observed_at']),component_source_asof={'original_B_PM':prov['data_at'],'official_GK_roster':evidence['observed_at']},official_gk_evidence=evidence,model=VERSION,scope='prospective_preview',minute_sampler_audit={'sampler':VERSION,'goalkeeper_MM_to_PM_mean_consistent':True},
        parts={'mm':'experimental_GK','pm_vfinal':'experimental_joint_GK','ts':'original_unchanged'},gk_team_fixtures=audit)
    payload['blockers'].append('Experimental joint GK/11-starter sampler; not production-certified. Unlisted competitors are pooled, not individual FPL forecasts.')
    payload['code_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['scripts/gk_joint_bridge.py','scripts/run_joint_gk_preview.py','scripts/mm_candidate_forecast.py','scripts/gk_solo_role.py','src/fpl_v1_1_model/joint_simulator.py','scripts/pm_preview_distributions.py']}
    payload['input_sha256']={name:hashlib.sha256((inputs/name).read_bytes()).hexdigest() for name in ['pm.csv.gz','history.csv.gz','target.csv.gz','provenance.json']}
    payload=seal_forecast(payload)
    write(out/'baseline-mm.json',dict(players=[dict(fixture_id=r.fixture_uuid,player_id=r.player_uuid,p_start=float(r.p),xmins=float(r.x),start_minutes=float(r.s),p_sub_given_not_start=float(r.q),sub_minutes=float(r.c))for r in pred.itertuples()]));
    write(out/'forecast.json',payload);write(out/'gk-mm.json',dict(model=VERSION,players=mmrows))
    write(out/'gk-audit.json',dict(model=VERSION,team_fixtures=audit,draws_per_fixture=400,point_components_reconciled=True,production_changed=False))
    if paired:baseline.to_csv(out/'paired-baseline.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,default=ROOT/'work/current-B-inputs');ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--no-baseline',action='store_true')
    args=ap.parse_args();p=current(args.inputs,args.out,paired=not args.no_baseline)
    print(json.dumps(dict(players=len(p['players']),fixtures=p['fixtures'],gws=p['gws'],forecast_sha256=p['forecast_sha256'])))
if __name__=='__main__':main()
