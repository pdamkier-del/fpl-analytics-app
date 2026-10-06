#!/usr/bin/env python3
"""Reproduce mapped CSV from frozen raw ratings and exact mappings, offline."""
import argparse,gzip,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.external_rating_ingest import map_rows
from fpl_v1_1_model.rating_history import validate_rating_ledger

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dir',default='data_v1_1/derived/mm_v2_ratings');ap.add_argument('--out');a=ap.parse_args()
    folder=ROOT/a.dir
    with gzip.open(folder/'exact_mapping_inputs.json.gz','rt') as f:j=json.load(f)
    dictset=lambda k:{tuple(r['key']):set(r['values']) for r in j[k]}
    raw=pd.read_csv(folder/'raw_provider_ratings.csv.gz',dtype={'provider_player_id':str,'provider_match_id':str,'provider_opta_id':str})
    mapped,audit=map_rows(raw,dictset('registry'),dictset('known_matches'),{},
        {r['key']:set(r['values']) for r in j['opta_ids']},dictset('names'),{tuple(r['key']):r['value'] for r in j['roles']})
    validate_rating_ledger(mapped)
    if a.out:mapped.to_csv(a.out,index=False,compression={'method':'gzip','mtime':0})
    existing=pd.read_csv(folder/'player_match_ratings.csv.gz',dtype={'provider_player_id':str,'provider_match_id':str,'provider_opta_id':str})
    pd.testing.assert_frame_equal(existing,mapped.reset_index(drop=True),check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-12)
    print(f'Offline rebuild matches {len(mapped)} mapped original ratings; {len(audit)} raw audit rows')
if __name__=='__main__':main()
