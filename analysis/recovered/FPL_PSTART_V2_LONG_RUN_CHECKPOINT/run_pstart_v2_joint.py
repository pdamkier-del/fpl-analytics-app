from pathlib import Path
import json,sqlite3,time,hashlib
import pandas as pd
import numpy as np
from fpl_v1_1_model.minutes import project_minutes
from fpl_v1_1_model.phase4b import FrozenPlayerForecast, build_match_input
from fpl_v1_1_model.joint_simulator import simulate_many

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/v1_1/pstart_v2_joint_validation'; OUT.mkdir(parents=True,exist_ok=True)
#; OUT.mkdir(parents=True,exist_ok=True)
DB=ROOT/'data_v1_1/normalized/fpl_v1_1.sqlite3'
N=80; SEED=26092501

def load_csv(name): return pd.read_csv(ROOT/name)
mins=load_csv('outputs/v1_1/pstart_v2_core/pstart_v2_fixture_holdout_2025_26.csv').rename(columns={'p_start_v2':'regularized_p_start','expected_minutes_v2':'regularized_expected_minutes'})
goal=load_csv('outputs/v1_1/phase3c_player_attack/goal_holdout_predictions.csv').rename(columns={'mu':'goal_mu'})
ast=load_csv('outputs/v1_1/phase3c_player_attack/assist_holdout_predictions.csv').rename(columns={'mu':'assist_mu'})
neg=load_csv('outputs/v1_1/phase3e_negative_events/negative_events_holdout_predictions.csv')
dc=load_csv('outputs/v1_1/phase3d_defcon/defcon_validation_predictions.csv')
keep=load_csv('outputs/v1_1/phase3g_keeper/keeper_holdout_predictions_2025_26.csv')
latent=load_csv('outputs/v1_1/phase5e_team_goal_candidates/latent_selected_predictions.csv'); latent=latent[latent.season=='2025-26']; lmap={(r.fixture_uuid,int(r.team_id)):float(r.lam) for r in latent.itertuples()}
# Phase 4B structural replay is GW22-38: this is the only interval where every selected component has frozen forecasts.
mins=mins[mins.gw>=22].copy(); goal=goal[goal.gw>=22]; ast=ast[ast.gw>=22]; neg=neg[neg.gw>=22]
base=goal.merge(ast[['fixture_uuid','player_uuid','assist_mu']],on=['fixture_uuid','player_uuid'],how='inner')
base=base.merge(mins[['fixture_uuid','player_uuid','regularized_p_start','regularized_expected_minutes']],on=['fixture_uuid','player_uuid'],how='inner')
base=base.merge(neg[['fixture_uuid','player_uuid','position','p_yellow','p_red']],on=['fixture_uuid','player_uuid'],how='left')
base=base.merge(dc[['fixture_uuid','player_uuid','mu_dc']],on=['fixture_uuid','player_uuid'],how='left')
base['mu_dc']=base.mu_dc.fillna(0.0); base['p_yellow']=base.p_yellow.fillna(0.0); base['p_red']=base.p_red.fillna(0.0)

con=sqlite3.connect(DB)
fix=pd.read_sql_query("select fixture_uuid,home_team_id,away_team_id from fixtures where season='2025-26'",con)
players=pd.read_sql_query("select player_uuid,canonical_name from players",con)
obs=pd.read_sql_query("select player_uuid,fixture_uuid,gw,team_id,fpl_position,started,minutes,total_points,kickoff_at from player_fixture_observations where season='2025-26'",con)
# exact duplicate logical rows are possible in raw-normalized history; keep one logical observation.
obs=obs.sort_values(['player_uuid','gw','fixture_uuid']).drop_duplicates(['player_uuid','fixture_uuid'],keep='first')
base=base.merge(obs[['player_uuid','fixture_uuid','team_id','fpl_position','total_points']],on=['player_uuid','fixture_uuid'],how='left',suffixes=('','_obs'))
base=base.merge(players,on='player_uuid',how='left')

# Frozen Phase 3A settings; no refit.
role_h=1.3150986300759975; dur_h=0.32192611540889443; li=0.03186876473704488; ls=0.6645162300313383
hist_by={}
for pid,g in obs.sort_values('gw').groupby('player_uuid'):
    hist_by[pid]=g[['gw','started','minutes']].to_dict('records')

def duration_params(pid,gw):
    h=[r for r in hist_by.get(pid,[]) if int(r['gw'])<int(gw)]
    p=project_minutes(h,role_half_life=role_h,duration_half_life=dur_h,start_logit_intercept=li,start_logit_slope=ls)
    return p.expected_minutes_given_start,p.expected_minutes_given_cameo,p.p_cameo_given_bench

