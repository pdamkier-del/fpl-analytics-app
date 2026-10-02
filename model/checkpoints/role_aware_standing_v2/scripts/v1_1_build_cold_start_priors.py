#!/usr/bin/env python3
"""Build cutoff-safe cold-start role priors for newly registered players.

A new signing can be forecast before his first match for the new club.
The prior is based on information observed before registration/deadline:
  * recency-weighted roles/minutes at previous clubs;
  * recency-weighted previous start share;
  * optional transfer-context model coefficients fitted on historical transfers.

No fee/expectation heuristic is hard-coded. If no fitted coefficient file is
provided, transfer-context coefficients are zero and only football history is
used. Priors fade automatically once new-club role evidence arrives.
"""
from __future__ import annotations
import argparse, json, sqlite3, sys
from collections import defaultdict
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.pstart_v2 import (
    TransferContextCoefficients, transfer_context_hierarchy_prior,
)
from v1_1_build_role_hierarchy import ROLES, normalize_role


def decay_days(days: float, half_life_matches: float) -> float:
    return 2.0 ** (-(max(0.0,float(days))/7.0)/float(half_life_matches))


def load_coefficients(path: str|None) -> TransferContextCoefficients:
    if not path:
        return TransferContextCoefficients()
    d=json.loads(Path(path).read_text())
    allowed={f.name for f in TransferContextCoefficients.__dataclass_fields__.values()}
    return TransferContextCoefficients(**{k:float(v) for k,v in d.items() if k in allowed})


def latest_transfer_context(con, pid, tid, asof):
    try:
        q='''SELECT * FROM player_transfer_context_v2
             WHERE external_player_id=? AND team_external_id=? AND observed_at<=?
             ORDER BY observed_at DESC LIMIT 1'''
        d=pd.read_sql_query(q,con,params=[str(pid),str(tid),pd.Timestamp(asof).isoformat()])
    except Exception:
        return None
    return None if d.empty else d.iloc[0].to_dict()


def previous_history(con,pid,new_team,asof,limit=80):
    q='''SELECT m.kickoff_at,p.team_external_id,p.started,p.minutes,p.in_matchday_squad,p.role
         FROM club_matches_v2 m JOIN player_match_roles_v2 p USING(source_match_id)
         WHERE p.external_player_id=? AND m.kickoff_at<?
           AND (p.team_external_id IS NULL OR p.team_external_id<>?)
         ORDER BY m.kickoff_at DESC LIMIT ?'''
    try:
        return pd.read_sql_query(q,con,params=[str(pid),pd.Timestamp(asof).isoformat(),str(new_team),int(limit)])
    except Exception:
        return pd.DataFrame()


