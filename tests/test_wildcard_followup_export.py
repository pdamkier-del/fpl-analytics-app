"""Export already-computed B WC decisions without changing original scores."""
import copy,json
from service.manager_job import calculate

def test_B_wc_path_is_exported_without_changing_original_search():
    raw={'season':'2026-27','gw':6,'source':'SYNTHETIC_EXPORT_REGRESSION','observed_at':'2026-10-10T07:00:00Z','bank_tenths':15,'free_transfers':2,'squad':[{'id':i+1,'purchase_price_tenths':50}for i in range(15)],'chips_used':{k:[]for k in ['wildcard','free_hit','bench_boost','triple_captain']}}
    positions=[1]*2+[2]*5+[3]*5+[4]*3
    f={'season':'2026-27','gws':list(range(6,12)),'data_asof':'2026-10-10T07:35:11Z','model':'original_locked_vFinal_diagnostic','locked_model_active':False,'blockers':[],'players':[{'id':i+1,'name':str(i+1),'team_id':i//3+1,'position':pos,'price_tenths':50,'weeks':[{'gw':g,'xpts':4.,'p_play':1.,'fixtures':[{}]}for g in range(6,12)]}for i,pos in enumerate(positions)]}
    before=copy.deepcopy(raw);normal=calculate(f,raw);b=calculate(dict(f,model='B-MM-PM-TS-v1'),raw)
    assert raw==before
    for key in ['plan','lineup','chip_assessment','chip_plan','comparison','current_team']:assert normal[key]==b[key]
    assert 'path'not in normal['wildcard_followup']
    follow=b['wildcard_followup'];assert follow['schema']=='B-wildcard-followup-v1'
    assert [r['gw']for r in follow['path']]==list(range(7,12))
    assert follow['squad_ids']==sorted(b['chip_assessment']['candidate_lineups']['wildcard']['squad_ids'])
    assert follow['six_gw_xp_after_hits']==normal['wildcard_followup']['six_gw_xp_after_hits']
    assert follow['weighted_objective_before_chip_timing_threshold']==normal['wildcard_followup']['weighted_objective_before_chip_timing_threshold']
    json.dumps(b,allow_nan=False)
