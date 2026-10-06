"""Cutoff-safe structural context features for Minute Model promotion tests.

Families:
- formation-conditioned start/role history,
- cold-start shrinkage context,
- competition-specific rotation history,
- conditional goalkeeper change-point,
- lineup/regime-change evidence.

All historical outcomes are gated by available_at < target cutoff.
"""
from __future__ import annotations
from collections import defaultdict
import math
import numpy as np
import pandas as pd

def _utc(x):
    t=pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")

def _decay(lag,half):
    return 2.0**(-float(lag)/float(half))

class StructuralHistory:
    def __init__(self, classified:pd.DataFrame, official_minutes:pd.DataFrame|None=None,
                 team_coverage:pd.DataFrame|None=None):
        c=classified.copy()
        c["kickoff"]=pd.to_datetime(c["kickoff"],utc=True,errors="coerce")
        c["available_at"]=c["kickoff"]+pd.Timedelta(hours=3)
        # classified_starters is one row per observed starter in the PL role audit.
        self.pl_games=defaultdict(list)
        for (team,fixture),g in c.groupby(["team_id","fixture_uuid"],sort=False):
            if g.kickoff.isna().all(): continue
            form=str(g["formation"].dropna().iloc[0]) if "formation" in g and g["formation"].notna().any() else "UNKNOWN"
            players=[]
            for r in g.itertuples(index=False):
                uid=str(getattr(r,"player_uuid"))
                role=str(getattr(r,"final_role","UNKNOWN"))
                players.append((uid,role))
            self.pl_games[int(team)].append({
                "fixture":str(fixture),"kickoff":g.kickoff.iloc[0],
                "available_at":g.available_at.iloc[0],"formation":form,
                "players":players,"starters":set(x[0] for x in players),
            })
        for t in self.pl_games:
            self.pl_games[t].sort(key=lambda z:(z["available_at"],z["fixture"]))

        self.official=defaultdict(list)
        if official_minutes is not None and team_coverage is not None:
            p=official_minutes.copy()
            cov=team_coverage[["match_id","team_id","competition","kickoff","available_at"]].copy()
            cov["available_at"]=pd.to_datetime(cov.available_at,utc=True,errors="coerce")
            # official_player_minutes may already carry these metadata columns.
            # Only enrich fields that are missing to avoid _x/_y suffix drift.
            meta_cols=["competition","kickoff","available_at"]
            missing_meta=[x for x in meta_cols if x not in p.columns]
            if missing_meta:
                p=p.merge(cov[["match_id","team_id"]+missing_meta],
                          on=["match_id","team_id"],how="left",validate="many_to_one")
            if "available_at" not in p.columns:
                raise ValueError("official minutes missing available_at after metadata enrichment")
            p["available_at"]=pd.to_datetime(p["available_at"],utc=True,errors="coerce")
            for r in p.itertuples(index=False):
                if pd.isna(r.available_at): continue
                st=getattr(r,"started",np.nan)
                started=False if pd.isna(st) else bool(st)
                self.official[int(r.team_id)].append({
                    "available_at":r.available_at,"competition":str(r.competition),
                    "player_uuid":str(r.player_uuid),"started":started,
                    "minutes":float(r.minutes) if pd.notna(r.minutes) else 0.0,
                    "match_id":str(r.match_id),
                })
            for t in self.official:
                self.official[t].sort(key=lambda z:(z["available_at"],z["match_id"],z["player_uuid"]))

    def pl_before(self,team,cutoff):
        cut=_utc(cutoff)
        return [g for g in self.pl_games[int(team)] if g["available_at"]<cut]

    def formation_features(self,team,player,cutoff,half_life=5.0):
        games=self.pl_before(team,cutoff)
        if not games:
            return dict(form_cond_start_prior=0.0,form_role_concentration=0.0,
                        form_role_evidence=0.0,form_expected_seen=0.0)
        # formation prior from recent actual team shapes
        fm=defaultdict(float)
        for lag,g in enumerate(reversed(games)):
            fm[g["formation"]]+=_decay(lag,half_life)
        den=sum(fm.values()) or 1.
        fp={f:w/den for f,w in fm.items()}

        start_prior=0.;role_conc=0.;evidence=0.;expected_seen=0.
        for f,pf in fp.items():
            fg=[g for g in games if g["formation"]==f]
            # use within-formation recency order
            total=0.;starts=0.;roles=defaultdict(float)
            for lag,g in enumerate(reversed(fg)):
                w=_decay(lag,half_life)
                total+=w
                found=[role for uid,role in g["players"] if uid==str(player)]
                if found:
                    starts+=w
                    roles[found[0]]+=w
            if total:
                sp=starts/total
                start_prior+=pf*sp
                expected_seen+=pf*float(starts>0)
                evidence+=pf*starts
                if starts>0: role_conc+=pf*(max(roles.values())/starts)
        return dict(form_cond_start_prior=start_prior,
                    form_role_concentration=role_conc,
                    form_role_evidence=evidence,
                    form_expected_seen=expected_seen)

    def rotation_features(self,team,player,cutoff,half_life=6.0,max_games=30):
        cut=_utc(cutoff)
        rec=[x for x in self.official[int(team)] if x["available_at"]<cut][-max_games:]
        if not rec:
            return dict(rot_pl_start_share=0.,rot_nonpl_start_share=0.,
                        rot_europe_start_share=0.,rot_cup_start_share=0.,
                        rot_pl_minus_nonpl=0.,rot_evidence=0.)
        # aggregate one team-match denominator by competition
        matches={}
        pstarts=defaultdict(float);den=defaultdict(float)
        unique=[]
        seen=set()
        for x in rec:
            k=x["match_id"]
            if k not in seen:
                seen.add(k);unique.append((k,x["competition"],x["available_at"]))
        unique=unique[-max_games:]
        for lag,(mid,comp,at) in enumerate(reversed(unique)):
            w=_decay(lag,half_life)
            bucket="pl" if comp=="prem" else ("europe" if comp in {"champions-league","europa-league","conference-league"} else "cup")
            den[bucket]+=w
            den["nonpl"]+=w if bucket!="pl" else 0.
            rows=[x for x in rec if x["match_id"]==mid and x["player_uuid"]==str(player)]
            if rows and any(x["started"] for x in rows):
                pstarts[bucket]+=w
                if bucket!="pl": pstarts["nonpl"]+=w
        def sh(k): return pstarts[k]/den[k] if den[k]>0 else 0.
        pl,non=sh("pl"),sh("nonpl")
        return dict(rot_pl_start_share=pl,rot_nonpl_start_share=non,
                    rot_europe_start_share=sh("europe"),rot_cup_start_share=sh("cup"),
                    rot_pl_minus_nonpl=pl-non,rot_evidence=sum(den.values()))

    def gk_streak(self,team,player,cutoff,max_games=4):
        games=self.pl_before(team,cutoff)[-max_games:]
        streak=0
        for g in reversed(games):
            if str(player) in g["starters"]: streak+=1
            else: break
        return streak

    def regime_shift(self,team,cutoff,lookback=6):
        games=self.pl_before(team,cutoff)
        if len(games)<3:return 0.0
        last=games[-1]["starters"]
        older=games[max(0,len(games)-lookback-1):-1]
        if not older:return 0.0
        # similarity of latest XI to each older XI; lower similarity = larger shift.
        sims=[len(last & g["starters"])/11.0 for g in older]
        return float(max(0.,1.-np.mean(sims)))