def build_prior(history, asof, role_half_life, start_half_life):
    role_mass=defaultdict(float); start_num=0.0; start_den=0.0; minutes_num=0.0; minutes_den=0.0
    if history.empty:
        return {},0.0,0.0,0.0
    asof=pd.Timestamp(asof)
    if asof.tzinfo is None: asof=asof.tz_localize('UTC')
    for r in history.itertuples(index=False):
        ko=pd.to_datetime(r.kickoff_at,utc=True,errors='coerce')
        if pd.isna(ko): continue
        days=max(0.0,(asof-ko).total_seconds()/86400.0)
        wr=decay_days(days,role_half_life); ws=decay_days(days,start_half_life)
        if r.in_matchday_squad == 0: # documented absence is not negative hierarchy evidence
            continue
        role=normalize_role(r.role)
        mins=max(0.0,float(r.minutes or 0.0))
        if role in ROLES and mins>0:
            role_mass[role]+=wr*min(1.35,mins/90.0)
        start_num += ws*float(int(r.started or 0)==1)
        start_den += ws
        minutes_num += ws*min(1.0,mins/90.0)
        minutes_den += ws
    total=sum(role_mass.values())
    q={r:(role_mass[r]/total if total>0 else 0.0) for r in ROLES}
    return q,(start_num/start_den if start_den>0 else 0.0),(minutes_num/minutes_den if minutes_den>0 else 0.0),start_den


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--coefficients-json',default=None,
                    help='Historically fitted TransferContextCoefficients JSON. Omit = transfer features have zero coefficient.')
    ap.add_argument('--prior-equivalent-matches',type=float,default=4.0,
                    help='Empirical-Bayes prior strength; select by historical transfer CV.')
    ap.add_argument('--role-half-life',type=float,default=20.0)
    ap.add_argument('--start-half-life',type=float,default=20.0)
    ap.add_argument('--min-role-share',type=float,default=0.03)
    ap.add_argument('--out',default='data_v1_1/features/cold_start_role_priors.csv')
    a=ap.parse_args()
    con=sqlite3.connect(a.db)
    coeff=load_coefficients(a.coefficients_json)
    regs=pd.read_sql_query('SELECT * FROM player_registration_v2 ORDER BY observed_at',con)
    if regs.empty:
        print('no player_registration_v2 rows'); return
    regs['observed_at']=pd.to_datetime(regs['observed_at'],utc=True,errors='coerce')
    regs=regs[regs.observed_at.notna()].copy()
    rows=[]
    for reg in regs.itertuples(index=False):
        if str(reg.registration_status).lower() in {'deregistered','left','loaned_out','inactive'}: continue
        pid=str(reg.external_player_id); tid=str(reg.team_external_id); t=reg.observed_at
        hist=previous_history(con,pid,tid,t)
        q,start_share,minutes_share,evidence=build_prior(hist,t,a.role_half_life,a.start_half_life)
        ctx=latest_transfer_context(con,pid,tid,t) or {}
        # Transfer-context model is optional and learned. With all-zero coefficients,
        # use previous start share as the hierarchy prior rather than sigmoid(0)=0.5.
        has_transfer_model=any(abs(float(getattr(coeff,f)))>1e-12 for f in coeff.__dataclass_fields__)
        if has_transfer_model:
            h=transfer_context_hierarchy_prior(
                previous_start_share=float(ctx.get('previous_start_share') or start_share),
                previous_minutes_share=float(ctx.get('previous_minutes_share') or minutes_share),
                fee_percentile_within_club=float(ctx.get('fee_percentile_within_club') or 0.0),
                expectation_signal=float(ctx.get('expectation_signal') or 0.0),
                age=(None if ctx.get('age') is None else float(ctx.get('age'))),
                coefficients=coeff)
        else:
            h=min(0.995,max(0.0,start_share))
        for role,qv in q.items():
            if qv < a.min_role_share: continue
            rows.append({'external_player_id':pid,'team_external_id':tid,'role':role,
                         'observed_at':t.isoformat(),'q_prior':qv,'hierarchy_prior':h,
                         'prior_equivalent_matches':float(a.prior_equivalent_matches),
                         'previous_start_share':start_share,'previous_minutes_share':minutes_share,
                         'previous_role_evidence':evidence,
                         'transfer_fee_eur':ctx.get('transfer_fee_eur'),
                         'fee_percentile_within_club':ctx.get('fee_percentile_within_club'),
                         'expectation_signal':ctx.get('expectation_signal'),
                         'source_name':'cold_start_history+transfer_model' if has_transfer_model else 'cold_start_history'})
    out=pd.DataFrame(rows)
    op=Path(a.out); op.parent.mkdir(parents=True,exist_ok=True); out.to_csv(op,index=False)
    if not out.empty:
        dbrows=out[['external_player_id','team_external_id','role','observed_at','q_prior','hierarchy_prior','prior_equivalent_matches','source_name']]
        dbrows.to_sql('player_cold_start_role_prior_v2',con,if_exists='append',index=False)
        con.commit()
    print('wrote',op,'rows',len(out),'players',out.external_player_id.nunique() if not out.empty else 0)

if __name__=='__main__': main()
