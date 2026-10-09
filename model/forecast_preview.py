"""Honest, testable preview of current bridge forecasts and chip opportunities.

This module does NOT run the locked MM→PM→TS/TC chain. The published bridge
provides static GW6–11 player forecasts, but no current locked PM/TC samples.
All opportunity weeks therefore carry the 'indicative_only' label.
Python standard library only: compatible with portable Windows app.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Any
import decision_optimizer as d

POS={"GK":2,"DEF":5,"MID":5,"FWD":3}
HALF=((1,19),(20,38))
WEIGHTS=(1.0,.60,.36,.216,.1296,.07776)

def _number(value, default=0.0):
    try:
        result=float(value)
        return result if isfinite(result) else default
    except (TypeError,ValueError):
        return default

def _asof(value):
    if not value:return None
    try:
        return datetime.fromisoformat(str(value).replace("Z","+00:00")).replace(tzinfo=timezone.utc) if datetime.fromisoformat(str(value).replace("Z","+00:00")).tzinfo is None else datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except ValueError:return None

def _gw_value(player, gw, field="xpts"):
    for record in player.get("gws") or []:
        if int(record.get("gw") or -1)==int(gw):
            return _number(record.get(field),None)
    return None

def _lineup(players, gw):
    # bridge optimizer uses the index into each player's forecast window
    first=int((players[0].get("gws") or [{}])[0].get("gw") or 0)
    gi=int(gw)-first
    return d.best_lineup(tuple(players),gi)

def _squad_score(players,gws):
    return sum(w * _lineup(players,gw)["total"] for w,gw in zip(WEIGHTS,gws))

def _candidate_pool(all_players, weeks, max_per_position=5):
    chosen={}
    for pos in POS:
        options=[p for p in all_players if p.get("pos")==pos
            and p.get("price") is not None
            and str(p.get("status") or "Available").lower() not in d.BAD_INCOMING_STATUSES]
        ranked=sorted(options,key=lambda p:sum(_number(_gw_value(p,gw)) * w for w,gw in zip(WEIGHTS,weeks)),reverse=True)
        singles=sorted(options,key=lambda p:_number(_gw_value(p,weeks[0])),reverse=True)
        chosen[pos]=tuple({int(p["id"]):p for p in [*ranked[:max_per_position],*singles[:max_per_position]]}.values())
    return chosen

def _optimize_candidate(base,all_players,bank,weeks,steps=3):
    """Small local-search *preview* using current prices, not purchase prices."""
    squad=list(base); budget=float(bank)
    pools=_candidate_pool(all_players,weeks)
    def score(team): return _squad_score(team,weeks)
    baseline=score(squad);best_score=baseline
    for _ in range(steps):
        choice=None
        ids={int(p["id"]) for p in squad}
        for index,outgoing in enumerate(squad):
            for incoming in pools.get(outgoing["pos"],()):
                iid=int(incoming["id"])
                if iid in ids:continue
                cash=budget+_number(outgoing.get("price"))-_number(incoming.get("price"))
                if cash < -1e-8:continue
                trial=list(squad);trial[index]=incoming
                if not d._club_ok(tuple(trial)):continue
                quality=score(trial)
                if quality>best_score+1e-7 and (choice is None or quality>choice[0]):
                    choice=(quality,index,incoming,cash)
        if choice is None:break
        best_score,index,incoming,budget=choice
        squad[index]=incoming
    return {"gain":round(max(0.,best_score-baseline),2),
        "squad_ids":[int(p["id"]) for p in squad],
        "out":[p.get("player") for p in base if int(p["id"]) not in {int(x["id"]) for x in squad}],
        "incoming":[p.get("player") for p in squad if int(p["id"]) not in {int(x["id"]) for x in base}]}

def forecast_preview(data:dict[str,Any], squad:dict[str,Any], *,now:datetime|None=None):
    meta=data.get("meta") or {};players=list(data.get("forecasts") or [])
    observed=_asof(meta.get("updated"))
    now=now or datetime.now(timezone.utc)
    age_hours=round((now-observed).total_seconds()/3600,1) if observed else None
    is_stale=age_hours is None or age_hours>72
    source=str(meta.get("model_version") or "unknown")
    player_ids=[int(x) for x in squad.get("player_ids") or []]
    indexed={int(p["id"]):p for p in players}
    selected=[indexed[x] for x in player_ids if x in indexed]
    gws=sorted({int(g.get("gw")) for p in players for g in (p.get("gws") or []) if g.get("gw") is not None})
    gws=[gw for gw in gws if gw>=int(meta.get("next_gw") or 1)][:6]
    alerts=[]
    if len(selected)!=15 or len(set(player_ids))!=15:
        alerts.append("Ingen komplet, gyldig 15-mandstrup gemt i My Team.")
    if is_stale:
        alerts.append("Forecastdata er forældede: opdater data før du bruger dem til en FPL-deadline.")
    if source!="locked_mm_pm_vfinal":
        alerts.append("xP kommer fra den ældre live-bridge, ikke den låste MM/PM/vFinal.")
    if len(gws)<6:
        alerts.append("Færre end seks forecast-GW er tilgængelige.")
    for p in selected:
        if any(_gw_value(p,gw) is None for gw in gws):
            alerts.append("En eller flere spillere mangler forecast i GW-vinduet.")
            break
    result={
       "mode":"bridge_preview_indicative_only", "locked_forecast_active":False,
       "data":{"season":meta.get("season"),"model_version":source,"updated":meta.get("updated"),
               "next_gw":meta.get("next_gw"),"forecast_end_gw":meta.get("forecast_end_gw"),
               "player_count":len(players),"fixture_count":len(data.get("fixtures") or []),
               "actual_count":len(data.get("actuals") or []),"age_hours":age_hours,
               "stale":is_stale,"available_gws":gws},
       "warning":"Illustrativ live-bridge-preview. Chipvinduer er IKKE output fra den låste fire-chip-model.",
       "alerts":list(dict.fromkeys(alerts)),"weeks":[],"chips":[],
    }
    if alerts and ("Ingen komplet" in " ".join(alerts) or not gws):
        return result
    try:
        d._LINEUP_CACHE.clear()
        for gw in gws:
            lineup=_lineup(selected,gw)
            bb_gross=sum(_number(_gw_value(p,gw)) for p in lineup["bench"])
            result["weeks"].append({"gw":gw,"xi_xp":round(lineup["total"],2),
                "formation":lineup["formation"],"captain":lineup["captain"]["player"],
                "captain_xp":round(_number(_gw_value(lineup["captain"],gw)),2),
                "bench_gross_xp":round(bb_gross,2),
                "xi":[{"id":int(p["id"]),"name":p["player"],"xpts":_gw_value(p,gw)}
                      for p in lineup["xi"]],
                "bench":[{"id":int(p["id"]),"name":p["player"],"xpts":_gw_value(p,gw)}
                      for p in lineup["bench"]]})
        bank=max(0.,_number(squad.get("bank")))
        if len(selected)==15 and d._club_ok(tuple(selected)):
            candidates={"fh":[],"wc":[]}
            for g in gws:
                tail=[n for n in gws if n>=g]
                fh=_optimize_candidate(selected,players,bank,[g],steps=2)
                wc=_optimize_candidate(selected,players,bank,tail,steps=3)
                first,end=(1,19) if g<=19 else (20,38)
                decay=(end-g)/(end-first)
                candidates["fh"].append({"gw":g,"gain":fh["gain"],"adjusted":round(fh["gain"]-10*decay,2),
                    "incoming":fh["incoming"],"out":fh["out"]})
                candidates["wc"].append({"gw":g,"gain":wc["gain"],"adjusted":round(wc["gain"]-20*decay,2),
                    "incoming":wc["incoming"],"out":wc["out"]})
            for kind,label in (("fh","Free Hit"),("wc","Wildcard")):
                best=max(candidates[kind],key=lambda z:z["adjusted"])
                result["chips"].append({"id":kind,"label":label,"candidate_gw":best["gw"] if best["adjusted"]>0 else None,
                    "expected_gain_proxy":best["gain"],"adjusted_proxy":best["adjusted"],
                    "confidence":"indicative_only", "reason":"Lokal, begrænset trupsøgning mod uændret trup; ikke fuld låst TS",
                    "incoming":best["incoming"],"out":best["out"]})
        # Bench Boost / Triple Captain cannot be certified from p(start) alone.
        bb=max(result["weeks"],key=lambda w:w["bench_gross_xp"])
        tc=max(result["weeks"],key=lambda w:w["captain_xp"])
        result["chips"].extend([
           {"id":"bb","label":"Bench Boost","candidate_gw":bb["gw"],"expected_gain_proxy":None,
            "bench_gross_xp":bb["bench_gross_xp"],"confidence":"indicative_only",
            "reason":"Højeste brutto-bænk-xP i det synlige vindue; autosub-sandsynligheder mangler."},
           {"id":"tc","label":"Triple Captain","candidate_gw":tc["gw"],"expected_gain_proxy":None,
            "captain_xp":tc["captain_xp"],"player":tc["captain"],"confidence":"indicative_only",
            "reason":"Højeste kaptajn-xP i synligt vindue; låst TC-v2 kræver simulationer og ukendt-DGW-option."},
        ])
    except (ValueError,KeyError,IndexError,TypeError) as exc:
        result["alerts"].append("Kunne ikke beregne en sammenhængende preview: "+str(exc))
    finally:
        d._LINEUP_CACHE.clear()
    return result
