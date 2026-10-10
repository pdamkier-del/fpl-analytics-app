"""Archived predeadline 2026 official FPL cohort validation.

Use source actual 2026 FPL ID+club+position as an eligibility key; exclude
any post-hoc participant absent from the authentic predeadline snapshot.
An archive 1-6h before deadline is evidence at that timestamp, NOT exact
deadline completeness or a substitute for matchday lineup news.
"""
from pathlib import Path
import json
import pandas as pd

POS={1:"GK",2:"DEF",3:"MID",4:"FWD"}

def load_archived_rosters(folder,expected_gws=(1,2,3,4,5)):
    folder=Path(folder)
    records={}
    evidence={}
    for gw in expected_gws:
        obj=json.loads((folder/f"gw{gw}.json").read_text())
        e=obj["evidence"]
        if int(e["gw"])!=gw:
            raise ValueError("Wrong archived roster GW")
        asof=pd.Timestamp(e["snapshot_at_utc"])
        deadline=pd.Timestamp(e["official_deadline"])
        if not asof<deadline:
            raise ValueError("Postdeadline archived roster")
        people=obj["players"]
        if len(people)!=int(e["players"]) or len({int(x["id"]) for x in people})!=len(people):
            raise ValueError("Archived roster inconsistent or duplicate")
        records[gw]={int(p["id"]):p for p in people}
        evidence[gw]=e
    return records,evidence

def filter_observed_against_snapshots(rows,archived):
    required={"gw","fpl_element","team_id","fpl_position"}
    if missing:=required-set(rows):
        raise ValueError("Missing player outcome identity: "+str(sorted(missing)))
    x=rows.copy()
    eligible=[]
    reason=[]
    for r in x.itertuples(index=False):
        gw=int(r.gw)
        pool=archived.get(gw)
        if pool is None:raise ValueError("Historical GW lacks archived source")
        p=pool.get(int(r.fpl_element))
        if p is None:
            eligible.append(False);reason.append("not_in_predeadline_roster")
        elif int(p["team"])!=int(r.team_id):
            eligible.append(False);reason.append("predeadline_club_differs_from_postmatch")
        elif POS[int(p["position"])]!=str(r.fpl_position):
            eligible.append(False);reason.append("predeadline_position_mismatch")
        else:
            eligible.append(True);reason.append("matching_archived_roster")
    x["_archive_eligibility"]=eligible
    x["_archive_reason"]=reason
    return x
