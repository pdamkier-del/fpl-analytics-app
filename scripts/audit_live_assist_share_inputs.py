#!/usr/bin/env python3
"""Read-only current PM goal/assist allocation diagnostic, common source cutoff."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
ph=pd.read_csv(B/'player_fixture_observations.csv.gz',low_memory=False)
f=pd.read_csv(B/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
cut=pd.to_datetime(f.cutoff,utc=True,errors='raise')
assert cut.nunique()==1
ph['available_at']=pd.to_datetime(ph.available_at,utc=True,errors='raise')
ph=ph[ph.available_at<cut.iloc[0]].copy()
assert f.target_gw.nunique()==6 and ph.fixture_uuid.nunique()>=40
assert (ph[['xg','xa','goals','fpl_assists']].apply(pd.to_numeric,errors='coerce').notna()).all().all()
group=ph.groupby(['fixture_uuid','team_id'])
hist=group.agg(xg=('xg','sum'),xa=('xa','sum'),goals=('goals','sum'),fpl_assists=('fpl_assists','sum')).reset_index()
totals=hist[['xg','xa','goals','fpl_assists']].sum().to_dict()
totals={k:round(float(v),4) for k,v in totals.items()}
totals['xA_div_xG']=round(totals['xa']/totals['xg'],4)
totals['FPL_assists_div_goals']=round(totals['fpl_assists']/totals['goals'],4)
ref=f.groupby(['fixture_uuid','team_id'],as_index=False).agg(
    goal_mu=('goal_mu','sum'),assist_mu=('assist_mu','sum'),
    apg=('assist_probability_per_goal','first'))
ref['inferred_apg']=ref.assist_mu/ref.goal_mu
assert np.allclose(ref.inferred_apg,ref.apg,rtol=0,atol=1e-8)
current_apg=ref[['apg']].describe(percentiles=[.1,.5,.9]).round(5).to_dict()['apg']
sun=hist[hist.team_id.eq(20)]
le=ph[ph.fpl_element.eq(542)]
assert len(le)==5 and sun.fixture_uuid.nunique()==5
st=sun[['xg','xa','goals','fpl_assists']].sum()
l=le[['xg','xa','goals','fpl_assists']].sum()
sund=dict(team={k:round(float(v),4) for k,v in st.items()},
          lefee={k:round(float(v),4) for k,v in l.items()},
          lefee_xg_share=round(float(l.xg/st.xg),5),
          lefee_xa_share=round(float(l.xa/st.xa),5))
future=f[f.fpl_element.eq(542)].sort_values('target_gw')
rows=[]
for r in future.itertuples(index=False):
    team=f[(f.fixture_uuid==r.fixture_uuid)&(f.team_id==20)]
    rows.append(dict(gw=int(r.target_gw),goal_mu=round(float(r.goal_mu),5),assist_mu=round(float(r.assist_mu),5),
                     goal_share=round(float(r.goal_mu/team.goal_mu.sum()),5),
                     assist_share=round(float(r.assist_mu/team.assist_mu.sum()),5),
                     team_expected_goals=round(float(team.goal_mu.sum()),5),
                     team_expected_assists=round(float(team.assist_mu.sum()),5)))
report=dict(classification='READ_ONLY_LIVE_ALLOCATION_SOURCE_AUDIT_NOT_MODEL_UPDATE',
            sample={'team_fixture_sides':len(hist),'player_fixture_rows':len(ph)},
            source_totals=totals,model_assist_probability_per_goal=current_apg,
            sunderland=sund,lefee_upcoming=rows,
            warning='Actual FPL assists per goal is short-season, not prospective estimator; xA is not directly FPL assists',
            promotion_allowed=False)
out=ROOT/'work/live-final-model/live_assist_share_audit.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
for k in ['source_totals','model_assist_probability_per_goal','sunderland','lefee_upcoming']:
    print('ALLOCATION_AUDIT_'+k.upper(),json.dumps(report[k],ensure_ascii=False))
