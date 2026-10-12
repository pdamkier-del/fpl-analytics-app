#!/usr/bin/env python3
"""Read-only verification of prior tactical bench evidence from 2025/26
confirmed Premier League lineup sheets.

An unused bench player is CONFIRMED only if: provider confirmed match lineup,
non-starter player has FPL ID, that ID is unambiguously anchored to player_uuid
through earlier unique starter surname+match identities, and official previous
GW says zero minutes. Otherwise classify as unknown, not tactical.
Postmatch bench evidence is used ONLY to classify a PREVIOUS GW for later
historical forecasts; it cannot be applied to current target match.
"""
from __future__ import annotations
import json,sys,unicodedata,re
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
CLASS=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
P=ROOT/'analysis/results/mm-unified-official-roles-20261006-v1/reused_diagnostic_predictions.csv.gz'
H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
OUT=ROOT/'work/live-final-model/mm_verified_bench_evidence.json'

def surname(x):
    s=unicodedata.normalize('NFKD',str(x).lower())
    s=''.join(c for c in s if not unicodedata.combining(c))
    tokens=re.findall(r'[a-z]+',s)
    return tokens[-1] if tokens else ''

def main():
    cl=pd.read_csv(CLASS,low_memory=False)
    required={'match_id','fixture_uuid','player_uuid','player'}
    if not required.issubset(cl):
        raise ValueError('Classification missing stable starter-identity anchor: '+str(set(cl.columns)))
    cl=cl[cl.match_id.astype(str).str.contains('-prem-')].drop_duplicates(['match_id','player_uuid'])
    cl['surname']=cl.player.map(surname)
    # Uniquely map verified fixture UUIDs to premier-league match IDs.
    fx=cl[['match_id','fixture_uuid']].drop_duplicates()
    if fx.duplicated('fixture_uuid').any() or fx.duplicated('match_id').any():raise ValueError('Ambiguous Premier League fixture mapping')
    line=[]
    for folder in sorted(RAW.glob('GW*')):
        z=pd.read_csv(folder/'lineups.csv',low_memory=False)
        z=z[z.match_id.astype(str).str.contains('-prem-')&z.lineup_status.astype(str).str.lower().eq('confirmed')].copy()
        if len(z):line.append(z)
    lu=pd.concat(line,ignore_index=True).drop_duplicates(['match_id','team_side','player_name','is_starting'])
    lu['surname']=lu.player_name.map(surname)
    lu['player_id']=pd.to_numeric(lu.player_id,errors='coerce')
    starts=lu[(lu.is_starting.astype(str).str.lower().isin(['true','1']))&lu.player_id.notna()].copy()
    # Unique surname ON BOTH sides within a match, no cross-team fuzzy remap.
    cunique=cl[~cl.duplicated(['match_id','surname'],keep=False)]
    lunique=starts[~starts.duplicated(['match_id','surname'],keep=False)]
    anchors=lunique.merge(cunique[['match_id','surname','player_uuid']],
                       on=['match_id','surname'],validate='one_to_one')
    anchors['player_id']=anchors.player_id.astype(int)
    # Only FPL ID -> one and only one UUID across all anchors.
    pairs=anchors[['player_id','player_uuid']].drop_duplicates()
    pairs=pairs[~pairs.duplicated('player_id',keep=False)]
    pairs=pairs[~pairs.duplicated('player_uuid',keep=False)]
    to_uuid=dict(zip(pairs.player_id,pairs.player_uuid))
    bench=lu[~lu.is_starting.astype(str).str.lower().isin(['true','1'])].copy()
    bench=bench[bench.player_id.notna()]
    bench['player_id']=bench.player_id.astype(int)
    bench['player_uuid']=bench.player_id.map(to_uuid)
    bench=bench[bench.player_uuid.notna()].copy()
    bench=bench.merge(fx,on='match_id',validate='many_to_one',how='inner')
    bench=bench[['fixture_uuid','player_uuid']].drop_duplicates()
    # Official 2025/26 recorded results, restricted to 2025/26 and same fixture.
    hh=pd.read_csv(H,usecols=['fixture_uuid','player_uuid','gw','minutes','y'],low_memory=False)
    hh['minutes']=pd.to_numeric(hh.minutes,errors='raise')
    hh['gw']=hh.gw.astype(int)
    covered=hh[['fixture_uuid','player_uuid','gw','minutes']].copy()
    bench=bench.merge(covered,on=['fixture_uuid','player_uuid'],validate='one_to_one',how='left')
    # If neither fixture nor player observation matches, cannot certify bench.
    evidence=bench[bench.minutes.eq(0)].copy()
    classified=hh.groupby(['player_uuid','gw']).size()
    ambiguous=set(classified[classified>1].index)
    bench_keys=set((str(v.player_uuid),int(v.gw)) for v in evidence.itertuples()
                   if pd.notna(v.gw) and (str(v.player_uuid),int(v.gw)) not in ambiguous)
    pred=pd.read_csv(P,low_memory=False)
    pred['gw']=pred.gw.astype(int)
    info=[]
    for v in pred.itertuples(index=False):
        pid=str(v.player_uuid);gw=int(v.gw)
        previous=(pid,gw-2)
        if previous in bench_keys:
            info.append(dict(gw=gw,team=str(v.team),player=str(v.player),
                prior_bench_gw=gw-2, prior_bench_verification='CONFIRMED_UNUSED_BENCH',
                actual_start=int(v.y),actual_minutes=float(v.minutes),forecast_pstart=float(v.mm_p_start)))
    out=dict(classification='RETROSPECTIVE_CONFIRMED_UNUSED_BENCH_PRIOR_GW_EVIDENCE_READ_ONLY',
        raw_confirmed_pl_lineup_rows=len(lu),raw_confirmed_pl_bench_id_rows=int(len(lu[(~lu.is_starting.astype(str).str.lower().isin(['true','1'])) &lu.player_id.notna()])),
        mapped_id_uuid_pairs=len(to_uuid),unambiguous_starter_name_anchors=len(anchors),
        mapped_bench_player_fixtures=len(bench),
        confirmed_unused_bench_fixture_players=len(evidence),
        confirmed_unused_prior_gw_cases_in_2025_scored_forecasts=len(info),
        examples=info[:25],caution='No unused-bench proof for all other AVAILABLE zero minute observations; do not infer tactical nonselection',
        historical_source_only=True,app_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('MM_BENCH_EVIDENCE',json.dumps({k:v for k,v in out.items() if k!='examples'},ensure_ascii=False))
    print('MM_BENCH_EXAMPLES',json.dumps(out['examples'],ensure_ascii=False))
if __name__=='__main__':main()
