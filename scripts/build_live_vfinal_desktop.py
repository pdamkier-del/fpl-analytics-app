#!/usr/bin/env python3
"""Publish real frozen-simulator outputs as a labelled diagnostic, never a release."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_live_vfinal_joint_simulation import POINT_COMPONENTS
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'

def build(inputs,predictions,bootstrap,audit):
    keys=['fixture_uuid','player_uuid']
    if inputs.duplicated(keys).any() or predictions.duplicated(keys).any():raise ValueError('Duplicate fixture/player')
    x=inputs.merge(predictions,on=keys,validate='one_to_one',suffixes=('','_sim'),how='outer',indicator=True)
    if not x._merge.eq('both').all():raise ValueError('Forecast identity coverage mismatch')
    if not x.target_gw.eq(x.gw_sim).all():raise ValueError('Wrong forecast GW')
    x['gw']=x.target_gw
    if not np.allclose(x[list(POINT_COMPONENTS)].sum(axis=1),x.xpts_fixture,atol=1e-8,rtol=0):raise ValueError('Point components mismatch')
    hard=x.live_eligibility_applied.fillna(False).astype(bool)
    if x.loc[hard,'xpts_fixture'].ne(0).any() or x.loc[hard,'expected_minutes_sim'].ne(0).any():raise ValueError('Unavailable player has minutes/points')
    players={int(p['id']):p for p in bootstrap['elements']}
    teams={int(t['id']):t['name'] for t in bootstrap['teams']}
    needed=['fpl_element','player_uuid','team_id','gw','control_p_start','p_cameo_given_bench','control_xmins','live_eligibility_applied','fixture_uuid','target_kickoff','xpts_fixture','expected_minutes_sim','penalty_miss_points',*POINT_COMPONENTS]
    x=x[list(dict.fromkeys(needed))+['cutoff']]
    out=[]
    for pid,g in x.groupby('fpl_element'):
        p=players[int(pid)]
        if set(g.team_id.astype(int))!={int(p['team'])}:raise ValueError('Team identity mismatch')
        weeks=[]
        for gw,w in g.groupby('gw'):
            # Same DGW probability aggregation as run_rolling_vfinal_gw6_38.
            pp=w.control_p_start+(1-w.control_p_start)*w.p_cameo_given_bench
            weeks.append({'gw':int(gw),'xpts':float(w.xpts_fixture.sum()),'xmins':float(w.control_xmins.sum()),
                'p_play':float(1-np.prod(1-pp)), 'unavailable':bool(w.live_eligibility_applied.fillna(False).all()),
                'fixtures':[{'fixture_uuid':r.fixture_uuid,'kickoff':r.target_kickoff,'xpts':float(r.xpts_fixture),
                    'p_start':float(r.control_p_start),'q_sub':float(r.p_cameo_given_bench),'xmins':float(r.control_xmins),
                    'simulated_minutes':float(r.expected_minutes_sim),'components':{k:float(getattr(r,k)) for k in POINT_COMPONENTS},
                    'penalty_miss_points_subset_of_negative':float(r.penalty_miss_points)} for r in w.itertuples()]})
        out.append({'id':int(pid),'player_uuid':str(g.player_uuid.iloc[0]),'name':p['web_name'],
                    'team':teams[int(p['team'])],'team_id':int(p['team']),'position':int(p['element_type']),
                    'price_tenths':int(p['now_cost']),'weeks':weeks})
    return {'model':'original_locked_vFinal_diagnostic','locked_model_active':False,
        'data_asof':str(x.cutoff.iloc[0]),'season':'2026-27','gws':sorted(x.gw.unique().astype(int).tolist()),
        'fixtures':int(x.fixture_uuid.nunique()),'player_fixture_rows':len(x),'players':out,
        'source_workflow':'https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38056989718',
        'quality':{'verified_bps_player_matches':int(audit['verified_player_match_rows']),
                   'quarantined_bps_player_matches':int(audit['quarantined_rows']),
                   'missing_bps_fields':audit['missing_fields']},
        'blockers':['BPS history is partial: incomplete rows are quarantined, never imputed.',
                    'MM/source coverage still requires a complete release quality audit.',
                    'No verified manager bank, free transfers, purchase prices or chip usage state.',
                    'Locked TC future-option scenario coverage is not yet available.'],
        'recommendations':{'transfers':{'status':'Not Available'},'chips':{'status':'Not Available'}}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'app/vfinal-diagnostic.json');a=p.parse_args()
    inp=BASE/'vfinal_live_full_simulator_input.csv.gz';pred=BASE/'live_vfinal_fixture_xp.csv.gz'
    result=build(pd.read_csv(inp,low_memory=False),pd.read_csv(pred),json.loads((ROOT/'work/live-final-model/bootstrap.json').read_text()),json.loads((ROOT/'work/live-final-model/live_bps_source_audit.json').read_text()))
    result['checksums']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (inp,pred)}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    print('Published diagnostic only:',result['fixtures'],result['player_fixture_rows'],len(result['players']))
if __name__=='__main__':main()
