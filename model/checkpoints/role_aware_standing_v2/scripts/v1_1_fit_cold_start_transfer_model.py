#!/usr/bin/env python3
"""Fit transfer-context coefficients from historical new-signing outcomes.

Each registration is evaluated on the player's first N known matchday-squad
opportunities for the new club. Features must have been observed at/before the
registration timestamp.  The target is actual started (0/1) per opportunity.
This keeps fee/expectation effects empirical rather than hand-coded.
"""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss

FEATURES=['previous_start_share','previous_minutes_share','fee_percentile_within_club','expectation_signal','age_centered']


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--first-n-opportunities',type=int,default=8)
    ap.add_argument('--min-transfers',type=int,default=30)
    ap.add_argument('--out-json',default='outputs/v1_1/pstart_v2/cold_start_transfer_coefficients.json')
    ap.add_argument('--audit-csv',default='outputs/v1_1/pstart_v2/cold_start_transfer_training_rows.csv')
    a=ap.parse_args(); con=sqlite3.connect(a.db)
    try:
        regs=pd.read_sql_query('SELECT * FROM player_registration_v2 ORDER BY observed_at',con)
        ctx=pd.read_sql_query('SELECT * FROM player_transfer_context_v2 ORDER BY observed_at',con)
    except Exception as e:
        raise SystemExit(f'missing cold-start tables: {e}')
    if regs.empty or ctx.empty: raise SystemExit('need historical registration + transfer context rows')
    regs['observed_at']=pd.to_datetime(regs.observed_at,utc=True,errors='coerce')
    ctx['observed_at']=pd.to_datetime(ctx.observed_at,utc=True,errors='coerce')
    rows=[]
    for reg in regs.itertuples(index=False):
        if pd.isna(reg.observed_at) or str(reg.registration_status).lower() in {'deregistered','left','loaned_out','inactive'}:continue
        c=ctx[(ctx.external_player_id.astype(str)==str(reg.external_player_id)) &
              (ctx.team_external_id.astype(str)==str(reg.team_external_id)) &
              (ctx.observed_at<=reg.observed_at)].sort_values('observed_at').tail(1)
        if c.empty: continue
        c=c.iloc[0]
        opp=pd.read_sql_query('''SELECT m.kickoff_at,p.started,p.minutes,p.in_matchday_squad
            FROM club_matches_v2 m JOIN player_match_roles_v2 p USING(source_match_id)
            WHERE p.external_player_id=? AND p.team_external_id=? AND m.kickoff_at>=?
            ORDER BY m.kickoff_at LIMIT ?''',con,
            params=[str(reg.external_player_id),str(reg.team_external_id),reg.observed_at.isoformat(),int(a.first_n_opportunities*3)])
        opp=opp[opp.in_matchday_squad.fillna(1).astype(float)>0].head(a.first_n_opportunities)
        for o in opp.itertuples(index=False):
            rows.append({'external_player_id':str(reg.external_player_id),'team_external_id':str(reg.team_external_id),
                'registration_at':reg.observed_at.isoformat(),'started':int(o.started or 0),
                'previous_start_share':float(c.previous_start_share or 0),
                'previous_minutes_share':float(c.previous_minutes_share or 0),
                'fee_percentile_within_club':float(c.fee_percentile_within_club or 0),
                'expectation_signal':float(c.expectation_signal or 0),
                'age_centered':(float(c.age)-25.0) if pd.notna(c.age) else 0.0})
    d=pd.DataFrame(rows)
    if d.empty or d.external_player_id.nunique()<a.min_transfers:
        raise SystemExit(f'not enough historical transfers: players={0 if d.empty else d.external_player_id.nunique()}')
    # Split by player so one signing cannot appear in both train and validation.
    players=sorted(d.external_player_id.unique()); cut=max(1,int(.8*len(players)))
    tr=set(players[:cut]); train=d[d.external_player_id.isin(tr)]; val=d[~d.external_player_id.isin(tr)]
    X=train[FEATURES].to_numpy(float); y=train.started.to_numpy(int)
    model=LogisticRegression(C=1.0,max_iter=3000).fit(X,y)
    out={'intercept':float(model.intercept_[0])}
    out.update({k:float(v) for k,v in zip(FEATURES,model.coef_[0])})
    # Dataclass key uses age_centered; all others match.
    p=Path(a.out_json); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,indent=2))
    apath=Path(a.audit_csv); apath.parent.mkdir(parents=True,exist_ok=True); d.to_csv(apath,index=False)
    if not val.empty:
        pv=model.predict_proba(val[FEATURES].to_numpy(float))[:,1]
        metrics={'n_train':len(train),'n_val':len(val),'n_transfers':len(players),
                 'val_brier':float(brier_score_loss(val.started,pv)),
                 'val_log_loss':float(log_loss(val.started,pv,labels=[0,1]))}
    else: metrics={'n_train':len(train),'n_val':0,'n_transfers':len(players)}
    p.with_suffix('.metrics.json').write_text(json.dumps(metrics,indent=2))
    print(json.dumps({'coefficients':out,'metrics':metrics},indent=2))

if __name__=='__main__':main()
