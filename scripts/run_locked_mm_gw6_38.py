#!/usr/bin/env python3
"""Locked Team-News MM walk-forward from GW6 through GW38.

Uses exactly the frozen MM architecture/policy. The only purpose of this runner
is to allow a source feature table that includes GW1-5 so those GWs can serve
as history/training before the first normal forecast at GW6.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))

from fpl_v1_1_model.rating_history import build_rating_features
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,build_strict_team_news_features
from run_v4_performance_rating_experiment import build_perf_ledger,add_features as add_perf_features
from run_v4_three_state_sequence_experiment import add_sequence_features
from run_mm_v2_team_news_availability_experiment import evaluate_news_variant

POLICY='soft_0.5_0.1'
RATINGS=ROOT/'data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz'
TEAM_NEWS=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    frame=add_sequence_features(pd.read_csv(a.source).reset_index(drop=True))
    frame=add_perf_features(frame,build_perf_ledger())
    frame=build_rating_features(frame,pd.read_csv(RATINGS))
    strict=read_split_gzip_jsonl(TEAM_NEWS,'predeadline_strict.jsonl.gz')
    frame=build_strict_team_news_features(frame,strict)
    known=pd.to_datetime(frame.outcome_known_at,utc=True)

    rows=[];audit=[]
    for gw in range(6,39):
        val=frame.gw.eq(gw).to_numpy()
        if not val.any(): raise ValueError(f'missing GW{gw} target rows')
        cut=pd.to_datetime(frame.loc[val,'cutoff'],utc=True).min()
        train=((frame.gw<gw)&(known<cut)).to_numpy()
        train_gws=sorted(int(x) for x in frame.loc[train,'gw'].unique())
        if not train_gws: raise ValueError(f'GW{gw}: no prior training history')
        feat,p_locked,x_locked,p_pre,p_news,x_news,q,sub,met=evaluate_news_variant(
            frame,train,val,POLICY)
        part=feat.loc[val,[
            'fixture_uuid','player_uuid','team_id','gw','team','player','pos','cutoff',
            'outcome_known_at','start_minutes_mean','cameo_minutes_mean',
            'p_cameo_given_bench','y','minutes'
        ]].copy()
        qv=np.asarray(q)[val]; subv=np.asarray(sub)[val]
        part['new_p_start']=np.asarray(p_news)[val]
        part['new_xmins']=np.asarray(x_news)[val]
        part['new_q_sub']=qv
        part['new_sub_minutes']=subv
        # starter duration is unchanged by the locked MM.
        part['new_start_minutes']=part.start_minutes_mean.astype(float)
        rows.append(part)
        audit.append(dict(gw=gw,cutoff=str(cut),train_gws=train_gws,
                          train_rows=int(train.sum()),target_rows=int(val.sum()),
                          state_log_loss=float(met['state_log_loss']),
                          xmins_rmse=float(met['xmins_rmse'])))
        print(f'GW{gw}: train {train_gws[0]}-{train_gws[-1]} rows={train.sum()} target={val.sum()}',flush=True)
    pred=pd.concat(rows,ignore_index=True)
    pred.to_csv(out/'locked_mm_predictions.csv.gz',index=False,compression='gzip')
    pd.DataFrame(audit).to_csv(out/'walkforward_audit.csv',index=False)
    summary={
      'classification':'retrospective fixed-architecture locked MM walk-forward',
      'policy':POLICY,'forecast_gws':[6,38],
      'first_forecast_training_gws':audit[0]['train_gws'],
      'rows':int(len(pred)),
      'note':'Architecture/hyperparameters are final locked choices; state and labels for each forecast use only rows known before that GW cutoff.'
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
