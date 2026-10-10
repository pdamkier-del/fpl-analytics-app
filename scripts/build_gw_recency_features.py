"""Derive leakage-safe recency features for the NEXT GW from completed official FPL events.

Input: app/gw-source-features.json (with past GW histories).
Output: app/gw-recency-features.json, a non-certified source feature layer.
This deliberately does not claim to run the locked minutes model.
"""
import json,math,statistics
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/"app"
def numeric(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else 0.0
    except (ValueError,TypeError):return 0.0
def aggregate(history,field,k):
    return sum(numeric(h.get(field)) for h in history[-k:])
def main():
    data=json.loads((APP/"gw-source-features.json").read_text())
    gw=data["gw"];out=[]
    for row in data["rows"]:
        history=sorted(row["recent_finished_gws"],key=lambda a:a["gw"])
        if any(h["gw"]>=gw for h in history):raise ValueError("Post-cutoff match history")
        last=history[-1] if history else {}
        decay=[0.5**(gw-1-h["gw"]) for h in history]
        total=sum(decay)
        wm=sum(w*numeric(h.get("minutes")) for h,w in zip(history,decay))/total if total else None
        starts=sum(numeric(h.get("starts")) for h in history)
        # FPL GW 'starts' is GW-specific; verify in bounds without clipping bad data.
        if any(numeric(h.get("starts"))<0 or numeric(h.get("starts"))>2 for h in history):raise ValueError("Bad historical starts")
        feature={"fixture_id":row["fixture_id"],"player_id":row["player_id"],"team_id":row["team_id"],
           "target_gw":gw,"history_n":len(history),"last_played_gw":max((h["gw"] for h in history if numeric(h.get("minutes"))>0),default=None),
           "minutes_last_1":numeric(last.get("minutes")) if history else None,
           "minutes_last_3":aggregate(history,"minutes",3),
           "minutes_last_5":aggregate(history,"minutes",5),
           "starts_last_3":aggregate(history,"starts",3),
           "starts_last_5":aggregate(history,"starts",5),
           "xg_last_5":round(aggregate(history,"expected_goals",5),4),
           "xa_last_5":round(aggregate(history,"expected_assists",5),4),
           "weighted_recent_minutes":round(wm,4) if wm is not None else None,
           "team_fixture_difficulty":row["team_fixture_difficulty"],
           "official_status":row["status"],
           "current_role_verified":False,"predeadline_team_news_verified":False,
           "locked_mm_feature_complete":False}
        out.append(feature)
    assert len(out)==data["player_fixture_count"]
    assert len({(r["fixture_id"],r["player_id"]) for r in out})==len(out)
    result={"schema_version":1,"classification":"current_GW_observed_recency_features_not_locked_MM",
       "gw":gw,"observed_at":data["observed_at"],"history_gws":data["completed_history_gws"],
       "count":len(out),"locked_mm_feature_complete":False,"rows":out}
    (APP/"gw-recency-features.json").write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False))
    print("VERIFIED CURRENT GW RECENCY FEATURES:",gw,len(out),"rows, prior GW",data["completed_history_gws"])
if __name__=="__main__":main()
