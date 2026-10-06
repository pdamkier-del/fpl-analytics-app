"""Cutoff-oriented forward Match Importance features.

For historical replay, future fixtures must come from the target GW snapshot,
not from the completed-season schedule. This avoids leaking later cup progress.
The signal is player-specific only through interactions with hierarchy/workload.
"""
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
import pandas as pd

from .match_importance import (
    BASE_COMPETITION_VALUES,canonical_competition,dynamic_competition_value,
    premier_league_stage_strength,knockout_stage_strength,opponent_strength_from_elo,
)

EURO={"champions-league","europa-league","conference-league"}

def _team_fixture_rows(matches:pd.DataFrame,code_to_team:dict[int,int])->pd.DataFrame:
    x=matches.copy()
    x["kickoff"]=pd.to_datetime(x.kickoff_time,utc=True,errors="coerce")
    x["competition"]=x.tournament.map(canonical_competition)
    rows=[]
    for r in x.itertuples(index=False):
        if pd.isna(r.kickoff): continue
        for side in ("home","away"):
            code=getattr(r,side+"_team",np.nan)
            if pd.isna(code) or int(code) not in code_to_team: continue
            oppside="away" if side=="home" else "home"
            opp_code=getattr(r,oppside+"_team",np.nan)
            rows.append({
                "match_id":str(r.match_id),"team_id":int(code_to_team[int(code)]),
                "opponent_team_id":(
                    int(code_to_team[int(opp_code)])
                    if pd.notna(opp_code) and int(opp_code) in code_to_team else np.nan
                ),
                "competition":str(r.competition),"kickoff":r.kickoff,
                "opponent_elo":getattr(r,oppside+"_team_elo",np.nan),
                "gameweek":getattr(r,"gameweek",np.nan),
                "home_team_id":(
                    int(code_to_team[int(getattr(r,"home_team"))])
                    if pd.notna(getattr(r,"home_team",np.nan)) and int(getattr(r,"home_team")) in code_to_team else np.nan
                ),
                "away_team_id":(
                    int(code_to_team[int(getattr(r,"away_team"))])
                    if pd.notna(getattr(r,"away_team",np.nan)) and int(getattr(r,"away_team")) in code_to_team else np.nan
                ),
                "home_score":getattr(r,"home_score",np.nan),
                "away_score":getattr(r,"away_score",np.nan),
                "finished":bool(getattr(r,"finished",False)),
            })
    return pd.DataFrame(rows)

def load_gw_schedule_snapshots(raw_root:Path,code_to_team:dict[int,int])->dict[int,pd.DataFrame]:
    out={}
    for gw in range(1,39):
        p=Path(raw_root)/f"GW{gw}"/"matches.csv"
        if not p.exists(): continue
        out[gw]=_team_fixture_rows(pd.read_csv(p),code_to_team)
    return out

def _importance(row,active_competitions,eta=.35):
    comp=canonical_competition(row["competition"])
    cv=dynamic_competition_value(comp,active_competitions,BASE_COMPETITION_VALUES,eta=eta)
    ko=pd.Timestamp(row["kickoff"])
    if comp=="prem":
        gw=row.get("gameweek")
        stage=premier_league_stage_strength(int(gw)) if pd.notna(gw) else .5
    else:
        stage=knockout_stage_strength(row.get("round_name"),ko.month)
    opp=opponent_strength_from_elo(row.get("opponent_elo"))
    # Same monotone components as existing MI; bounded weighted score is used
    # only to express current-vs-next relative scheduling pressure.
    return float(.45*cv+.30*stage+.25*opp)

def add_forward_match_importance(frame:pd.DataFrame,snapshots:dict[int,pd.DataFrame], *,
                                 tau_days=4.0,eta=.35)->pd.DataFrame:
    out=frame.copy()
    vals=[]
    for r in out.itertuples(index=False):
        gw=int(r.gw);team=int(r.team_id)
        sched=snapshots.get(gw)
        if sched is None or sched.empty:
            vals.append((np.nan,np.nan,np.nan,0.,0.,0.,0.));continue
        # The target fixture kickoff itself is the anchor; only fixtures present
        # in this GW's snapshot can become forward context.
        target_ko=getattr(r,"target_kickoff",None)
        cur=pd.DataFrame()
        if target_ko is not None and pd.notna(target_ko):
            tk=pd.Timestamp(target_ko)
            if tk.tzinfo is None: tk=tk.tz_localize("UTC")
            else: tk=tk.tz_convert("UTC")
            cur=sched[(sched.team_id.eq(team))&(sched.kickoff.eq(tk))]
        if cur.empty:
            cur=sched[(sched.team_id.eq(team))&(sched.match_id.astype(str).eq(str(r.fixture_uuid)))]
        if cur.empty:
            # Final conservative fallback: nearest PL fixture after deadline.
            cand=sched[(sched.team_id.eq(team))&(sched.competition.eq("prem"))]
            target_cut=pd.Timestamp(r.cutoff)
            future=cand[cand.kickoff>=target_cut]
            if future.empty:
                vals.append((np.nan,np.nan,np.nan,0.,0.,0.,0.));continue
            currow=future.sort_values("kickoff").iloc[0]
        else:
            currow=cur.iloc[0]
        current_ko=pd.Timestamp(currow.kickoff)
        future=sched[(sched.team_id.eq(team))&(sched.kickoff>current_ko)].sort_values("kickoff")
        if future.empty:
            vals.append((np.nan,np.nan,np.nan,0.,0.,0.,0.));continue
        nxt=future.iloc[0]
        days=(pd.Timestamp(nxt.kickoff)-current_ko).total_seconds()/86400.
        active=sorted(set(sched[sched.team_id.eq(team)].competition.astype(str)))
        cur_mi=_importance(currow,active,eta=eta)
        next_mi=_importance(nxt,active,eta=eta)
        gap=max(0.,next_mi-cur_mi)
        decay=math.exp(-max(0.,days)/float(tau_days))
        pressure=gap*decay
        vals.append((days,str(nxt.competition),next_mi,pressure,
                     float(str(nxt.competition) in EURO),float(str(nxt.competition)=="fa-cup"),
                     float(str(nxt.competition)=="efl-cup")))
    z=pd.DataFrame(vals,columns=[
        "future_days_to_next","future_next_competition","future_next_importance",
        "future_rotation_pressure","future_next_is_europe","future_next_is_fa_cup",
        "future_next_is_efl_cup"],index=out.index)
    for c in z: out[c]=z[c]

    # No common player-level intercept: interact pressure with hierarchy and
    # workload, so established/high-load players carry the strongest rest risk.
    p=out.future_rotation_pressure.fillna(0.).to_numpy(float)
    for h in ("role_h_fast","role_h_slow"):
        if h in out: out["future_"+h+"_pressure"]=out[h].to_numpy(float)*p
    if "work_minutes_7d" in out:
        out["future_work7_pressure"]=np.clip(out.work_minutes_7d.to_numpy(float)/180.,0.,2.)*p
    if "work_starts_7d" in out:
        out["future_starts7_pressure"]=np.clip(out.work_starts_7d.to_numpy(float)/2.,0.,2.)*p
    return out