#!/usr/bin/env python3
"""Forensic read-only GW7-12 frozen MM audit for Chelsea's João Pedro.
Never changes frozen MM/PM/TS; records what mathematically causes low xM.
"""
from __future__ import annotations
from pathlib import Path
import json,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
W=ROOT/'work/live-final-model'
b=json.loads((W/'bootstrap.json').read_text())
people={int(p['id']):p for p in b['elements']}
club={int(t['id']):t['name'] for t in b['teams']}
matches=json.loads((W/'fixtures.json').read_text())
f=pd.read_csv(B/'vfinal_live_full_simulator_input.csv.gz',low_memory=False)
raw=pd.read_csv(W/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
hist=pd.read_csv(B/'player_fixture_observations.csv.gz',low_memory=False)
past_features=pd.read_csv(B/'reconstructed_training_features.csv.gz',low_memory=False)
cutoff=pd.to_datetime(f.cutoff,utc=True)
assert cutoff.nunique()==1
hist['available_at']=pd.to_datetime(hist.available_at,utc=True)
hist=hist[hist.available_at<cutoff.iloc[0]].copy()
assert (hist.gw<min(f.target_gw)).all()
# Exact historic ID/club must be validated from official source before diagnosing.
identified=[p for p in b['elements'] if 'pedro' in (p.get('web_name') or '').lower() and 'jo' in (p.get('first_name') or '').lower() and club.get(int(p['team']))=='Chelsea']
if len(identified)!=1:raise ValueError('Ambiguous Chelsea Joao Pedro FPL identity: '+str([(p['id'],p['web_name']) for p in identified]))
player=identified[0]
pid=int(player['id'])
z=f[f.fpl_element.eq(pid)].sort_values('target_gw')
r=raw[raw.fpl_element.eq(pid)].sort_values('target_gw')
h=hist[hist.fpl_element.eq(pid)].sort_values('gw')
assert len(z)==len(r)==6 and len(h)>=5,(len(z),len(r),len(h))
assert set(z.player_uuid)==set(r.player_uuid)==set(h.player_uuid)
print('JOAO_ID',json.dumps({'id':pid,'name':player['web_name'],'club':club[int(player['team'])],
    'status':player.get('status'),'chance_next':player.get('chance_of_playing_next_round'),
    'news':player.get('news'),'news_added':player.get('news_added'),
    'now_cost':player.get('now_cost'),'official_minutes':player.get('minutes'),
    'official_starts':player.get('starts'),'official_total_points':player.get('total_points'),
    'forecast_cutoff':str(cutoff.iloc[0]),'gws':list(map(int,z.target_gw))},default=str))
wanted=['gw','fixture_uuid','started','minutes','available_at','goals','fpl_assists','xg','xa']
print('JOAO_HISTORY',h[[c for c in wanted if c in h]].sort_values('gw').to_json(orient='records',date_format='iso'))
p=past_features[past_features.player_uuid.eq(z.player_uuid.iloc[0])]
for c in ['gw','started','y','minutes','outcome_known_at','seq_hist_n']:
    if c in p and c not in wanted:wanted.append(c)
if len(p):
    print('JOAO_TRAINING',p[[x for x in ['gw','y','minutes','started','outcome_known_at','seq_hist_n','rating_hist_n','team_news_state'] if x in p]].sort_values('gw').tail(12).to_json(orient='records'))
fields=['target_gw','fixture_uuid','player','pos','expected_role','xi_assigned_role','xi_selected_map','xi_formation','p_start','control_p_start','base_logit','start_minutes_mean',
       'cameo_minutes_mean','p_cameo_given_bench','mm_q_sub','mm_sub_minutes','mm_raw_xmins',
       'xmins','control_xmins','expected_minutes','live_effective_q_sub','live_eligibility_applied','team_news_state',
       'team_news_raw_status','team_news_scoped_chance','team_news_availability_cap','team_news_hard_out',
       'seq_hist_n','seq_last_minutes','seq_prev_minutes','seq_mean2_minutes','seq_mean3_minutes','seq_mean5_minutes',
       'seq_last_started','seq_start_share3','seq_start_share5','seq_start_streak','seq_nonstart_streak',
       'work_minutes_7d','work_minutes_14d','work_team_nonpl_matches_7d','work_player_rest_days',
       'rating_hist_n','rating_recent','rating_self_delta','rating_comp_adjustment','performance_score',
       'xi_q_role','xi_score_margin','xi_role_competitors','xi_assignment_score']
for name,d in [('JOAO_MM',r),('JOAO_PM_INPUT',z)]:
    print(name,d[[c for c in fields if c in d]].sort_values('target_gw').to_json(orient='records',date_format='iso'))
rows=[]
for p in r.sort_values('target_gw').itertuples(index=False):
    pstart=float(p.p_start);sm=float(p.start_minutes_mean);qs=float(p.mm_q_sub);sub=float(p.mm_sub_minutes)
    reconstructed=pstart*sm+(1-pstart)*qs*sub
    rows.append(dict(gw=int(p.target_gw),p_start=pstart,start_minutes_conditional=sm,
                     appearance_if_benched=qs,sub_minutes_conditional=sub,
                     term_starter=pstart*sm,term_sub=(1-pstart)*qs*sub,
                     reconstructed_xmins=reconstructed,published_raw_xmins=float(p.xmins),
                     xmins_if_90pct_start=.9*sm+.1*qs*sub,
                     xmins_if_certain_start=sm))
print('JOAO_COMPONENTS',json.dumps(rows))
matches_index={str(m['id']):m for m in matches}
for row in r.sort_values('target_gw').itertuples(index=False):
    t=raw[(raw.fixture_uuid==row.fixture_uuid)&raw.team_id.eq(row.team_id)].copy()
    top=t.sort_values('p_start',ascending=False)
    minimal=['player','expected_role','xi_assigned_role','xi_selected_map','p_start','xmins','start_minutes_mean','team_news_state']
    print('JOAO_CHELSEA_COMPETITION',json.dumps({'gw':int(row.target_gw),
        'squad_size':len(t),'sum_start':round(float(t.p_start.sum()),6),
        'xi_formation':row.xi_formation,
        'joao_rank':int((t.p_start>float(row.p_start)).sum()+1),
        'top_players':top[[c for c in minimal if c in top]].head(18).round(5).to_dict('records')},default=str))
report=dict(classification='JOAO_PEDRO_MM_FORENSIC_NO_MODEL_CHANGE',id=pid,gws=list(map(int(r.target_gw)),
            latest_xmins=float(r.sort_values('target_gw').xmins.iloc[0]),
            training_rows=len(p),history_rows=len(h),history_source_gws=sorted(map(int,h.gw.unique())),
            calculation=rows,cutoff=str(cutoff.iloc[0]),promoted=False)
out=W/'joao_pedro_mm_forensic.json';out.write_text(json.dumps(report,indent=2)+'\n')
