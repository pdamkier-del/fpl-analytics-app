#!/usr/bin/env python3
"""Verified current action/role supplement, not a new historical fitted input."""
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.experimental_player_pm import posterior


def action_profile(ledger,identity,pid,cut,half=365.,strength=20.):
    h=ledger.copy();h['known']=pd.to_datetime(h.available_at,utc=True);h=h[h.known<cut].merge(identity[['player_uuid','pos']],on='player_uuid',validate='many_to_one')
    if pid not in set(identity.player_uuid):raise ValueError('Unknown canonical player')
    role=identity.set_index('player_uuid').loc[pid,'pos'];h=h[h.minutes_played.gt(0)].copy();h['w']=np.exp2(-(cut-h.known).dt.total_seconds()/86400/half)
    out={}
    for field in ['keypass_rate90','dribble_rate90','sot_rate90','cbi_rate90','recovery_rate90','tackle_rate90','cross_rate90','foulwon_rate90']:
        v=h[h[field].notna() & h[field].ge(0)];pop=v[v.pos.eq(role)];g=v[v.player_uuid.eq(pid)]
        if not len(pop) or not len(g):out[field]=None;continue
        e=g.minutes_played*g.w/90;pe=pop.minutes_played*pop.w/90
        prior=float((pop[field]*pe).sum()/pe.sum());out[field]=dict(**posterior(float((g[field]*e).sum()),float(e.sum()),prior,strength),observations=len(g),latest_known=str(g.known.max()),source='checksum-verified BPS action ledger; publication proxy',used_in_candidate=False)
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='analysis/results/player-pm-v2-20261015');a=ap.parse_args();base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    f=pd.read_csv(base/'performance_feature_matrix.csv.gz',low_memory=False);cut=pd.to_datetime(f.cutoff,utc=True).min();f=f[f.target_gw.eq(f.target_gw.min())].drop_duplicates('player_uuid');identity=f[['player_uuid','pos']]
    ledger=pd.read_csv(base/'verified_bps_action_ledger.csv.gz');profiles=[]
    for r in f[f.fpl_element.isin([411,12,165,154])].itertuples():
        known=pd.Timestamp(r.max_history_known_at) if pd.notna(r.max_history_known_at) else None
        if known is not None and known>=cut:raise ValueError('Future tactical history')
        row=f[f.player_uuid.eq(r.player_uuid)].iloc[0];roles={c[2:-5]:float(row[c]) for c in f if c.startswith('q_') and c.endswith('_fast')}
        profiles.append(dict(player=r.player,player_uuid=r.player_uuid,element=int(r.fpl_element),expected_role=r.expected_role,soft_role_probabilities=roles,max_role_history_known_at=str(known),role_certification='Inherited diagnostic mapping, not newly source-certified',actions=action_profile(ledger,identity,r.player_uuid,cut)))
    out=dict(classification='VERIFIED_CURRENT_ACTION_PROFILES_NOT_HISTORICAL_PM_ABLATION',cutoff=str(cut),ledger_rows=len(ledger),profiles=profiles,source_manifest='model/checkpoints/current-diagnostic.json',limitations=['Only verified ledger rows are used; quarantined/missing rows are not zero-filled','Current action/soft-role profiles are descriptive supplements, not additional inputs in the controlled historical PM v2 matrix','No inferred pair chemistry or unobserved set-piece order','Actual source-publication times remain uncertified'],locked_model_active=False)
    p=Path(a.out)/'verified_current_action_profiles.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'players':[p['player'] for p in profiles],'ledger_rows':len(ledger),'saved':str(p)}))
if __name__=='__main__':main()
