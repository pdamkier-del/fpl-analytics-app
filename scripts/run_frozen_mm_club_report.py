"""Turn existing frozen MM replay candidates into per-team paired error reports.

Run after scripts/individual_mm_validation.py has produced season candidates.
This script NEVER fits a new model, reconstructs injuries or reads target
outcomes as forecast features. It evaluates already-frozen predictions.
"""
import argparse
import csv
import gzip
import json
from pathlib import Path
import pandas as pd
from research_role_injury_club_audit import club_error_report

BASE = Path(__file__).resolve().parents[1]
REQUIRED = {"season","fixture_uuid","player_uuid","team_id","minutes","mode","x"}

def run(source, destination, candidate_mode="role_start"):
    rows = pd.read_csv(source, compression="infer")
    missing = REQUIRED.difference(rows.columns)
    if missing:
        raise ValueError(f"Missing frozen replay fields: {sorted(missing)}")
    if rows[list(REQUIRED)].isna().any().any():
        raise ValueError("Missing canonical identity / truth / predictions")
    actual_key = ["season","fixture_uuid","player_uuid"]
    original = rows[rows["mode"]=="original"].copy()
    candidate = rows[rows["mode"]==candidate_mode].copy()
    for kind, table in [("original",original),("candidate",candidate)]:
        if table.duplicated(actual_key).any():
            raise ValueError(f"Duplicate {kind} player fixture")
    if original.empty or candidate.empty:
        raise ValueError("Missing original or candidate forecasts")
    # Read the exact shared player-fixture cohort, not an invented fill.
    pairs=original.merge(candidate,on=actual_key,how="outer",
       suffixes=("_original","_candidate"),indicator=True,validate="one_to_one")
    if not pairs["_merge"].eq("both").all():
        raise ValueError("Original/candidate cohort mismatch")
    if not pairs["team_id_original"].eq(pairs["team_id_candidate"]).all():
        raise ValueError("Club identity changed between arms")
    if not pairs["minutes_original"].eq(pairs["minutes_candidate"]).all():
        raise ValueError("Different truth between arms")
    if "gw_original" in pairs:
        if not pairs.gw_original.eq(pairs.gw_candidate).all():
            raise ValueError("Gameweek mismatch")
        season = str(pairs.season.iloc[0])
        pairs=pairs[pairs.gw_original.ge(22) if season=="2024-25" else pairs.gw_original.ge(6)]
    scored=[dict(season=r.season,club=f"{r.season}:{r.team_id_original}",
      player_uuid=r.player_uuid,fixture_uuid=r.fixture_uuid,
      actual_minutes=r.minutes_original,baseline_minutes=r.x_original,
      candidate_minutes=r.x_candidate) for r in pairs.itertuples(index=False)]
    report=club_error_report(scored)
    out=Path(destination);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"candidate":candidate_mode,"source":str(source),
        "rows":len(scored),"club_metrics":report,
        "no_medically_verified_injury_labels":True,
        "independent_holdout":False},indent=2)+"\n",encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--mode",default="role_start")
    args=p.parse_args()
    report=run(args.input,args.out,args.mode)
    for r in report:
        print(f"{r['club']} n={r['n']} baseline={r['original_mae']:.2f} candidate={r['candidate_mae']:.2f} delta={r['delta_mae']:+.2f}")

if __name__=="__main__":
    main()
