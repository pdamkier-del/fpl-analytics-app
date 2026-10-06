#!/usr/bin/env python3
"""Export any finalized MM forecast table to the stable mm-release-v1 contract."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fpl_v1_1_model.mm_release import write_mm_release

def read_frame(path:Path):
    if path.suffix==".parquet": return pd.read_parquet(path)
    return pd.read_csv(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--model-version",required=True)
    ap.add_argument("--season",default="2025-26")
    ap.add_argument("--p-start-col",default="p_start")
    ap.add_argument("--xmins-col",default="xmins")
    args=ap.parse_args()
    m=write_mm_release(
        read_frame(Path(args.input)),Path(args.out),
        model_version=args.model_version,season=args.season,
        p_start_col=args.p_start_col,xmins_col=args.xmins_col)
    print(json.dumps(m.__dict__,indent=2))

if __name__=="__main__":
    main()