# Team lambda_goal in keeper file is the opponent scoring mean. lambda_saves belongs to defending team.
kmap={(r.fixture_uuid,int(r.team_id)):r for r in keep.itertuples()}
alpha={'DEF':1.6136326854524488,'MID':0.9017026562284318,'FWD':0.7194052759354805,'GKP':0.0,'GK':0.0}
# Development-only structural assist probability; not optimized against 2025/26.
a=con.execute("select sum(fpl_assists),sum(goals) from player_fixture_observations where season in ('2023-24','2024-25')").fetchone()
assist_prob=float(a[0]/a[1])
rows=[]; t0=time.time(); fixtures_done=0
for fr in fix.itertuples():
    g=base[base.fixture_uuid==fr.fixture_uuid]
    if g.empty: continue
    kh=kmap.get((fr.fixture_uuid,int(fr.home_team_id))); ka=kmap.get((fr.fixture_uuid,int(fr.away_team_id)))
    if kh is None or ka is None: continue
    # home scoring mean = away defending row's goal mean; vice versa.
    lam_h=lmap.get((fr.fixture_uuid,int(fr.home_team_id)),float(ka.lambda_goal)); lam_a=lmap.get((fr.fixture_uuid,int(fr.away_team_id)),float(kh.lambda_goal))
    plist=[]
    for r in g.itertuples():
        xmins=float(r.regularized_expected_minutes)
        if xmins < .05: continue
        sm,cm,pc=duration_params(r.player_uuid,r.gw)
        ks=kmap.get((fr.fixture_uuid,int(r.team_id)))
        lsave=float(ks.lambda_saves) if (str(r.fpl_position) in ('GKP','GK') and ks is not None) else 0.0
        plist.append(FrozenPlayerForecast(str(r.player_uuid),int(r.team_id),str(r.fpl_position),float(r.regularized_p_start),xmins,sm,cm,pc,
            float(r.goal_mu),float(r.assist_mu),float(r.mu_dc),alpha.get(str(r.fpl_position),0.0),float(r.p_yellow),float(r.p_red),lsave,0.0,0.0))
    if not plist: continue
    inp=build_match_input(home_team_id=int(fr.home_team_id),away_team_id=int(fr.away_team_id),lambda_home_goals=lam_h,lambda_away_goals=lam_a,players=plist,assist_probability_per_goal=assist_prob)
    sim=simulate_many(inp,n=N,seed=SEED+fixtures_done)
    actual_map={str(r.player_uuid):(r.total_points,r.canonical_name,r.gw,r.fpl_position,r.team_id) for r in g.itertuples()}
    for pid,z in sim.items():
        actual,name,gw,pos,team=actual_map.get(pid,(np.nan,None,None,None,None))
        rows.append({'season':'2025-26','gw':gw,'fixture_uuid':fr.fixture_uuid,'player_uuid':pid,'player_name':name,'team_id':team,'position':pos,
                     'xPts_v1_1_candidate':z['xPts'],'xPts_nonbonus':z['xPts_nonbonus'],'expected_bonus_mc':z['expected_bonus'],'median':z['median'],'p10':z['p10'],'p90':z['p90'],'expected_minutes_mc':z['expected_minutes'],
                     'p_start_mc':z['p_start'],'p_attacking_return':z['p_attacking_return'],'p_10_plus':z['p_10_plus'],'p_clean_sheet_award':z['p_clean_sheet_award'],
                     'appearance_points_mc':z['appearance_points'],'goal_points_mc':z['goal_points'],'assist_points_mc':z['assist_points'],'cs_points_mc':z['cs_points'],'save_points_mc':z['save_points'],'dc_points_mc':z['dc_points'],'negative_points_mc':z['negative_points'],'gc_points_mc':z['gc_points'],
                     'actual_points_reference_only':actual})
    fixtures_done+=1

out=pd.DataFrame(rows).sort_values(['gw','fixture_uuid','xPts_v1_1_candidate'],ascending=[True,True,False])
out.to_csv(OUT/'joint_xpts_pstart_v2_80sim_2025_26_gw22_38.csv',index=False)
manifest={
 'phase':'PSTART_V2_EXACT_XPTS','status':'validation_candidate_not_selected','season':'2025-26','gw_range':[22,38],'n_simulations_per_fixture':N,'seed_base':SEED,
 'fixtures_simulated':fixtures_done,'player_fixture_rows':len(out),'assist_probability_per_goal':assist_prob,
 'bps_background_policy':'zero in historical structural replay because 2026/27 BPS rules differ; no previous-season BPS background imported',
 'own_goals_policy':'off until shared score mutation exists','penalties_policy':'folded into xG; explicit penalty module off to avoid double counting',
 'half_lives_retuned':False,'runtime_seconds':time.time()-t0,
 'purpose':'Exact joint-simulator sensitivity: Phase 5E latent team goals with only P(start)/xMins replaced by frozen P(start) v2-core.'
}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2)); print(out.head(15).to_string(index=False))
