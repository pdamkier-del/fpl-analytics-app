#!/usr/bin/env python3
"""Check actual one-match/one-GW/six-GW outputs and source timestamps."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    b=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    f=pd.read_csv(b/'vfinal_live_full_simulator_input.csv.gz',low_memory=False);p=pd.read_csv(b/'live_vfinal_fixture_xp.csv.gz');cut=pd.to_datetime(f.cutoff,utc=True)
    a={'source_cutoff':str(cut.iloc[0]),'target_outcome_rows':int(f[['actual_start','actual_minutes']].notna().any(axis=1).sum()),'fields':{},'team_news_source_cutoff_semantics':'GW deadline scope, not observed_at; source availability uses effective_at and roster_observed_at.'}
    if a['target_outcome_rows']:raise ValueError('Future target outcomes used')
    for c in ['max_history_known_at','history_latest_available_at','team_news_effective_at','roster_observed_at','evidence_at']:
        t=pd.to_datetime(f[c],utc=True,errors='coerce');a['fields'][c]={'known':int(t.notna().sum()),'post_forecast_cutoff':int((t>cut).sum())}
        if (t>cut).any():raise ValueError('Postcutoff '+c)
    a['exact_11_max_error']=float((f.groupby(['fixture_uuid','team_id']).control_p_start.sum()-11).abs().max())
    if a['exact_11_max_error']>1e-6:raise ValueError('Expected XI mass is not eleven')
    a['hard_unavailable_rows']=int(f.live_eligibility_applied.sum())
    hard=f.loc[f.live_eligibility_applied.fillna(False),['fixture_uuid','player_uuid']].merge(p,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    if hard.xpts_fixture.ne(0).any() or hard.expected_minutes.ne(0).any():raise ValueError('Hard unavailable simulated points/minutes')
    for name in ['one_match_xp.csv.gz','one_gw_xp.csv.gz']:
        q=pd.read_csv(b/name);j=q.merge(p,on=['fixture_uuid','player_uuid'],suffixes=('_subset','_full'),validate='one_to_one')
        a[name]={'rows':len(q),'same_as_six_gw':bool(len(j)==len(q) and np.array_equal(j.xpts_fixture_subset,j.xpts_fixture_full))}
        if not a[name]['same_as_six_gw']:raise ValueError('Subset seed parity failed')
    out=ROOT/'work/live-final-model/live_release_component_audit.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(a,indent=2)+'\n');print(json.dumps(a))
if __name__=='__main__':main()
