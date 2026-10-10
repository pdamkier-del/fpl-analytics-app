#!/usr/bin/env python3
"""Export frozen MM output under the stable mm-release-v1 contract.

Historical behavior is unchanged. For a *current live* release, the explicitly
approved --live-hard-availability boundary requires original MM q/sub
outputs and cutoff-safe, player-scoped official Team News evidence.
This does not train a model or generate missing live MM predictions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fpl_v1_1_model.mm_release import normalize_mm_release,write_mm_release
from fpl_v1_1_model.live_availability_boundary import (
    BOUNDARY_VERSION,prepare_live_mm_release_candidate,validate_scoped_official_news,
)


def read_frame(path:Path):
    if path.suffix==".parquet":
        return pd.read_parquet(path)
    if path.name.endswith((".jsonl.gz",".jsonl")):
        return pd.read_json(path,lines=True,compression="infer")
    if path.suffix==".json":
        return pd.read_json(path)
    return pd.read_csv(path)


def sha256(path:Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(args):
    original=read_frame(Path(args.input))
    if not args.live_hard_availability:
        if args.season!="2025-26":
            raise ValueError("Current-season MM exports require approved --live-hard-availability")
        if any(x is not None for x in (args.origin_gw,args.news_ledger)):
            raise ValueError("--origin-gw/--news-ledger require --live-hard-availability")
        return write_mm_release(
            original,Path(args.out),model_version=args.model_version,
            season=args.season,p_start_col=args.p_start_col,
            xmins_col=args.xmins_col)

    if not (args.origin_gw and args.news_ledger):
        raise ValueError("Live release requires --origin-gw and --news-ledger")
    if args.season=="2025-26":
        raise ValueError("Never apply current live policy to locked historical 2025/26 replays")
    config=json.loads((ROOT/"config"/"fpl_locked_model.json").read_text())
    if args.model_version!=config["version"]:
        raise ValueError("Live release model-version differs from the frozen model")
    for c in (args.p_start_col,args.xmins_col,args.q_sub_col,
              args.sub_minutes_col,"start_minutes_mean",
              "team_news_state","team_news_availability_cap"):
        if c not in original.columns:
            raise ValueError(f"Missing genuine frozen MM output field: {c}")
    if len({args.p_start_col,args.xmins_col,args.q_sub_col,
            args.sub_minutes_col})!=4:
        raise ValueError("Raw MM probability/duration fields must be distinct")

    release_input=normalize_mm_release(
        original,season=args.season,model_version=args.model_version,
        p_start_col=args.p_start_col,xmins_col=args.xmins_col)
    news_path=Path(args.news_ledger)
    ledger=read_frame(news_path)
    # Validate independently for each player, not just a CLI-supplied GW string.
    news_check=validate_scoped_official_news(
        release_input,ledger,origin_gw=args.origin_gw)
    output=prepare_live_mm_release_candidate(
        release_input,
        p_start=release_input["p_start"].to_numpy(),
        q_sub=original[args.q_sub_col].to_numpy(),
        sub_minutes=original[args.sub_minutes_col].to_numpy(),
        origin_gw=args.origin_gw,news_scoped_gw=news_check["official_news_gw"])
    out=Path(args.out)
    manifest=write_mm_release(
        output,out,model_version=args.model_version,season=args.season)
    policy={
        "status":"verified_mm_release_only_not_complete_final_chain",
        "availability_policy":BOUNDARY_VERSION,
        "source_model_version":args.model_version,
        "season":args.season,
        "origin_gw":int(args.origin_gw),
        "frozen_mm_unchanged":True,
        "raw_input_sha256":sha256(Path(args.input)),
        "official_team_news_sha256":sha256(news_path),
        "published_mm_sha256":manifest.sha256_csv_gz,
        "hard_unavailable_player_fixture_rows":int(output.live_eligibility_applied.sum()),
        "raw_expected_minutes_removed":round(float(output.live_eligibility_minutes_removed.sum()),6),
        "source_news":news_check,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "full_final_chain_live_certified":False,
    }
    (out/"live_availability_policy.json").write_text(
        json.dumps(policy,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return manifest


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--model-version",required=True)
    ap.add_argument("--season",default="2025-26")
    ap.add_argument("--p-start-col",default="p_start")
    ap.add_argument("--xmins-col",default="xmins")
    ap.add_argument("--live-hard-availability",action="store_true",
                    help="Apply approved release boundary to verified original MM output")
    ap.add_argument("--origin-gw",type=int)
    ap.add_argument("--news-ledger",help="Captured official FPL Team News ledger CSV")
    ap.add_argument("--q-sub-col",default="mm_q_sub")
    ap.add_argument("--sub-minutes-col",default="mm_sub_minutes")
    args=ap.parse_args()
    manifest=export(args)
    print(json.dumps(manifest.__dict__,indent=2))


if __name__=="__main__":
    main()
