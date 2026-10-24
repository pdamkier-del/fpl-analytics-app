"""Read-only empirical check: reported FPL minutes are not a conserved game clock."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    with sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro',uri=True)as con:
        d=pd.read_sql_query("SELECT season,fixture_uuid,team_id,player_uuid,fpl_position,minutes,fpl_red_cards,source_name "
            "FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",con)
    if d.duplicated(['season','fixture_uuid','player_uuid']).any():raise ValueError('Duplicate actual player/fixture observations')
    keeper=d.fpl_position.isin(['GK','GKP'])
    d['field_minutes']=np.where(keeper,0,d.minutes)
    d['keeper_minutes']=np.where(keeper,d.minutes,0)
    d['missing_red']=d.fpl_red_cards.isna().astype(int)
    d['missing_minutes']=d.minutes.isna().astype(int)
    d['played']=d.minutes.gt(0).astype(int)
    g=d.groupby(['season','fixture_uuid','team_id']).agg(field=('field_minutes','sum'),
        keeper=('keeper_minutes','sum'),red=('fpl_red_cards','sum'),
        missing_red=('missing_red','sum'),missing_minutes=('missing_minutes','sum'),players=('played','sum'))
    selected=g[g.red.eq(0)&g.missing_red.eq(0)&g.missing_minutes.eq(0)]
    rows=[]
    for season,s in selected.groupby(level=0):
        rows.append(dict(season=season,team_fixtures=len(s),recorded_red_cards=0,
            missing_minute_or_red_labels=0,reported_outfield_median=float(s.field.median()),
            reported_outfield_mean=float(s.field.mean()),reported_outfield_min=float(s.field.min()),
            reported_outfield_max=float(s.field.max()),outfield_exactly_900=int(s.field.eq(900).sum()),
            goalkeeper_exactly_90=int(s.keeper.eq(90).sum()),goalkeeper_min=float(s.keeper.min()),
            goalkeeper_max=float(s.keeper.max()),most_common_outfield_totals={str(k):int(v)for k,v in s.field.value_counts().head(8).items()}))
    result=dict(scope='Observed FPL-label accounting only; not proof of a specific rounding transform or a complete legal physical timeline',
        core_sha256=hashlib.sha256(a.db.read_bytes()).hexdigest(),sources=sorted(d.source_name.unique()),
        physical_regulation_outfield_minutes=900,reported_FPL_sum_required_to_equal_900=False,
        removal_context='No recorded red card, with complete minute/red labels; unmodelled removals/other events are not ruled out',
        seasons=rows,production_changed=False)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
