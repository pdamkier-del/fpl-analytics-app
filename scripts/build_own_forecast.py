"""Transparent experimental FPL xP baseline from official 2026/27 observed stats.
NOT the locked MM/vFinal. Does not consult ep_next, future scores, or future outcomes.
Only fixture metadata for unplayed games. Forecasts remain provisional.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
import json,math
APP=Path(__file__).resolve().parents[1]/"app"

def value(x,default=0.0):
    try:
        a=float(x)
        return a if math.isfinite(a) else default
    except (ValueError,TypeError):return default
def clamp(x,lo,hi):return max(lo,min(hi,x))
def calculate(people,games):
    players=people["players"];fixtures=games["fixtures"]
    next_gw=people.get("next_gw")
    remaining=sorted({int(f["gw"]) for f in fixtures if f.get("gw") is not None and not f.get("finished")})
    if next_gw is not None:remaining=[g for g in remaining if g>=int(next_gw)]
    horizon=remaining[:6]
    completed=defaultdict(int)
    for f in fixtures:
        if f.get("finished") and f.get("gw") is not None:
            completed[int(f["home"])]+=1;completed[int(f["away"])]+=1
    by_team_gw=defaultdict(list)
    for f in fixtures:
        if f.get("gw") in horizon and not f.get("finished"):
            by_team_gw[(int(f["home"]),int(f["gw"]))].append((f,True))
            by_team_gw[(int(f["away"]),int(f["gw"]))].append((f,False))
    rows=[]
    prior_xg={1:.005,2:.075,3:.18,4:.39}
    prior_xa={1:.008,2:.085,3:.18,4:.13}
    for p in players:
        team=int(p["team"]);pos=int(p["position"]);mins=max(0,value(p.get("minutes")))
        games_played=completed[team]
        starts=clamp(value(p.get("starts")),0,38)
        # Deliberately conservative hierarchical early-season estimates.
        start_rate=(starts+1.4)/(max(1,games_played)+2.6)
        mean_start_mins=clamp((mins/max(1,starts)) if starts else 73,45,90)
        chance=p.get("chance_of_playing_next_round")
        availability=1 if p.get("status")=="a" else (clamp(value(chance,60)/100,0,1) if p.get("status")=="d" else .1)
        pstart=clamp(start_rate*availability,0,.96)
        xmins=clamp((pstart*mean_start_mins+(1-pstart)*min(.28,starts/max(2,games_played)) * 18),0,90)
        exposure=max(0,mins/90)
        xg=(value(p.get("expected_goals"))+2.8*prior_xg[pos])/(exposure+2.8)
        xa=(value(p.get("expected_assists"))+2.8*prior_xa[pos])/(exposure+2.8)
        # Official FPL points rules; bonus/discipline on observed per-minute smoothed basis.
        gpts={1:6,2:6,3:5,4:4}[pos]
        bps=clamp((value(p.get("bonus"))+.3)/(exposure+3),0,.9)
        cards=clamp((value(p.get("yellow_cards"))+3*.09)/(exposure+3),0,.3)
        player_weeks=[]
        for gw in horizon:
            matches=by_team_gw.get((team,gw),[])
            if not matches:continue
            fixture_preds=[]
            for f,home in matches:
                difficulty=value(f.get("difficulty_home" if home else "difficulty_away"),3)
                if difficulty<=0:difficulty=3
                factor=clamp(1+(.12*(3-difficulty))+(.06 if home else -.05),.7,1.3)
                attack_factor=factor
                defense_factor=clamp(1+(.14*(difficulty-3))-(.06 if home else -.02),.7,1.35)
                expected_goals=xg*attack_factor*xmins/90
                expected_assists=xa*attack_factor*xmins/90
                appearance=2*pstart + 1*(1-pstart)*clamp(xmins/28,0,1)
                cs_prob=math.exp(-1.45*defense_factor)
                cs=(4 if pos<=2 else 1 if pos==3 else 0)*cs_prob*clamp(xmins/90,0,1)
                concede= -(1.45*defense_factor/2)*clamp(xmins/90,0,1) if pos<=2 else 0
                saves=max(0,value(p.get("saves"))+8)/(exposure+8)*xmins/90/3 if pos==1 else 0
                bonus=bps*xmins/90
                disciplinary=-cards*xmins/90
                total=max(0,appearance+gpts*expected_goals+3*expected_assists+cs+concede+saves+bonus+disciplinary)
                fixture_preds.append({"fixture_id":f["id"],"opponent":f["away"] if home else f["home"],
                                      "home":home,"difficulty":difficulty,"xpts":round(total,3)})
            player_weeks.append({"gw":gw,"xpts":round(sum(x["xpts"] for x in fixture_preds),3),
                                 "xmins":round(xmins*len(matches),2),
                                 "pstart":round(pstart,4),"fixtures":fixture_preds})
        if player_weeks:
            rows.append({"id":p["id"],"team":team,"position":pos,"name":p["web_name"],
                         "price":p["price"],"xg90":round(xg,4),"xa90":round(xa,4),
                         "weeks":player_weeks})
    return {"schema_version":1,"model":"experimental_owned_xp_v0","locked_model_active":False,
        "source":"2026/27 official FPL stats + original transparent estimation; never ep_next",
        "data_asof":people["fetched_at"],"computed_at":datetime.now(timezone.utc).isoformat(),
        "season":"2026/27","next_gw":next_gw,"gws":horizon,
        "caveat":"Experimental independent xP baseline; NOT the user's frozen MM/PM/vFinal. Provisional start and fixture models.",
        "players":rows}

def main():
    people=json.loads((APP/"current-players.json").read_text())
    games=json.loads((APP/"live-fixtures.json").read_text())
    assert people["fetched_at"]==games["fetched_at"]
    o=calculate(people,games)
    assert len(o["players"])>=250
    assert all(0<=w["xpts"]<=50 and 0<=w["pstart"]<=1 for p in o["players"] for w in p["weeks"])
    assert not o["locked_model_active"]
    (APP/"own-forecast.json").write_text(json.dumps(o,ensure_ascii=False,separators=(",",":"),allow_nan=False))
    print("EXPERIMENTAL OWN xP:",len(o["players"]),"players for GWs",o["gws"])
if __name__=="__main__":main()
