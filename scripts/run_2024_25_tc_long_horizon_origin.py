#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sqlite3,sys
from dataclasses import replace
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline
from fpl_v1_1_model.joint_simulator import simulate_many_samples
from fpl_v1_1_model.role_event_priors import QCOLS
from fpl_v1_1_model.vfinal_replay_state import fit_team_latent
from run_rolling_vfinal_gw6_38 import load_models,bps_bounds
from run_bps_background_experiment import actual_background_ledger,feature_frame as bps_features,apply_model as bps_apply
from run_vfinal_integrated import make_vfinal_input
from vfinal_replay_components import build_fixture_components
from run_2024_25_conditional_mm import jsonl_gz,perf_ledger,norm
from run_2024_25_conditional_pm import bps_ledger_2024,penalty_history_2024,penalty_state,team_map

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',required=True);ap.add_argument('--derived',required=True)
    ap.add_argument('--source',required=True);ap.add_argument('--mm',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--origin',type=int,required=True)
    ap.add_argument('--period-end',type=int,required=True);ap.add_argument('--draws',type=int,default=400)
    ap.add_argument('--top-k',type=int,default=20)
    a=ap.parse_args()
    origin=int(a.origin)
    if not (6<=origin<=38 and origin<=a.period_end<=38):raise ValueError('bad origin/end')
    derived=Path(a.derived);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    src=pd.read_csv(a.source).reset_index(drop=True);mm=pd.read_csv(a.mm)
    src['cutoff']=pd.to_datetime(src.cutoff,utc=True);mm['cutoff']=pd.to_datetime(mm.cutoff,utc=True)
    models=load_models()
    obs=jsonl_gz(derived/'all_competition_player_observations.jsonl.gz')
    perf=perf_ledger(obs);bpsledger=bps_ledger_2024(obs)
    lo,hi=bps_bounds(src,actual_background_ledger())

    con=sqlite3.connect(Path(a.db))
    ph=pd.read_sql_query("""SELECT season,fixture_uuid,player_uuid,team_id,opponent_team_id,gw,kickoff_at,fpl_position,
      minutes,xg,xa,defcon_count,yellow_cards,fpl_red_cards,own_goals,goals,fpl_assists
      FROM player_fixture_observations WHERE season='2024-25' AND is_final=1""",con)
    th=pd.read_sql_query("""SELECT season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,xg
      FROM team_fixture_observations WHERE season='2024-25' AND source_name='vaastav_historical_core'""",con)
    sot=pd.read_sql_query("""SELECT season,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,
      shots_on_target,shots_on_target_conceded FROM team_fixture_observations
      WHERE season='2024-25' AND source_name='football_data_co_uk'""",con)
    con.close()
    for x in (ph,th,sot):
        x['kickoff_at']=pd.to_datetime(x.kickoff_at,utc=True);x['available_at']=x.kickoff_at+pd.Timedelta(hours=4)
    ph=ph.drop_duplicates(['fixture_uuid','player_uuid']);ph['defcon_count']=pd.to_numeric(ph.defcon_count,errors='coerce').fillna(0.)
    for col in ['xg','xa','minutes','yellow_cards','fpl_red_cards','own_goals','goals','fpl_assists']:
        ph[col]=pd.to_numeric(ph[col],errors='coerce').fillna(0.)

    fixtures=pd.read_csv(derived/'pl_fixture_actuals.csv')
    fixtures['kickoff']=pd.to_datetime(fixtures.kickoff_time,utc=True)
    fixtures=fixtures[fixtures.event.notna()].copy();fixtures['event']=fixtures.event.astype(int)
    sched=fixtures.rename(columns={'id':'match_id','event':'gameweek','team_h':'home_team_id','team_a':'away_team_id'})
    cands=jsonl_gz(derived/'deadline_player_candidates.jsonl.gz');tmap=team_map(cands)
    pens=penalty_history_2024(obs,fixtures,tmap)
    identity=pd.read_csv(derived/'player_identity.csv').dropna(subset=['player_uuid'])
    mp=dict(zip(identity.player_uuid.astype(str),identity.fpl_element.astype(int)))
    rolehist=src[['fixture_uuid','player_uuid','team_id','cutoff','max_history_known_at']+QCOLS].copy()

    cutoff=src.loc[src.gw.eq(origin),'cutoff'].min()
    sstate=src[src.gw<=origin].sort_values(['gw','cutoff']).drop_duplicates('player_uuid',keep='last').copy()
    mstate=mm[mm.gw<=origin].sort_values(['gw','cutoff']).drop_duplicates('player_uuid',keep='last').copy()
    state=sstate.merge(mstate[['player_uuid','new_p_start','new_xmins','new_q_sub','new_sub_minutes','new_start_minutes']],
                       on='player_uuid',how='inner',validate='one_to_one')
    state['cutoff']=cutoff
    bf=bps_features(state,3.,bpsledger);state['bg_mean_rate90']=np.clip(bps_apply(bf,models['bps']),lo,hi)
    broad=state.pos.replace({'G':'GK','GKP':'GK'}).astype(str);sd=models['bpsvar']['position_sd90']
    state['bg_sd90']=[float(sd.get(p,models['bpsvar']['global_sd90'])) for p in broad]

    fx=sched[sched.gameweek.between(origin,int(a.period_end)) & (sched.kickoff>=cutoff)].drop_duplicates('match_id').copy()
    if fx.empty:raise ValueError('no future fixtures')
    lambdas=fit_team_latent(th[th.available_at<=cutoff],fx[['match_id','home_team_id','away_team_id']],origin)
    past=ph[ph.available_at<=cutoff].copy()
    goals=float(past.goals.sum());assist_prob=min(1.,max(.5,float(past.fpl_assists.sum())/goals)) if goals>0 else .7
    ps,plam=penalty_state(origin,state,pens,fixtures,models['pen'])
    bmean=state.set_index('player_uuid').bg_mean_rate90.to_dict();bsd=state.set_index('player_uuid').bg_sd90.to_dict()

    sample_sums={};meta={};counter=0
    for fr in fx.itertuples(index=False):
        home=int(fr.home_team_id);away=int(fr.away_team_id)
        rg=state[state.team_id.astype(int).isin([home,away])].copy()
        if rg.empty:continue
        rg['fixture_uuid']=f'tc24-o{origin}-{int(fr.match_id)}'
        rg['home_team_id']=home;rg['away_team_id']=away
        rg['opponent_team_id']=np.where(rg.team_id.astype(int)==home,away,home)
        rg['was_home']=rg.team_id.astype(int)==home;rg['evidence_at']=cutoff
        rg['expected_minutes']=rg.new_xmins.astype(float);rg['pos']=rg.pos.replace({'G':'GK'})
        rg=rg.drop(columns=[x for x in rg.columns if str(x).startswith('perf_')],errors='ignore')
        hgoal,agoal=lambdas[str(fr.match_id)]
        rg=build_fixture_components(rg,past,rolehist,cutoff,models['attack'],models['dc'],models['neg'],
          models['ga'],models['dc_model'],models['dc_cal'],perf,home,away,hgoal,agoal,assist_prob,season='2024-25')
        sides=rg[['fixture_uuid','team_id','opponent_team_id','was_home']].drop_duplicates(['fixture_uuid','team_id'])
        try:
            ks=keeper_saves_at_deadline(sot,sides,cutoff,models['keeper'],season='2024-25')
            rg=rg.merge(ks[['fixture_uuid','team_id','lambda_saves']],on=['fixture_uuid','team_id'],how='left',validate='many_to_one')
        except ValueError:
            rg['lambda_saves']=0.
        vals=[ps.get(str(pid),(0.,.78)) for pid in rg.player_uuid]
        rg['pen_attempt_state']=[v[0] for v in vals];rg['pen_conversion']=[v[1] for v in vals]
        rg['pen_weight_raw']=rg.pen_attempt_state+.02*np.maximum(rg.goal_rate90,1e-6)
        den=rg.groupby('team_id').pen_weight_raw.transform('sum');rg['pen_weight']=np.where(den>0,rg.pen_weight_raw/den,0)
        rg['team_pen_conversion']=(rg.pen_weight*rg.pen_conversion).groupby(rg.team_id).transform('sum')
        rg['lambda_pen']=[plam(int(t),int(o)) for t,o in zip(rg.team_id,rg.opponent_team_id)]
        rg['bg_mean_rate90']=rg.player_uuid.map(bmean).fillna(0.);rg['bg_sd90']=rg.player_uuid.map(bsd).fillna(float(models['bpsvar']['global_sd90']))
        rg['control_p_start']=rg.new_p_start;rg['control_xmins']=rg.new_xmins
        rg['p_cameo_given_bench']=rg.new_q_sub;rg['start_minutes_mean']=rg.new_start_minutes;rg['cameo_minutes_mean']=rg.new_sub_minutes
        rg['v4_workload_start_p_start']=rg.new_p_start;rg['v4_workload_start_xmins']=rg.new_xmins
        rg['v4_p_cameo_given_bench']=rg.new_q_sub;rg['v4_start_minutes_mean']=rg.new_start_minutes;rg['v4_cameo_minutes_mean']=rg.new_sub_minutes
        rg['cutoff']=cutoff
        inp,_=make_vfinal_input(rg);inp=replace(inp,bps_rules='2024-25')
        sim=simulate_many_samples(inp,n=int(a.draws),seed=82400000+origin*1000+counter);counter+=1
        target=int(fr.gameweek)
        for rr in rg.itertuples(index=False):
            fid=mp.get(str(rr.player_uuid))
            if fid is None:continue
            key=(target,int(fid));arr=np.asarray(sim[str(rr.player_uuid)],dtype=np.float32)
            sample_sums[key]=sample_sums.get(key,np.zeros_like(arr))+arr
            meta[key]=dict(gw=target,candidate_id=int(fid),candidate_name=str(rr.player),player_uuid=str(rr.player_uuid),team=int(rr.team_id),position='GKP' if rr.pos in ('G','GK','GKP') else str(rr.pos))

    means=[]
    for key,arr in sample_sums.items():
        r=meta[key].copy();r['mean_points']=float(arr.mean());means.append(r)
    md=pd.DataFrame(means)
    chosen=pd.concat([g.sort_values('mean_points',ascending=False).head(int(a.top_k)) for _,g in md.groupby('gw',sort=True)],ignore_index=True)
    keep={(int(r.gw),int(r.candidate_id)) for r in chosen.itertuples(index=False)}
    rows=[]
    for key,arr in sample_sums.items():
        if key not in keep:continue
        m=meta[key]
        for s,p in enumerate(arr):
            rows.append(dict(simulation=int(s),gw=int(m['gw']),candidate_id=int(m['candidate_id']),candidate_name=str(m['candidate_name']),player_uuid=str(m['player_uuid']),team=int(m['team']),position=str(m['position']),points=float(p)))
    z=pd.DataFrame(rows);z.to_csv(out/'tc_samples.csv.gz',index=False,compression='gzip')
    chosen.to_csv(out/'tc_candidates.csv',index=False)
    summary=dict(season='2024-25',classification='CONDITIONAL TC long-horizon samples',origin_gw=origin,period_end_gw=int(a.period_end),draws=int(a.draws),top_k=int(a.top_k),schedule='FINAL_SEASON_SCHEDULE_PROXY',cutoff_strict=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
