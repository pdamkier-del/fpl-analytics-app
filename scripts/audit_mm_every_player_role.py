#!/usr/bin/env python3
"""Full MM role audit: every team, every player, name + modeled roles.

Uses the same cutoff-safe role features already present in the MM feature table.
This is an audit/report only: no MM/PM/TS parameters are changed.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from fpl_v1_1_model.role_classifier import ROLES
from run_mm_unified_official_roles import SOURCE

OUT=ROOT/'analysis/results/mm-role-player-audit-20261006-v1'

def fnum(x,d=3):
    try:
        z=float(x)
        return round(z,d) if np.isfinite(z) else None
    except Exception:return None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(SOURCE)
    if 'player_uuid' not in df or 'team' not in df or 'player' not in df:
        raise RuntimeError('SOURCE missing player identity columns')

    # Use the player's latest available cutoff row as the current audited state
    # inside the historical MM benchmark. If duplicate latest rows exist, take
    # the last deterministic fixture/player row.
    sort_cols=[c for c in ['cutoff','gw','fixture_uuid','player_uuid'] if c in df.columns]
    if sort_cols:
        if 'cutoff' in df: df['cutoff']=pd.to_datetime(df.cutoff,utc=True,errors='coerce')
        df=df.sort_values(sort_cols)
    latest=df.dropna(subset=['player_uuid','team','player']).groupby(
        ['team','player_uuid'],as_index=False,sort=True).tail(1).copy()

    rows=[]
    for r in latest.itertuples(index=False):
        q=[];h=[]
        rd=r._asdict()
        for role in ROLES:
            qv=fnum(rd.get(f'q_{role}_slow',0.0),4) or 0.0
            hv=fnum(rd.get(f'H_{role}_slow',0.0),4) or 0.0
            q.append((role,qv));h.append((role,hv))
        q.sort(key=lambda x:(x[1],x[0]),reverse=True)
        hmap=dict(h)
        primary=q[0][0] if q and q[0][1]>0 else str(rd.get('expected_role') or 'UNKNOWN')
        primary_q=q[0][1] if q else 0.0
        modeled=str(rd.get('expected_role') or '').strip()
        if modeled and modeled.upper()!='NAN' and modeled!='UNKNOWN':
            primary=modeled
            primary_q=dict(q).get(primary,primary_q)
        secondary=[(role,val) for role,val in q if role!=primary and val>=.10]
        realistic=[(role,val) for role,val in q if val>=.05]
        flags=[]
        if primary in ('','UNKNOWN','nan','NaN') or primary_q<=0: flags.append('UNKNOWN_ROLE')
        if primary_q<.40: flags.append('LOW_PRIMARY_Q')
        if len([1 for _,v in q if v>=.20])>=2: flags.append('MULTI_ROLE')
        if sum(v for _,v in q)<.50: flags.append('LOW_ROLE_EVIDENCE')
        rows.append({
            'team':str(rd.get('team')),
            'player':str(rd.get('player')),
            'player_uuid':str(rd.get('player_uuid')),
            'fpl_pos':str(rd.get('pos','')),
            'primary_role':primary,
            'primary_q':primary_q,
            'primary_H':fnum(hmap.get(primary,0.0),4),
            'secondary_roles':'; '.join(f'{a}:{b:.2f}' for a,b in secondary),
            'all_realistic_roles':'; '.join(f'{a}:{b:.2f}' for a,b in realistic),
            'role_count_q20':sum(v>=.20 for _,v in q),
            'gw_latest':rd.get('gw'),
            'pstart_input':fnum(rd.get('p_start',rd.get('base_p_start',np.nan)),4),
            'flags':'|'.join(flags) if flags else 'OK',
        })
    out=pd.DataFrame(rows).sort_values(['team','fpl_pos','primary_role','player'])
    out.to_csv(OUT/'all_players_by_team.csv',index=False)

    # Human-readable per-team list.
    md=['# MM role audit — every team and player','',
        'Primary role is taken from the latest cutoff-safe role state in the MM benchmark.',
        'Secondary roles are shown when q >= 0.10. This report changes no model parameters.','']
    for team,g in out.groupby('team',sort=True):
        md += [f'## {team}', '', '| Player | FPL | Primary role | q | H | Other roles | Flag |',
               '|---|---:|---|---:|---:|---|---|']
        for r in g.itertuples(index=False):
            md.append(f'| {r.player} | {r.fpl_pos} | {r.primary_role} | {r.primary_q:.2f} | '
                      f'{(r.primary_H if r.primary_H is not None else 0):.2f} | '
                      f'{r.secondary_roles or "—"} | {r.flags} |')
        md.append('')
    (OUT/'all_players_by_team.md').write_text('\n'.join(md)+'\n',encoding='utf-8')

    summary={
        'teams':int(out.team.nunique()),
        'players':int(len(out)),
        'unknown_role':int(out['flags'].str.contains('UNKNOWN_ROLE').sum()),
        'low_primary_q':int(out['flags'].str.contains('LOW_PRIMARY_Q').sum()),
        'multi_role':int(out['flags'].str.contains('MULTI_ROLE').sum()),
        'low_role_evidence':int(out['flags'].str.contains('LOW_ROLE_EVIDENCE').sum()),
        'players_per_team':out.groupby('team').size().to_dict(),
        'primary_role_counts':out.primary_role.value_counts().to_dict(),
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
