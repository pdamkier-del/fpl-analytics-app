"""Phase 3G: keeper SOT/save model using the external Football-Data source.

Selection discipline:
- existing Phase 3B half-lives are fixed (13 attack / 20 defence); no h search;
- 2022/23+2023/24 train candidate structures;
- 2024/25 selects structure;
- selected structures refit on 2022/23-2024/25;
- 2025/26 is evaluation only.

The source is PARTIAL and its SOT definition is not forced to equal FPL saves +
goals.  Instead source SOT predicts FPL save opportunity, while the independent
Phase 3B team-goal model supplies goals for the final coherent simulation.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln
from scipy.stats import poisson

TRAIN = ("2022-23", "2023-24")
VALID = "2024-25"
HOLD = "2025-26"
MIN_HISTORY = 5
SEED = 26092026


def load(db: Path):
    con = sqlite3.connect(db)
    sot = pd.read_sql_query(
        """SELECT season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,
                  shots_on_target,shots_on_target_conceded
           FROM team_fixture_observations WHERE source_name='football_data_co_uk'
           ORDER BY season,kickoff_at,fixture_uuid,was_home DESC""", con
    )
    goals = pd.read_sql_query(
        """SELECT season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,gf,ga,xg,xga
           FROM team_fixture_observations WHERE source_name='vaastav_historical_core'
           ORDER BY season,kickoff_at,fixture_uuid,was_home DESC""", con
    )
    saves = pd.read_sql_query(
        """SELECT season,fixture_uuid,team_id,SUM(COALESCE(saves,0)) AS saves,
                  SUM(COALESCE(penalty_saves,0)) AS penalty_saves
           FROM player_fixture_observations WHERE fpl_position='GK'
           GROUP BY season,fixture_uuid,team_id""", con
    )
    con.close()
    for x, col in ((sot,"kickoff_at"),(goals,"kickoff_at")):
        x[col] = pd.to_datetime(x[col], utc=True)
    return sot, goals, saves


def sequential_sot(rows: pd.DataFrame, seasons, h_att: float, h_def: float) -> pd.DataFrame:
    out=[]; da=2**(-1/h_att); dd=2**(-1/h_def)
    for season in seasons:
        d=rows[rows.season==season].sort_values(["kickoff_at","fixture_uuid","was_home"],ascending=[True,True,False])
        att={}; deff={}; games={}; league_sum=0.; league_n=0
        for (_,fid),cur in d.groupby(["kickoff_at","fixture_uuid"],sort=True):
            for r in cur.itertuples(index=False):
                t=int(r.team_id); o=int(r.opponent_team_id)
                if games.get(t,0)>=MIN_HISTORY and games.get(o,0)>=MIN_HISTORY and t in att and o in deff and league_n:
                    aw,asot=att[t]; dw,dsot=deff[o]
                    out.append({"season":season,"fixture_uuid":r.fixture_uuid,"team_id":t,"opp":o,
                                "home":int(r.was_home),"actual_sot":float(r.shots_on_target),
                                "attack_sot":asot/aw,"opp_allow_sot":dsot/dw,"league_sot":league_sum/league_n})
            for r in cur.itertuples(index=False):
                t=int(r.team_id); a=att.get(t,[0.,0.]); b=deff.get(t,[0.,0.])
                a=[x*da for x in a]; b=[x*dd for x in b]
                a[0]+=1; a[1]+=float(r.shots_on_target)
                b[0]+=1; b[1]+=float(r.shots_on_target_conceded)
                att[t]=a; deff[t]=b; games[t]=games.get(t,0)+1
                league_sum+=float(r.shots_on_target); league_n+=1
    return pd.DataFrame(out)


def sot_predict(kind: str, z, d: pd.DataFrame):
    A=d.attack_sot.to_numpy(float); D=d.opp_allow_sot.to_numpy(float); L=d.league_sot.to_numpy(float); H=d.home.to_numpy(float)
    if kind=="league": return np.exp(z[0]+z[1]*H)*L
    if kind=="attack": return np.exp(z[0]+z[1]*H)*A
    if kind=="defence": return np.exp(z[0]+z[1]*H)*D
    if kind=="arithmetic":
        w=1/(1+np.exp(-z[2])); return np.exp(z[0]+z[1]*H)*(w*A+(1-w)*D)
    if kind=="multiplicative": return np.exp(z[0]+z[1]*H)*A*D/np.maximum(.1,L)
    if kind=="loglinear":
        return L*np.exp(z[0]+z[1]*H+z[2]*np.log(np.maximum(A,.05)/L)+z[3]*np.log(np.maximum(D,.05)/L))
    raise KeyError(kind)


def fit_sot(kind: str, d: pd.DataFrame):
    x0={"league":[0,.15],"attack":[0,.15],"defence":[0,.15],"arithmetic":[0,.15,0],
        "multiplicative":[0,.15],"loglinear":[0,.15,.7,.7]}[kind]
    y=d.actual_sot.to_numpy(float)
    def obj(z):
        lam=np.clip(sot_predict(kind,z,d),.05,15); return float(np.mean(lam-y*np.log(lam)))
    return minimize(obj,x0,method="Nelder-Mead",options={"maxiter":5000,"xatol":1e-10,"fatol":1e-12})


def metrics(y, lam):
    y=np.asarray(y,float); lam=np.clip(np.asarray(lam,float),1e-9,None); e=lam-y
    return {"n":int(len(y)),"poisson_nll_no_constant":float(np.mean(lam-y*np.log(lam))),
            "mae":float(np.mean(np.abs(e))),"rmse":float(np.sqrt(np.mean(e*e))),
            "bias":float(np.mean(e)),"mean_prediction":float(np.mean(lam)),"mean_actual":float(np.mean(y))}


def sequential_goal_lambda(rows: pd.DataFrame, seasons, fit: dict) -> pd.DataFrame:
    ha=float(fit["attack_half_life"]); hd=float(fit["defence_half_life"]); da=2**(-1/ha); dd=2**(-1/hd)
    alpha=float(fit["xg_weight_alpha"]); beta=float(fit["xga_weight_beta"]); intercept=float(fit["intercept"]); home=float(fit["home_log_effect"])
    out=[]
    for season in seasons:
        d=rows[rows.season==season].sort_values(["kickoff_at","fixture_uuid","was_home"],ascending=[True,True,False])
        att={};deff={};games={};lg=0.;ln=0
        for (_,fid),cur in d.groupby(["kickoff_at","fixture_uuid"],sort=True):
            for r in cur.itertuples(index=False):
                t=int(r.team_id);o=int(r.opponent_team_id)
                if games.get(t,0)>=MIN_HISTORY and games.get(o,0)>=MIN_HISTORY and t in att and o in deff and ln:
                    aw,gf,xg=att[t];dw,ga,xga=deff[o]
                    attack=alpha*xg/aw+(1-alpha)*gf/aw; weak=beta*xga/dw+(1-beta)*ga/dw
                    lam=np.exp(intercept+home*int(r.was_home))*max(.05,attack)*max(.05,weak)/max(.3,lg/ln)
                    out.append({"season":season,"fixture_uuid":r.fixture_uuid,"team_id":t,"lambda_goal":float(np.clip(lam,.05,5.0))})
            for r in cur.itertuples(index=False):
                t=int(r.team_id);a=att.get(t,[0.,0.,0.]);b=deff.get(t,[0.,0.,0.]);a=[x*da for x in a];b=[x*dd for x in b]
                a[0]+=1;a[1]+=float(r.gf);a[2]+=float(r.xg);b[0]+=1;b[1]+=float(r.ga);b[2]+=float(r.xga)
                att[t]=a;deff[t]=b;games[t]=games.get(t,0)+1;lg+=float(r.gf);ln+=1
    return pd.DataFrame(out)


def attach_saves(d: pd.DataFrame, saves: pd.DataFrame, goals: pd.DataFrame) -> pd.DataFrame:
    x=d.merge(goals,on=["season","fixture_uuid","team_id"],how="inner")
    target=saves.rename(columns={"team_id":"opp","saves":"actual_saves","penalty_saves":"actual_penalty_saves"})
    return x.merge(target,on=["season","fixture_uuid","opp"],how="inner")


def save_predict(kind: str, z, d: pd.DataFrame):
    S=np.maximum(d.lambda_source_sot.to_numpy(float),.01); G=np.maximum(d.lambda_goal.to_numpy(float),.01); H=d.home.to_numpy(float)
    base=np.maximum(.01,S-G)
    if kind=="raw_sot_minus_goals": return base
    if kind=="base_power": return np.exp(z[0])*base**z[1]
    if kind=="base_power_home": return np.exp(z[0]+z[2]*H)*base**z[1]
    if kind=="sot_only": return np.exp(z[0]+z[2]*H)*S**z[1]
    if kind=="sot_plus_goal": return np.exp(z[0]+z[3]*H)*S**z[1]*np.exp(z[2]*G)
    raise KeyError(kind)


def fit_save(kind: str, d: pd.DataFrame):
    if kind=="raw_sot_minus_goals": return np.array([])
    x0={"base_power":[0,1],"base_power_home":[0,1,0],"sot_only":[-.6,1,0],"sot_plus_goal":[-.6,1,0,0]}[kind]
    y=d.actual_saves.to_numpy(float)
    def obj(z):
        lam=np.clip(save_predict(kind,z,d),.01,12);return float(np.mean(lam-y*np.log(lam)))
    return minimize(obj,x0,method="Nelder-Mead",options={"maxiter":5000,"xatol":1e-10,"fatol":1e-12}).x


def expected_save_points(lams):
    out=[]
    for lam in np.asarray(lams,float):
        p=math.exp(-lam);cum=p;total=0.;n=0
        while n<300 and 1-cum>1e-12:
            n+=1;p*=lam/n;cum+=p;total+=(n//3)*p
        out.append(total)
    return np.asarray(out)


def full_poisson_nll(y,mu):
    y=np.asarray(y,float);mu=np.maximum(np.asarray(mu,float),1e-12)
    return float(np.mean(mu-y*np.log(mu)+gammaln(y+1)))


def nb2_nll(alpha,y,mu):
    y=np.asarray(y,float);mu=np.maximum(np.asarray(mu,float),1e-12)
    if alpha<=1e-9:return full_poisson_nll(y,mu)
    r=1/alpha;p=r/(r+mu)
    ll=gammaln(y+r)-gammaln(r)-gammaln(y+1)+r*np.log(p)+y*np.log1p(-p)
    return float(-np.mean(ll))


def bootstrap_mae_delta(df, pred_col, base_col, reps=5000):
    x=df.copy(); y=x.actual_saves.to_numpy(float)
    x["_delta_abs"] = np.abs(x[pred_col].to_numpy(float)-y)-np.abs(x[base_col].to_numpy(float)-y)
    per_fixture=x.groupby("fixture_uuid")["_delta_abs"].mean().to_numpy(float)
    rng=np.random.default_rng(SEED); n=len(per_fixture)
    draws=rng.integers(0,n,size=(reps,n)); vals=per_fixture[draws].mean(axis=1)
    return {"mean_delta":float(np.mean(vals)),"ci95":[float(np.quantile(vals,.025)),float(np.quantile(vals,.975))]}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--db",type=Path,default=Path("data_v1_1/normalized/fpl_v1_1.sqlite3"));ap.add_argument("--team-goal-fit",type=Path,default=Path("outputs/v1_1/phase3b_team_goals/team_goal_fit.json"));ap.add_argument("--out",type=Path,default=Path("outputs/v1_1/phase3g_keeper"));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sot,goalrows,saves=load(a.db);goalfit=json.loads(a.team_goal_fit.read_text())["fit"]
    h_att=float(goalfit["attack_half_life"]);h_def=float(goalfit["defence_half_life"])

    tr=sequential_sot(sot,TRAIN,h_att,h_def);va=sequential_sot(sot,(VALID,),h_att,h_def)
    candidates=[]
    for kind in ["league","attack","defence","arithmetic","multiplicative","loglinear"]:
        fit=fit_sot(kind,tr);m=metrics(va.actual_sot,sot_predict(kind,fit.x,va));candidates.append({"model":kind,"n_params":len(fit.x),"params":fit.x.tolist(),"validation":m})
    # loglinear has the best validation NLL, but arithmetic is within 0.005 NLL,
    # uses one fewer parameter and has slightly lower validation MAE. Freeze the
    # simpler near-best structure before touching 2025/26.
    selected_sot="arithmetic"
    dev=sequential_sot(sot,TRAIN+(VALID,),h_att,h_def);hold=sequential_sot(sot,(HOLD,),h_att,h_def)
    sf=fit_sot(selected_sot,dev);dev["lambda_source_sot"]=np.clip(sot_predict(selected_sot,sf.x,dev),.05,15);hold["lambda_source_sot"]=np.clip(sot_predict(selected_sot,sf.x,hold),.05,15)

    # Save-mapping selection on train/validation, using SOT model fit on train only.
    st=fit_sot(selected_sot,tr);tr["lambda_source_sot"]=np.clip(sot_predict(selected_sot,st.x,tr),.05,15);va["lambda_source_sot"]=np.clip(sot_predict(selected_sot,st.x,va),.05,15)
    gtr=sequential_goal_lambda(goalrows,TRAIN,goalfit);gva=sequential_goal_lambda(goalrows,(VALID,),goalfit)
    trj=attach_saves(tr,saves,gtr);vaj=attach_saves(va,saves,gva)
    save_candidates=[]
    for kind in ["raw_sot_minus_goals","base_power","base_power_home","sot_only","sot_plus_goal"]:
        z=fit_save(kind,trj);m=metrics(vaj.actual_saves,save_predict(kind,z,vaj));save_candidates.append({"model":kind,"n_params":len(z),"params":z.tolist(),"validation":m})
    selected_save="sot_only"

    # Refit selected save mapping on full development and evaluate 2025/26.
    gdev=sequential_goal_lambda(goalrows,TRAIN+(VALID,),goalfit);ghold=sequential_goal_lambda(goalrows,(HOLD,),goalfit)
    devj=attach_saves(dev,saves,gdev);holdj=attach_saves(hold,saves,ghold)
    sz=fit_save(selected_save,devj);devj["lambda_saves"]=np.clip(save_predict(selected_save,sz,devj),.01,12);holdj["lambda_saves"]=np.clip(save_predict(selected_save,sz,holdj),.01,12)
    holdj["lambda_sot_modelled_fpl"]=holdj.lambda_goal+holdj.lambda_saves

    # Cutoff-safe league-save baseline for scale/context (cumulative prior team-side saves).
    for frame in (devj,holdj):
        frame.sort_values(["season","fixture_uuid","team_id"],inplace=True)
        # fixture UUID order is not chronological, so derive baseline by season from the
        # pre-match league mean available through the source-SOT sequential state. A
        # conservative constant uses the development league mean for holdout.
    dev_save_mean=float(devj.actual_saves.mean())
    holdj["league_save_baseline"]=dev_save_mean
    holdj["raw_sot_minus_goals"]=np.maximum(.01,holdj.lambda_source_sot-holdj.lambda_goal)

    # Distribution check: NB2 dispersion fitted only on development.
    alpha_fit=minimize_scalar(lambda la:nb2_nll(math.exp(la),devj.actual_saves,devj.lambda_saves),bounds=(-8,2),method="bounded")
    alpha=float(math.exp(alpha_fit.x))
    distribution={"selected":"poisson","nb2_alpha_fit_on_development":alpha,
                  "development_poisson_nll":full_poisson_nll(devj.actual_saves,devj.lambda_saves),
                  "development_nb2_nll":nb2_nll(alpha,devj.actual_saves,devj.lambda_saves),
                  "holdout_poisson_nll":full_poisson_nll(holdj.actual_saves,holdj.lambda_saves),
                  "holdout_nb2_nll":nb2_nll(alpha,holdj.actual_saves,holdj.lambda_saves)}

    holdj["expected_save_points"]=expected_save_points(holdj.lambda_saves)
    holdj["actual_save_points"]=(holdj.actual_saves.astype(int)//3).astype(int)
    sp_err=holdj.expected_save_points-holdj.actual_save_points
    save_point_metrics={"n":int(len(holdj)),"mae":float(np.mean(abs(sp_err))),"rmse":float(np.sqrt(np.mean(sp_err*sp_err))),
                        "bias":float(np.mean(sp_err)),"mean_prediction":float(holdj.expected_save_points.mean()),"mean_actual":float(holdj.actual_save_points.mean())}
    bucket={}
    for k in (1,2,3):
        p=1-poisson.cdf(3*k-1,holdj.lambda_saves);y=(holdj.actual_saves>=3*k).astype(float)
        bucket[str(k)]={"brier":float(np.mean((p-y)**2)),"mean_prediction":float(np.mean(p)),"event_rate":float(np.mean(y))}

    # External source reconciliation diagnostic copied from actual DB-linked rows.
    # Compare source SOT to FPL saves + actual goals only as a diagnostic, never a repair rule.
    rec=holdj.copy();rec["identity_delta"]=rec.actual_sot-(rec.actual_saves) # goals/OG not available in this joined table; Work report remains canonical for exact identity.

    result={
      "selection_protocol":{"train_seasons":list(TRAIN),"validation_season":VALID,"evaluation_season":HOLD,
        "holdout_caveat":"2025/26 was inspected during Phase 3G exploratory development before the final scripted freeze, so it is evaluation-only but not a never-seen blind holdout.",
        "half_lives_fixed_not_tuned":{"attack":h_att,"defence":h_def},"min_history_matches":MIN_HISTORY},
      "source":{"name":"football_data_co_uk","classification":"PARTIAL","rows":int(len(sot)),
        "definition_policy":"Use source SOT as predictor; never force source SOT = FPL saves + goals."},
      "sot_structure_candidates":candidates,
      "selected_sot":{"model":selected_sot,"intercept":float(sf.x[0]),"attacker_home_log_effect":float(sf.x[1]),
        "opponent_sot_for_weight":float(1/(1+math.exp(-sf.x[2]))),"team_sot_allowed_weight":float(1-1/(1+math.exp(-sf.x[2]))),
        "development":metrics(dev.actual_sot,dev.lambda_source_sot),"evaluation":metrics(hold.actual_sot,hold.lambda_source_sot)},
      "save_mapping_candidates":save_candidates,
      "selected_save":{"model":selected_save,"intercept":float(sz[0]),"sot_exponent":float(sz[1]),"attacker_home_log_effect":float(sz[2]),
        "development":metrics(devj.actual_saves,devj.lambda_saves),"evaluation":metrics(holdj.actual_saves,holdj.lambda_saves)},
      "save_ablations":{"raw_source_sot_minus_team_goal_lambda":metrics(holdj.actual_saves,holdj.raw_sot_minus_goals),
        "development_mean_saves_baseline":metrics(holdj.actual_saves,holdj.league_save_baseline),
        "mae_delta_selected_minus_development_mean_baseline_bootstrap":bootstrap_mae_delta(holdj,"lambda_saves","league_save_baseline")},
      "save_distribution":distribution,"save_points_evaluation":save_point_metrics,"save_point_bucket_calibration":bucket,
      "simulation_contract":{"goals":"Phase 3B team-goal Poisson mean","saves":"Phase 3G Poisson save mean",
        "modelled_sot":"goals + saves in every draw","penalty_saves":"shared penalty event from Phase 3F, not independent"}
    }
    (a.out/"keeper_fit.json").write_text(json.dumps(result,indent=2)+"\n")
    cols=["season","fixture_uuid","team_id","opp","home","actual_sot","lambda_source_sot","lambda_goal","actual_saves","lambda_saves","lambda_sot_modelled_fpl","expected_save_points","actual_save_points"]
    holdj[cols].to_csv(a.out/"keeper_holdout_predictions_2025_26.csv",index=False)
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
