#!/usr/bin/env python3
"""Check the live feature implementation against frozen PR9 NUM values.

Two complete final historical origins, exact same prior observations/news. This
is a feature regression, not new forecast-accuracy or independent validation.
"""
import json,sqlite3,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from current_b_features import prior_features,KEY
from individual_mm_evidence import load_frame
from research_individual_mm_refinement import NUM
ROOT=Path(__file__).resolve().parents[1]

def run():
    source=load_frame(ROOT/'work/mm-integration-source/results/predictions.npz')
    base=source[source['mode'].eq('role_chance_return_duration')].copy()
    roles=source[source['mode'].eq('role')][KEY+['p']].rename(columns={'p':'p_role'})
    base=base.merge(roles,on=KEY,validate='one_to_one')
    with sqlite3.connect(ROOT/'work/core.sqlite3') as db:
        core=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,kickoff_at,started,minutes FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
    core['kickoff_at']=pd.to_datetime(core.kickoff_at,utc=True,format='mixed')
    core['known_at']=core.kickoff_at+pd.to_timedelta(np.where(core.season.eq('2024-25'),4,3),unit='h')
    core=core.merge(base[KEY+['news_eligible','news_state']],on=KEY,how='left',validate='one_to_one')
    conflict=core.news_eligible.eq(True)&core.news_state.isin(['OUT','SUSPENDED'])&(core.started.eq(1)|core.minutes.gt(0))
    core['role_available']=((core.news_eligible.eq(True)&core.news_state.isin(['AVAILABLE','RETURNED_AVAILABLE']))|core.started.eq(1)|core.minutes.gt(0))&~conflict
    reference=pd.read_csv(ROOT/'analysis/results/individual-mm-refinement-20261016/prior_only_features.csv.gz',float_precision='round_trip')
    reports=[]
    for season in ['2024-25','2025-26']:
        cut=pd.to_datetime(base.loc[base.season.eq(season),'cutoff'],utc=True,format='mixed').max()
        target=base[base.season.eq(season)&pd.to_datetime(base.cutoff,utc=True,format='mixed').eq(cut)].drop(columns=['y','minutes'],errors='ignore')
        actual=prior_features(target,core[core.known_at.lt(cut)],base)
        paired=actual[KEY+NUM].merge(reference[KEY+NUM],on=KEY,suffixes=('_new','_frozen'),validate='one_to_one')
        errors={}
        for column in NUM:
            a,b=paired[column+'_new'].to_numpy(float),paired[column+'_frozen'].to_numpy(float)
            if not np.array_equal(np.isnan(a),np.isnan(b)):raise ValueError('Unknown/missing feature changed: '+column)
            error=float(np.nanmax(abs(a-b))) if np.isfinite(a).any() else 0.
            if error>1e-6:raise ValueError('PR9 feature mismatch '+column+': '+str(error))
            errors[column]=error
        reports.append(dict(season=season,cutoff=str(cut),rows=len(actual),max_abs_error=max(errors.values()),fields=errors))
    report=dict(scope='feature_regression_not_independent_accuracy',matched_rows=sum(x['rows'] for x in reports),tolerance=1e-6,origins=reports,passed=True,
        implementation_sha256=hashlib.sha256((ROOT/'scripts/current_b_features.py').read_bytes()).hexdigest())
    out=ROOT/'work/current-B-role-training/feature-parity.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report
if __name__=='__main__':run()
