"""Cutoff-safe relative Future Match Importance v2 features."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from .match_importance import canonical_competition,opponent_strength_from_elo
from .relative_match_importance import (
    infer_stage_2025_26,normalized_competition_shares_v2,premier_race_multiplier,
)

def _unique_matches(sched:pd.DataFrame)->pd.DataFrame:
    cols=["match_id","competition","kickoff","home_team_id","away_team_id",
          "home_score","away_score","finished","gameweek"]
    use=[c for c in cols if c in sched.columns]
    x=sched[use].drop_duplicates("match_id").copy()
    x["kickoff"]=pd.to_datetime(x.kickoff,utc=True,errors="coerce")
    return x

def premier_table_before(sched:pd.DataFrame,cutoff)->pd.DataFrame:
    """Reconstruct PL table using only matches completed before cutoff."""
    x=_unique_matches(sched)
    cut=pd.Timestamp(cutoff)
    if cut.tzinfo is None:cut=cut.tz_localize("UTC")
    else:cut=cut.tz_convert("UTC")
    x=x[(x.competition.eq("prem"))&(x.kickoff<cut)&x.finished.fillna(False)]
    teams=sorted(set(pd.to_numeric(x.home_team_id,errors="coerce").dropna().astype(int))|
                 set(pd.to_numeric(x.away_team_id,errors="coerce").dropna().astype(int)))
    rec={t:{"team_id":t,"played":0,"points":0.0,"gf":0.0,"ga":0.0} for t in teams}
    for r in x.itertuples(index=False):
        if pd.isna(r.home_team_id) or pd.isna(r.away_team_id):continue
        if pd.isna(r.home_score) or pd.isna(r.away_score):continue
        h,a=int(r.home_team_id),int(r.away_team_id);hs,as_=float(r.home_score),float(r.away_score)
        for t in (h,a):
            rec.setdefault(t,{"team_id":t,"played":0,"points":0.0,"gf":0.0,"ga":0.0})
            rec[t]["played"]+=1
        rec[h]["gf"]+=hs;rec[h]["ga"]+=as_;rec[a]["gf"]+=as_;rec[a]["ga"]+=hs
        if hs>as_:rec[h]["points"]+=3
        elif hs<as_:rec[a]["points"]+=3
        else:rec[h]["points"]+=1;rec[a]["points"]+=1
    if not rec:return pd.DataFrame(columns=["team_id","played","points","gd","position"])
    out=pd.DataFrame(rec.values())
    out["gd"]=out.gf-out.ga
    out=out.sort_values(["points","gd","gf"],ascending=[False,False,False]).reset_index(drop=True)
    out["position"]=np.arange(1,len(out)+1)
    return out

def _race_mult(table:pd.DataFrame,team:int,opp:int|None,gw:int)->float:
    if table.empty or opp is None:return 1.0
    idx=table.set_index("team_id")
    if team not in idx.index or opp not in idx.index:return 1.0
    t=idx.loc[team];o=idx.loc[opp]
    bypos={int(r.position):float(r.points) for r in table.itertuples(index=False)}
    remaining=max(1,38-int(round(float(t.played))))
    return premier_race_multiplier(
        position=int(t.position),points=float(t.points),
        opponent_position=int(o.position),opponent_points=float(o.points),
        table_points_by_position=bypos,games_remaining=remaining)

def _next_by_comp(team_sched:pd.DataFrame,after)->dict[str,pd.Series]:
    z=team_sched[team_sched.kickoff>after].sort_values("kickoff")
    out={}
    for _,r in z.iterrows():
        c=canonical_competition(r.competition)
        if c not in out:out[c]=r
    return out

def _active_context(team_sched:pd.DataFrame,after,gw:int,table:pd.DataFrame,
                    current_opp:int|None=None)->tuple[list[tuple[str,str]],dict[str,float]]:
    """Competitions with a known future fixture in this cutoff snapshot.

    This is intentionally conservative: unknown future draws are not invented.
    PL is kept active through GW38.
    """
    nxt=_next_by_comp(team_sched,after)
    if "prem" not in nxt and gw<=38:
        # PL remains an active competition even if no later row is visible.
        nxt["prem"]=pd.Series({"competition":"prem","kickoff":after,"gameweek":gw,
                                "opponent_team_id":current_opp,"opponent_elo":np.nan})
    active=[];mult={}
    for comp,r in nxt.items():
        stage=infer_stage_2025_26(comp,r.get("kickoff"),r.get("gameweek",gw))
        active.append((comp,stage))
        if comp=="prem":
            opp=r.get("opponent_team_id")
            opp=None if pd.isna(opp) else int(opp)
            mult[comp]=_race_mult(table,int(team_sched.iloc[0].team_id),opp,gw)
        else:
            # modest opponent modifier; stage remains the dominant cup signal.
            os=opponent_strength_from_elo(r.get("opponent_elo"))
            mult[comp]=0.85+0.30*float(os)
    return active,mult

def _shares(active,mult):
    # Generic fixed-budget normalization with context multipliers.
    from .relative_match_importance import raw_competition_priority
    raw={}
    for comp,stage in active:
        c=canonical_competition(comp)
        raw[c]=raw.get(c,0.0)+raw_competition_priority(c,stage)*float(mult.get(c,1.0))
    den=sum(raw.values())
    return {k:(v/den if den>0 else 0.0) for k,v in raw.items()}

def add_relative_future_mi_v2(frame:pd.DataFrame,snapshots:dict[int,pd.DataFrame],*,tau_days=4.0)->pd.DataFrame:
    out=frame.copy();vals=[]
    for r in out.itertuples(index=False):
        gw,team=int(r.gw),int(r.team_id);sched=snapshots.get(gw)
        if sched is None or sched.empty:
            vals.append((0.,0.,0.,0.,1.,np.nan,np.nan));continue
        ts=sched[sched.team_id.eq(team)].copy()
        if ts.empty:
            vals.append((0.,0.,0.,0.,1.,np.nan,np.nan));continue
        target_ko=getattr(r,"target_kickoff",None)
        cur=pd.DataFrame()
        if target_ko is not None and pd.notna(target_ko):
            tk=pd.Timestamp(target_ko)
            if tk.tzinfo is None:tk=tk.tz_localize("UTC")
            else:tk=tk.tz_convert("UTC")
            cur=ts[(ts.competition.eq("prem"))&(ts.kickoff.eq(tk))]
        if cur.empty:
            cur=ts[(ts.competition.eq("prem"))&(ts.match_id.astype(str).eq(str(r.fixture_uuid)))]
        if cur.empty:
            vals.append((0.,0.,0.,0.,1.,np.nan,np.nan));continue
        currow=cur.iloc[0];cko=pd.Timestamp(currow.kickoff)
        cutoff=pd.Timestamp(r.cutoff)
        table=premier_table_before(sched,cutoff)
        copp=currow.get("opponent_team_id")
        copp=None if pd.isna(copp) else int(copp)

        # Current budget uses all competitions with a known future fixture in the
        # cutoff snapshot, plus the current PL match.
        after_before_current=cko-pd.Timedelta(microseconds=1)
        active,mult=_active_context(ts,after_before_current,gw,table,copp)
        cur_stage=infer_stage_2025_26("prem",cko,gw)
        active=[x for x in active if x[0]!="prem"]+[("prem",cur_stage)]
        mult["prem"]=_race_mult(table,team,copp,gw)
        shares=_shares(active,mult)
        cur_share=float(shares.get("prem",0.0))

        future=ts[ts.kickoff>cko].sort_values("kickoff")
        if future.empty:
            vals.append((cur_share,0.,0.,0.,mult["prem"],np.nan,np.nan));continue
        nxt=future.iloc[0];days=(pd.Timestamp(nxt.kickoff)-cko).total_seconds()/86400.
        ncomp=canonical_competition(nxt.competition)
        # Recompute budget anchored immediately before the next match.
        active2,mult2=_active_context(ts,pd.Timestamp(nxt.kickoff)-pd.Timedelta(microseconds=1),
                                     int(nxt.get("gameweek",gw) if pd.notna(nxt.get("gameweek",gw)) else gw),
                                     table,None)
        nstage=infer_stage_2025_26(ncomp,nxt.kickoff,nxt.get("gameweek",gw))
        active2=[x for x in active2 if x[0]!=ncomp]+[(ncomp,nstage)]
        if ncomp=="prem":
            nopp=nxt.get("opponent_team_id");nopp=None if pd.isna(nopp) else int(nopp)
            mult2["prem"]=_race_mult(table,team,nopp,gw)
        else:
            mult2[ncomp]=0.85+0.30*opponent_strength_from_elo(nxt.get("opponent_elo"))
        shares2=_shares(active2,mult2)
        next_share=float(shares2.get(ncomp,0.0))
        decay=math.exp(-max(0.,days)/float(tau_days))
        # v2.1: absolute future importance. A highly important next match should
        # create rotation pressure even when the current PL match is also important.
        pressure=next_share*decay
        vals.append((cur_share,next_share,pressure,days,mult["prem"],ncomp,nstage))

    z=pd.DataFrame(vals,columns=[
      "mi2_current_share","mi2_next_share","mi2_rotation_pressure","mi2_days_to_next",
      "mi2_pl_race_multiplier","mi2_next_competition","mi2_next_stage"],index=out.index)
    for c in z:out[c]=z[c]
    p=out.mi2_rotation_pressure.fillna(0.).to_numpy(float)
    cur=out.mi2_current_share.fillna(0.).to_numpy(float)
    for h in ("role_h_fast","role_h_slow"):
        if h in out:
            hv=pd.to_numeric(out[h],errors="coerce").fillna(0.).to_numpy()
            out["mi2_"+h+"_pressure"]=hv*p
            out["mi2_"+h+"_current"]=hv*cur
    if "work_minutes_7d" in out:
        out["mi2_work7_pressure"]=np.clip(pd.to_numeric(out.work_minutes_7d,errors="coerce").fillna(0.).to_numpy()/180.,0.,2.)*p
    if "work_starts_7d" in out:
        out["mi2_starts7_pressure"]=np.clip(pd.to_numeric(out.work_starts_7d,errors="coerce").fillna(0.).to_numpy()/2.,0.,2.)*p
    return out