#!/usr/bin/env python3
"""Six-GW public diagnostics from original frozen MM inference, no final xP.

GW6 uses the approved hard-ineligibility gate. For future GWs team news is
UNKNOWN; the current GW OUT status is never copied into later dates.
"""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.live_availability_boundary import prepare_live_mm_release_candidate

WORK=ROOT/'work/live-final-model';APP=ROOT/'app'

def publish():
    source=json.loads((WORK/'source_manifest.json').read_text())
    audit=json.loads((WORK/'mm_inference_six_gw.json').read_text())
    if audit['live_certified'] is not False or audit['target_outcomes_used']!=0:
        raise ValueError('Only diagnostic frozen MM output accepted')
    df=pd.read_csv(WORK/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
    origin=int(source['target_gw'])
    expected=list(range(origin,min(origin+5,38)+1))
    if sorted(map(int,df.target_gw.unique()))!=expected or not df.gw.eq(origin).all():
        raise ValueError('Origin/horizon mismatch')
    if len(df)!=667*len(expected):
        raise ValueError('Missing horizon player-fixture rows')
    if not df.groupby('target_gw').fpl_element.nunique().eq(667).all():
        raise ValueError('Future player roster or ID incomplete')
    if df.duplicated(['target_gw','fpl_element']).any():
        raise ValueError('Duplicate future player identity')
    if df[['p_start','mm_q_sub','xmins']].isna().any().any():
        raise ValueError('Invalid MM diagnostic parameters')
    if df[df.target_gw.ne(origin)].team_news_state.ne('UNKNOWN').any():
        raise ValueError('Current team news illegally carried into later GWs')
    if df[df.target_gw.ne(origin)].team_news_availability_cap.ne(1.).any():
        raise ValueError('Current injury status illegally carried to future GWs')
    current=df[df.target_gw.eq(origin)].copy()
    gated=prepare_live_mm_release_candidate(
       current,p_start=current.p_start.to_numpy(float),
       q_sub=current.mm_q_sub.to_numpy(float),
       sub_minutes=current.mm_sub_minutes.to_numpy(float),
       origin_gw=origin,news_scoped_gw=origin)
    future=df[df.target_gw.ne(origin)].copy()
    future['live_effective_q_sub']=future.mm_q_sub
    future['live_eligibility_applied']=False
    future['mm_raw_xmins']=future.xmins
    full=pd.concat([gated,future],ignore_index=True)
    maxerr=float((full.groupby(['target_gw','fixture_uuid','team_id']).p_start.sum()-11).abs().max())
    if maxerr>1e-6:raise ValueError('Six GW exact 11 constraint failed')
    output=[]
    for row in full.itertuples(index=False):
        output.append({
          'gw':int(row.target_gw),'id':int(row.fpl_element),
          'name':str(row.player),'team_id':int(row.team_id),'team':str(row.team),
          'role':str(row.expected_role),'xi_role':str(row.xi_assigned_role),
          'xi_formation':str(row.xi_formation),
          'p_start':round(float(row.p_start),6),
          'p_sub_given_not_start':round(float(row.live_effective_q_sub),6),
          'xmins':round(float(row.xmins),4),
          'raw_xmins':round(float(row.mm_raw_xmins),4),
          'not_available':bool(row.live_eligibility_applied),
          'future_team_news_unknown':bool(row.target_gw!=origin)
        })
    if not all(np.isfinite([p['p_start'],p['p_sub_given_not_start'],p['xmins']]).all() for p in output):
        raise ValueError('Nonfinite six-week MM forecast')
    result={
        'schema_version':1,'classification':'UNCERTIFIED_DIAGNOSTIC_SIX_GW_MM_NOT_FINAL',
        'locked_model_active':False,'full_final_chain_certified':False,
        'model_math_changed':False,'source_observed_at':source['observed_at'],
        'origin_gw':origin,'gws':expected,'players_per_gw':667,
        'player_week_rows':len(output),'fixture_count_per_gw':{
            str(k):int(v) for k,v in full.groupby('target_gw').fixture_uuid.nunique().items()},
        'origin_not_available_count':int(gated.live_eligibility_applied.sum()),
        'max_expected_starters_error':maxerr,
        'training_status':audit['training_quality']['classification'],
        'training_blockers':audit['training_quality']['blockers'],
        'future_news_unknown':True,'live_pm_xp_computed':False,
        'description':'Låst MM-kode på delvist rekonstrueret historik, kun diagnostik, ikke finalmodel.',
        'rows':output}
    (APP/'mm-diagnostic-6gw.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False))
    print('PUBLISHED SIX-GW NONCERTIFIED MM',json.dumps({
        'gws':expected,'rows':len(output),'error':maxerr,'current_not_available':result['origin_not_available_count']},ensure_ascii=False))
    return result
if __name__=='__main__':publish()