def add_structural_context(frame:pd.DataFrame, history:StructuralHistory)->pd.DataFrame:
    out=frame.copy()
    cache={}
    rows=[]
    for r in out.itertuples(index=False):
        key=(int(r.team_id),str(r.player_uuid),str(r.cutoff))
        if key not in cache:
            z={}
            z.update(history.formation_features(r.team_id,r.player_uuid,r.cutoff))
            z.update(history.rotation_features(r.team_id,r.player_uuid,r.cutoff))
            z["gk_pl_streak"]=float(history.gk_streak(r.team_id,r.player_uuid,r.cutoff))
            z["team_regime_shift"]=history.regime_shift(r.team_id,r.cutoff)
            cache[key]=z
        rows.append(cache[key])
    z=pd.DataFrame(rows,index=out.index)
    for c in z:out[c]=z[c].astype(float)

    # Cold-start features: when formation/role evidence is weak, let recent
    # official workload serve as a shrinkage prior rather than treating zeros as
    # evidence that the player cannot start.
    low=(out.form_role_evidence<0.35).astype(float)
    out["cold_role_low_evidence"]=low
    if "work_starts_14d" in out:
        out["cold_work_starts14"]=low*np.clip(out.work_starts_14d.astype(float)/3.,0.,1.5)
    else: out["cold_work_starts14"]=0.
    if "work_minutes_14d" in out:
        out["cold_work_minutes14"]=low*np.clip(out.work_minutes_14d.astype(float)/270.,0.,1.5)
    else: out["cold_work_minutes14"]=0.

    # Conditional GK change-point. A PL streak is only treated as regime evidence
    # when another keeper is not currently hard-out and future rotation pressure
    # is not already a plausible explanation.
    pos=out.pos.astype(str).str.upper() if "pos" in out else pd.Series("",index=out.index)
    is_gk=pos.isin(["G","GK"]).astype(float)
    other_out=np.zeros(len(out),dtype=float)
    if "team_news_hard_out" in out:
        for idxs in out.groupby(["fixture_uuid","team_id"],sort=False).indices.values():
            idxs=np.asarray(idxs,dtype=int)
            gks=idxs[pos.iloc[idxs].isin(["G","GK"]).to_numpy()]
            for i in gks:
                other=[j for j in gks if j!=i]
                other_out[i]=float(any(out.iloc[j].team_news_hard_out>=.5 for j in other))
    pressure=np.clip(out.get("future_rotation_pressure",pd.Series(0.,index=out.index)).astype(float).to_numpy()/0.25,0.,1.)
    unexplained=is_gk.to_numpy()*np.clip(out.gk_pl_streak.to_numpy(float)/3.,0.,1.)*(1-other_out)*(1-pressure)
    out["gk_other_keeper_hard_out"]=other_out
    out["gk_unexplained_change_signal"]=unexplained

    # Regime interactions let the learner discount stale slow hierarchy when
    # the latest PL XI is structurally different from prior XIs.
    if "role_h_slow" in out:
        out["regime_h_slow_interaction"]=out.team_regime_shift*out.role_h_slow.astype(float)
    else:out["regime_h_slow_interaction"]=0.
    if "role_h_fast" in out:
        out["regime_h_fast_interaction"]=out.team_regime_shift*out.role_h_fast.astype(float)
    else:out["regime_h_fast_interaction"]=0.
    return out
