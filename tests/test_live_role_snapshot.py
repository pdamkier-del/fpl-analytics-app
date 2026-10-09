#!/usr/bin/env python3
"""Verify evidence-backed q/H from completed lineups, and safe cross-season IDs."""
import csv, json, importlib.util
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('role_live',ROOT/'scripts/build_live_role_snapshot.py')
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader();writer.writerows(rows)

def main():
    with TemporaryDirectory() as t:
        tmp=Path(t); prior=tmp/'prior';stats=tmp/'stats'
        ids=[dict(player_id=i,player_code=10000+i) for i in range(1,12)]
        write(tmp/'ident.csv',ids)
        match='25-26-prem-test-vs-example'
        write(prior/'GW1'/'fixtures.csv',[
          dict(match_id=match,kickoff_time='2026-05-01T15:00:00Z',finished='True')])
        positions=['G']+['D']*4+['M']*5+['F']
        lines=[];avgs=[];mins=[]
        for i in range(1,12):
            lines.append(dict(match_id=match,team_side='home',team_code=94,player_id=i,
                              player_name=f'Person {i}',position=positions[i-1],is_starting='True',
                              formation='4-2-3-1',lineup_status='confirmed'))
            avgs.append(dict(match_id=match,team_side='home',player_id=i,
                             x=float(i*6),y=float(i*8)))
            mins.append(dict(match_id=match,player_id=i,minutes_played=90))
        write(prior/'GW1'/'lineups.csv',lines)
        write(prior/'GW1'/'average_positions.csv',avgs)
        write(stats/'GW1'/'playermatchstats.csv',mins)
        official={'observed_at_utc':'2026-10-09T12:00:00Z','season':'2026-27',
           'teams':[{'id':1,'code':94},{'id':2,'code':17}],
           'players':[{'id':i+200,'player_code':10000+i,
                       'team_id':2 if i==11 else 1,'name':f'Person {i}'}
                      for i in range(1,12)]+
                     [{'id':999,'player_code':99999,'team_id':1,'name':'New player'}]}
        with patch.object(module,'IDENT_PRIOR',tmp/'ident.csv'):
            result=module.build(official,{},raw_prior=prior,stats_prior=stats,
                                raw_current=tmp/'no_current',
                                cutoff=datetime(2026,10,9,12,tzinfo=timezone.utc))
        assert result['historical_tactical_lineups_found']==1,result['source_report']
        assert result['current_tactical_lineups_found']==0
        assert result['current_xi_certified'] is False
        byid={p['id']:p for p in result['players']}
        old=byid[201]; moved=byid[211]; new=byid[999]
        assert old['role_source']=='prior_season_same_club'
        assert old['primary_role']=='GK'
        assert old['H'].get('GK',0)>.1
        assert abs(sum(old['q'].values())-1)<.005
        assert moved['role_source']=='prior_season_different_club'
        assert moved['q'] and not moved['H']
        assert new['role_source']=='missing_observed_role'
        assert not new['q'] and not new['H']
        assert not result['expected_lineups']
        # Match observations after cutoff are never available for q/H.
        with patch.object(module,'IDENT_PRIOR',tmp/'ident.csv'):
            early=module.build(official,{},raw_prior=prior,stats_prior=stats,
                                raw_current=tmp/'no_current',
                                cutoff=datetime(2026,4,1,12,tzinfo=timezone.utc))
        assert early['historical_tactical_lineups_found']==0
        assert not any(x['q'] for x in early['players'])
        future=[{
           'id':i+200,'team_id':1,'role_source':'current_season_confirmed',
           'q':{role:1.},'H':{role:.9},'evidence':3.}
           for i,role in enumerate(['GK','RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST'],1)]
        recent={'current_tactical_lineups_found':20,'players':future,
           'team_formations':[{'team_id':1,'confidence':'current_observed',
             'formations':[{'formation':'4-2-3-1','weighted_share':1.,'current_season_games':3}]}]}
        b={'meta':{'updated':'2026-10-09T11:00:00Z','model_version':'locked_mm_pm_vfinal','next_gw':8},
           'forecasts':[{'id':x['id'],'player':'P'+str(x['id']),
                         'gws':[{'gw':8,'pstart':.95,'xmins':82}]} for x in future]}
        official_xi={'official_next_gw':8,'teams':[{'id':1,'code':94,'short_name':'CHE'}]}
        def dummy_optimizer(players,**kwargs):
            assert kwargs['formations']==('4-2-3-1',)
            assert kwargs['formation_log_prior']=={'4-2-3-1':0.0}
            slots=['GK','RB','RCB','LCB','LB','RDM','LDM','RAM','CAM','LAM','ST']
            return {'formation':'4-2-3-1','xi':[
                SimpleNamespace(player_uuid=p['player_uuid'],role=role,q_role=1.,
                                hierarchy=.9,base_p_start=.95)
                for p,role in zip(players,slots)]}
        result_xi=module.generate_current_xi(recent,official_xi,b,
            asof=datetime(2026,10,9,12,tzinfo=timezone.utc),optimizer=dummy_optimizer)
        assert result_xi and len(result_xi[0]['players'])==11
        assert result_xi[0]['club']=='CHE'
        assert len({p['id'] for p in result_xi[0]['players']})==11
        b['meta']['model_version']='live_simple_baseline_v0.1'
        assert not module.generate_current_xi(recent,official_xi,b,
            asof=datetime(2026,10,9,12,tzinfo=timezone.utc),optimizer=dummy_optimizer)
        print('LIVE_ROLE_EVIDENCE_OK',json.dumps({'prior':old['primary_role'],
           'q':old['q']['GK'],'H':old['H']['GK'],
           'transferred_H':moved['H'],'no_guess':new['role_source']}))

if __name__=='__main__':main()
