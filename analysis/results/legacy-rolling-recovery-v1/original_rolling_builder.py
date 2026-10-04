#!/usr/bin/env python3
"""Build rolling, deadline-frozen Phase 5Q-style forecasts for 2025/26.

The Phase 5Q component parameters are kept fixed.  For every FPL deadline the
current-season state is rebuilt from matches whose kick-off precedes that
deadline, then frozen while the next six GWs are projected.  GW1-5 use a
documented previous-season cold start; GW6 onward use the selected
current-season-only Phase 5Q state.

Historical 2025/26 fixture snapshots are unavailable, so the archived final
fixture-to-GW assignment is used.  This limitation is recorded in the output
manifest and must not be described as a perfect schedule-as-of replay.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from fpl_v1_1_model.joint_simulator import simulate_many
from fpl_v1_1_model.minutes import project_minutes
from fpl_v1_1_model.negative_events import competing_card_probabilities
from fpl_v1_1_model.phase4b import FrozenPlayerForecast, build_match_input
from fpl_v1_1_model.keeper import (
    SOTRateParams, SaveRateParams, forecast_fpl_save_mean, forecast_source_sot_mean,
)

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data_v1_1/normalized/fpl_v1_1.sqlite3"
OUT = ROOT / "outputs/v1_1/phase5t_rolling_reference"
SEASON = "2025-26"
PRIOR = "2024-25"
N_SIM = 400
SEED = 26092601


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


MIN_FIT = _json("outputs/v1_1/phase3a_minutes/continuous_half_life_fit.json")
PSTART = _json("outputs/v1_1/phase3a_minutes/pstart_regularization.json")["selected"]
ATTACK = _json("outputs/v1_1/phase3c_player_attack/player_attack_fit.json")
NEG = _json("outputs/v1_1/phase3e_negative_events/negative_events_fit.json")["recommended_for_joint_model"]
DC = _json("outputs/v1_1/phase3d_defcon/defcon_fit.json")["selected"]
KEEPER = _json("outputs/v1_1/phase3g_keeper/keeper_fit.json")


def deadline_by_gw(team_rows: pd.DataFrame) -> dict[int, pd.Timestamp]:
    # Historical FPL deadlines are normally 90 minutes before the first match.
    first = pd.to_datetime(team_rows.groupby("gw")["kickoff_at"].min(), utc=True)
    return {int(gw): ts - pd.Timedelta(minutes=90) for gw, ts in first.items()}


def load_data():
    with sqlite3.connect(DB) as con:
        pf = pd.read_sql_query(
            """SELECT season,gw,fixture_uuid,player_uuid,team_id,opponent_team_id,
                      was_home,kickoff_at,fpl_position,started,minutes,xg,xa,goals,
                      fpl_assists,yellow_cards,fpl_red_cards,own_goals,defcon_count
                 FROM player_fixture_observations
                WHERE season IN (?,?)""", con, params=(PRIOR, SEASON),
        )
        tf = pd.read_sql_query(
            """SELECT season,gw,fixture_uuid,team_id,opponent_team_id,was_home,
                      kickoff_at,gf,ga,xg,xga
                 FROM team_fixture_observations
                WHERE source_name='vaastav_historical_core' AND season IN (?,?)""",
            con, params=(PRIOR, SEASON),
        )
        sot = pd.read_sql_query(
            """SELECT e.season,v.gw,e.fixture_uuid,e.team_id,e.opponent_team_id,
                      e.was_home,v.kickoff_at,e.shots_on_target,e.shots_on_target_conceded
                 FROM team_fixture_observations e
                 JOIN team_fixture_observations v
                   ON v.fixture_uuid=e.fixture_uuid AND v.team_id=e.team_id
                  AND v.source_name='vaastav_historical_core'
                WHERE e.source_name='football_data_co_uk' AND e.season IN (?,?)""",
            con, params=(PRIOR, SEASON),
        )
        mapping = pd.read_sql_query(
            """SELECT player_uuid,CAST(external_id AS INTEGER) id
                 FROM player_id_mapping
                WHERE season=? AND id_namespace='fpl_element'""", con, params=(SEASON,),
        ).drop_duplicates("id")
        names = pd.read_sql_query("SELECT player_uuid,canonical_name FROM players", con)
    for d in (pf, tf, sot):
        d["kickoff_at"] = pd.to_datetime(d["kickoff_at"], utc=True)
    pf = pf.drop_duplicates(["season", "fixture_uuid", "player_uuid"])
    tf = tf.drop_duplicates(["season", "fixture_uuid", "team_id"])
    sot = sot.drop_duplicates(["season", "fixture_uuid", "team_id"])
    return pf, tf, sot, mapping, names


def current_meta_by_origin(mapping: pd.DataFrame, names: pd.DataFrame) -> dict[int, pd.DataFrame]:
    gws = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/gws/merged_gw.csv", low_memory=False)
    gws["position"] = gws.position.replace({"GK": "GKP"})
    label = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/players_raw.csv", low_memory=False)
    web = label.set_index("id").web_name.astype(str).to_dict()
    teams = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/teams.csv", low_memory=False)
    team_id = teams.set_index("name").id.astype(int).to_dict()
    uuid_by_id = mapping.set_index("id").player_uuid.to_dict()
    known = pd.DataFrame(columns=["id", "player_uuid", "web_name", "team", "position", "price_tenths"])
    out = {}
    for gw in range(1, 39):
        x = gws[gws.GW == gw].sort_values("kickoff_time").drop_duplicates("element").copy()
        x = x.rename(columns={"element": "id", "value": "price_tenths"})
        x["id"] = x.id.astype(int)
        x["player_uuid"] = x.id.map(uuid_by_id)
        x["web_name"] = x.id.map(web).fillna(x.name)
        x["team"] = x.team.map(team_id).fillna(x.team)
        x["team"] = pd.to_numeric(x.team, errors="coerce")
        x = x[["id", "player_uuid", "web_name", "team", "position", "price_tenths"]]
        x = x[x.player_uuid.notna() & x.team.notna()].copy()
        x["team"] = x.team.astype(int)
        # A normal GW file contains the active FPL elements for every club that
        # plays in that GW.  Remove previously known elements missing from a
        # playing club (departed/removed), while retaining a blank-GW club's
        # roster until its next observed snapshot.
        playing_teams = set(x.team.astype(int))
        keep_old = ~known.team.isin(playing_teams) | known.id.isin(x.id)
        known = pd.concat([known[keep_old & ~known.id.isin(x.id)], x], ignore_index=True)
        known = known.drop_duplicates("id", keep="last")
        out[gw] = known.copy()
    return out


def _weighted_player_rate(rows: pd.DataFrame, stat: str, half_life: float) -> tuple[float, float]:
    if rows.empty:
        return 0.0, 0.0
    r = rows.sort_values("kickoff_at", ascending=False)
    w = 2.0 ** (-np.arange(len(r), dtype=float) / half_life)
    return float(np.sum(w * r[stat].fillna(0).to_numpy(float))), float(np.sum(w * r.minutes.fillna(0).to_numpy(float)))


def player_state(meta: pd.DataFrame, pf: pd.DataFrame, deadline: pd.Timestamp, origin: int) -> pd.DataFrame:
    cur = pf[(pf.season == SEASON) & (pf.kickoff_at < deadline)].copy()
    prior = pf[pf.season == PRIOR].copy()
    # Previous-season rows are an explicit cold-start layer only.
    hist = pd.concat([prior, cur], ignore_index=True) if origin <= 5 else cur
    pos_source = hist
    pos_rates = {}
    for pos, g in pos_source.groupby("fpl_position"):
        mins = max(float(g.minutes.sum()), 1.0)
        pos_rates[pos] = {
            "xg": 90.0 * float(g.xg.sum()) / mins,
            "xa": 90.0 * float(g.xa.sum()) / mins,
            "yellow": 90.0 * float(g.yellow_cards.sum()) / mins,
            "red": 90.0 * float(g.fpl_red_cards.sum()) / mins,
        }
    league_goals = float(hist.goals.sum())
    assist_prob = float(hist.fpl_assists.sum() / league_goals) if league_goals > 0 else 0.90
    rows = []
    for m in meta.itertuples():
        h = hist[hist.player_uuid == m.player_uuid].sort_values("kickoff_at")
        mh = h[["started", "minutes"]].to_dict("records")
        pr = project_minutes(
            mh, role_half_life=float(MIN_FIT["role_half_life"]),
            duration_half_life=float(MIN_FIT["duration_half_life"]),
            start_logit_intercept=float(PSTART["intercept"]),
            start_logit_slope=float(PSTART["slope"]),
        )
        pos = "GK" if str(m.position) == "GKP" else str(m.position)
        fallback = pos_rates.get(pos, {"xg": 0.0, "xa": 0.0, "yellow": 0.0, "red": 0.0})
        xg, mins_g = _weighted_player_rate(h, "xg", float(ATTACK["goal"]["recency_half_life"]))
        xa, mins_a = _weighted_player_rate(h, "xa", float(ATTACK["assist"]["recency_half_life"]))
        tg = float(ATTACK["goal"]["current_season_position_prior_minutes_tau"])
        ta = float(ATTACK["assist"]["current_season_position_prior_minutes_tau"])
        goal90 = 90.0 * (xg + tg * fallback["xg"] / 90.0) / max(mins_g + tg, 1.0)
        assist90 = 90.0 * (xa + ta * fallback["xa"] / 90.0) / max(mins_a + ta, 1.0)
        total_min = float(h.minutes.sum())
        yellow90 = 90.0 * (float(h.yellow_cards.sum()) + float(NEG["yellow_prior_minutes_tau"]) * fallback["yellow"] / 90.0) / max(total_min + float(NEG["yellow_prior_minutes_tau"]), 1.0)
        # The selected joint model uses the current position rate for reds.
        red90 = fallback["red"]
        disc = competing_card_probabilities(pr.expected_minutes, yellow90, red90)
        rows.append({
            **m._asdict(), "position_model": pos, "p_start": pr.p_start,
            "p_play": pr.p_play, "xmins": pr.expected_minutes,
            "start_minutes_mean": pr.expected_minutes_given_start,
            "cameo_minutes_mean": pr.expected_minutes_given_cameo,
            "p_cameo": pr.p_cameo_given_bench, "goal90": goal90,
            "assist90": assist90, "p_yellow": disc.yellow, "p_red": disc.red,
            "assist_ratio": min(1.0, max(0.5, assist_prob)),
        })
    return pd.DataFrame(rows)


def fit_latent_team_state(history: pd.DataFrame, teams: list[int], origin: int):
    """Phase 5Q h12/ridge .25 latent xG state, frozen at one deadline."""
    if history.empty:
        return None
    idx = {t: i for i, t in enumerate(sorted(teams))}; T = len(idx)
    h = history[history.team_id.isin(idx) & history.opponent_team_id.isin(idx)].copy()
    if h.empty:
        return None
    yy = h.xg.fillna(h.gf).to_numpy(float)
    home = h.was_home.to_numpy(int)
    ti = h.team_id.map(idx).to_numpy(int); oi = h.opponent_team_id.map(idx).to_numpy(int)
    ages = np.maximum(0, origin - h.gw.to_numpy(int)); w = 2.0 ** (-ages / 12.0)
    def unpack(z):
        aa = np.r_[z[2:2+T-1], -np.sum(z[2:2+T-1])]
        dd = np.r_[z[2+T-1:2+2*(T-1)], -np.sum(z[2+T-1:2+2*(T-1)])]
        return z[0], z[1], aa, dd
    def obj(z):
        mu, hh, aa, dd = unpack(z); eta = mu + hh * home + aa[ti] + dd[oi]
        lam = np.exp(np.clip(eta, -4, 3))
        return float(np.sum(w * (lam - yy * eta)) / np.sum(w) + .25 * (np.mean(aa*aa) + np.mean(dd*dd)))
    z = np.zeros(2 + 2 * (T - 1)); z[0] = math.log(max(.2, float(np.average(yy, weights=w))))
    opt = minimize(obj, z, method="L-BFGS-B", options={"maxiter": 120, "ftol": 1e-9})
    return idx, unpack(opt.x)


def prior_team_strength(tf: pd.DataFrame):
    p = tf[tf.season == PRIOR].groupby("team_id", as_index=False).agg(xgf=("xg", "mean"), xga=("xga", "mean"))
    old = pd.read_csv(ROOT / f"data/cache/history/{PRIOR}/teams.csv", low_memory=False)[["id", "name"]]
    new = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/teams.csv", low_memory=False)[["id", "name"]]
    p = p.merge(old.rename(columns={"id": "team_id"}), on="team_id", how="left")
    p = p.merge(new.rename(columns={"id": "current_team_id"}), on="name", how="inner")
    p["team_id"] = p.current_team_id.astype(int)
    league = float(p.xgf.mean())
    return p.set_index("team_id"), league


def team_lambdas(origin: int, fixtures: pd.DataFrame, history: pd.DataFrame, all_teams: list[int], prior):
    fitted = fit_latent_team_state(history, all_teams, origin) if origin >= 6 else None
    out = {}
    if fitted is not None:
        idx, (mu, hh, aa, dd) = fitted
        for r in fixtures.itertuples():
            if int(r.team_id) in idx and int(r.opponent_team_id) in idx:
                val = math.exp(mu + hh * int(r.was_home) + aa[idx[int(r.team_id)]] + dd[idx[int(r.opponent_team_id)]])
            else:
                val = math.exp(mu + hh * int(r.was_home))
            out[(r.fixture_uuid, int(r.team_id))] = float(np.clip(val, .05, 5.0))
        return out
    p, league = prior
    for r in fixtures.itertuples():
        a = float(p.xgf.mean()) if int(r.team_id) not in p.index else float(p.loc[int(r.team_id), "xgf"])
        d = float(p.xga.mean()) if int(r.opponent_team_id) not in p.index else float(p.loc[int(r.opponent_team_id), "xga"])
        val = league * (a / league) * (d / league) * (1.10 if int(r.was_home) else 1/1.10)
        out[(r.fixture_uuid, int(r.team_id))] = float(np.clip(val, .25, 3.8))
    return out


def sot_state(sot: pd.DataFrame, deadline: pd.Timestamp, origin: int):
    use = sot[(sot.season == SEASON) & (sot.kickoff_at < deadline)].copy()
    if origin <= 5:
        old = pd.read_csv(ROOT / f"data/cache/history/{PRIOR}/teams.csv", low_memory=False)[["id", "name"]]
        new = pd.read_csv(ROOT / f"data/cache/history/{SEASON}/teams.csv", low_memory=False)[["id", "name"]]
        remap = old.merge(new, on="name", suffixes=("_old", "_new")).set_index("id_old").id_new.to_dict()
        pre = sot[sot.season == PRIOR].copy()
        pre["team_id"] = pre.team_id.map(remap)
        pre["opponent_team_id"] = pre.opponent_team_id.map(remap)
        pre = pre[pre.team_id.notna() & pre.opponent_team_id.notna()].copy()
        pre[["team_id", "opponent_team_id"]] = pre[["team_id", "opponent_team_id"]].astype(int)
        use = pd.concat([pre, use], ignore_index=True)
    league = float(use.shots_on_target.mean()) if len(use) else 4.2
    out = {}
    for team, g in use.groupby("team_id"):
        g = g.sort_values("kickoff_at", ascending=False)
        wa = 2.0 ** (-np.arange(len(g)) / 13.0)
        wd = 2.0 ** (-np.arange(len(g)) / 20.0)
        out[int(team)] = (float(np.average(g.shots_on_target, weights=wa)), float(np.average(g.shots_on_target_conceded, weights=wd)), len(g))
    return out, league


def dc_context(pf: pd.DataFrame, deadline: pd.Timestamp, state: pd.DataFrame):
    h = pf[(pf.season == SEASON) & (pf.kickoff_at < deadline)].copy()
    pos = h.groupby("fpl_position").agg(dc=("defcon_count", "sum"), mins=("minutes", "sum"))
    posrate = {p: 90*float(r.dc)/max(float(r.mins), 1.0) for p, r in pos.iterrows()}
    out = {}
    tau = float(DC["position_prior_minutes_tau"]); half = float(DC["player_dc_half_life"])
    for r in state.itertuples():
        q = h[h.player_uuid == r.player_uuid]
        cnt, mins = _weighted_player_rate(q, "defcon_count", half)
        prior = posrate.get(r.position_model, 0.0)
        rate = 90*(cnt + tau*prior/90)/max(mins+tau, 1.0)
        out[str(r.player_uuid)] = max(0.0, float(r.xmins)/90*rate)
    return out


def build_tasks(pf, tf, sot, meta_by_origin):
    deadlines = deadline_by_gw(tf[tf.season == SEASON])
    schedule = tf[tf.season == SEASON].copy()
    prior = prior_team_strength(tf)
    tasks=[]; context={}; audit=[]
    sparams=SOTRateParams(
        opponent_weight=float(KEEPER["selected_sot"]["opponent_sot_for_weight"]),
        intercept=float(KEEPER["selected_sot"]["intercept"]),
        attacker_home_log_effect=float(KEEPER["selected_sot"]["attacker_home_log_effect"]),
    )
    zparams=SaveRateParams(
        intercept=float(KEEPER["selected_save"]["intercept"]),
        sot_exponent=float(KEEPER["selected_save"]["sot_exponent"]),
        attacker_home_log_effect=float(KEEPER["selected_save"]["attacker_home_log_effect"]),
    )
    assist_tot = pf[pf.season.isin(["2023-24", PRIOR])] if "2023-24" in set(pf.season) else pf[pf.season == PRIOR]
    # Preserve Phase 5Q's fixed historical standard/fantasy-assist split.
    assist_total_probability = 0.8998682476943346
    fantasy_assist_probability = assist_total_probability * (252.0 / 942.0)
    standard_assist_probability = assist_total_probability - fantasy_assist_probability
    task_no=0
    for origin in range(1, 39):
        deadline=deadlines[origin]; meta=meta_by_origin[origin]
        st=player_state(meta,pf,deadline,origin)
        future=schedule[schedule.gw.between(origin,min(38,origin+5))]
        history=schedule[schedule.kickoff_at < deadline]
        teams=sorted(set(meta.team.astype(int)))
        lmap=team_lambdas(origin,future,history,teams,prior)
        sstate,sleague=sot_state(sot,deadline,origin)
        dcmap=dc_context(pf,deadline,st)
        for fix, sides in future.groupby("fixture_uuid"):
            sides=sides.sort_values("was_home",ascending=False)
            if len(sides)!=2: continue
            home=int(sides.iloc[0].team_id); away=int(sides.iloc[1].team_id)
            group=st[st.team.isin([home,away])].copy()
            forecasts=[]
            for team,tg in group.groupby("team"):
                props_goal=np.maximum(0,tg.xmins.to_numpy(float)/90*tg.goal90.to_numpy(float))
                props_ass=np.maximum(0,tg.xmins.to_numpy(float)/90*tg.assist90.to_numpy(float))
                sg=float(props_goal.sum()); sa=float(props_ass.sum())
                opp=away if int(team)==home else home
                opp_for=sstate.get(opp,(sleague,sleague,0))[0]
                team_against=sstate.get(int(team),(sleague,sleague,0))[1]
                attacker_home=(opp==home)
                lsot=forecast_source_sot_mean(opp_for,team_against,sleague,attacker_was_home=attacker_home,params=sparams)
                lsave=forecast_fpl_save_mean(lsot,attacker_was_home=attacker_home,params=zparams)
                for j,r in enumerate(tg.itertuples()):
                    goal_mu=(props_goal[j]/sg*lmap[(fix,int(team))]) if sg>0 else 0.0
                    assist_mu=(props_ass[j]/sa*lmap[(fix,int(team))]) if sa>0 else 0.0
                    forecasts.append(FrozenPlayerForecast(
                        player_id=str(r.player_uuid),team_id=int(team),position=str(r.position_model),
                        p_start=float(r.p_start),expected_minutes=float(r.xmins),
                        start_minutes_mean=float(r.start_minutes_mean),cameo_minutes_mean=float(r.cameo_minutes_mean),
                        p_cameo_given_bench=float(r.p_cameo),goal_mu=float(goal_mu),assist_mu=float(assist_mu),
                        dc_mu=float(dcmap.get(str(r.player_uuid),0.0)),
                        dc_alpha=float({"DEF":1.6136326854524488,"MID":.9017026562284318,"FWD":.14670110956291363}.get(str(r.position_model),0.0)),
                        p_yellow=float(r.p_yellow),p_red=float(r.p_red),
                        lambda_saves=float(lsave if str(r.position_model)=="GK" else 0.0),
                    ))
            inp=build_match_input(home_team_id=home,away_team_id=away,
                lambda_home_goals=lmap[(fix,home)],lambda_away_goals=lmap[(fix,away)],players=forecasts,
                assist_probability_per_goal=standard_assist_probability,
                fantasy_assist_probability_per_goal=fantasy_assist_probability)
            gw=int(sides.iloc[0].gw)
            tasks.append((origin,gw,fix,inp,SEED+task_no,N_SIM));task_no+=1
            context[(origin,gw,fix)] = group[["id","player_uuid","web_name","position","p_play"]].copy()
        audit.append({"origin_gw":origin,"deadline":deadline.isoformat(),"history_matches":int(history.fixture_uuid.nunique()),"known_players":int(len(meta)),"future_fixtures":int(future.fixture_uuid.nunique()),"cold_start":origin<=5})
    return tasks,context,pd.DataFrame(audit)


def simulate_task(task):
    origin,gw,fix,inp,seed,n=task
    return origin,gw,fix,simulate_many(inp,n=n,seed=seed)


def main():
    started=time.time();OUT.mkdir(parents=True,exist_ok=True)
    pf,tf,sot,mapping,names=load_data()
    # 2023/24 is needed only for the fixed Phase 5Q assist-frequency constant,
    # which is already encoded above; all state rows are 2024/25 or 2025/26.
    meta=current_meta_by_origin(mapping,names)
    tasks,context,audit=build_tasks(pf,tf,sot,meta)
    results=[]
    with ProcessPoolExecutor(max_workers=6) as pool:
        fut=[pool.submit(simulate_task,t) for t in tasks]
        for done,f in enumerate(as_completed(fut),1):
            origin,gw,fix,sim=f.result(); m=context[(origin,gw,fix)]
            for r in m.itertuples():
                z=sim.get(str(r.player_uuid))
                if z is None: continue
                results.append({"origin_gw":origin-1,"decision_gw":origin,"gw":gw,"fixture_uuid":fix,
                    "id":int(r.id),"web_name":str(r.web_name),"position":str(r.position),
                    "xpts_fixture":float(z["xPts"]),"p_play_fixture":float(r.p_play)})
            if done%100==0 or done==len(fut): print(f"completed {done}/{len(fut)} rolling fixtures",flush=True)
    raw=pd.DataFrame(results)
    grouped=raw.groupby(["origin_gw","decision_gw","gw","id","web_name","position"],as_index=False).agg(
        xpts_mean=("xpts_fixture","sum"), fixtures=("fixture_uuid","nunique"),
        p_no_play=("p_play_fixture",lambda x:float(np.prod(1-np.clip(x,0,1)))),
    )
    grouped["p_play"]=1-grouped.pop("p_no_play")
    grouped.to_csv(OUT/"rolling_phase5q_forecasts.csv",index=False)
    raw.to_csv(OUT/"rolling_fixture_forecasts.csv",index=False)
    audit.to_csv(OUT/"cutoff_audit.csv",index=False)
    manifest={"phase":"5T","season":SEASON,"model":"Phase 5Q legacy-minutes + h12/ridge.25 reference, rolling state",
        "origins":[1,38],"horizons":[1,6],"n_sim":N_SIM,"fixture_rows":len(raw),"player_gw_rows":len(grouped),
        "gw1_5":"previous-season cold-start state; reported separately",
        "cutoff":"matches with kickoff strictly before estimated deadline (first GW kickoff minus 90 minutes)",
        "prices":"not used in forecast generation; replay uses archived weekly merged_gw value",
        "fixture_schedule_caveat":"final archived 2025/26 GW assignment used because timestamped 2025/26 schedule snapshots are unavailable",
        "defcon_caveat":"selected DC parameters were developed on 2025/26 GW6-21; only GW22-38 is later temporal validation",
        "runtime_seconds":time.time()-started}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
