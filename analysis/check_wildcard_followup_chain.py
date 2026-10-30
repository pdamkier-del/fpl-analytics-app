"""Run the unchanged B chain on an explicitly synthetic manager fixture."""
import argparse,json,time
from pathlib import Path
from datetime import datetime,timezone
from service.preview_manager_job import calculate

def verify_bb_score_identity(forecast,result):
    import numpy as np
    people={p['id']:p for p in forecast['players']};actions={r['gw']:r for r in result['wildcard_followup']['path']}
    for c in result['wildcard_followup']['bench_boost']['candidates']:
        gw=c['gw'];ids=c['squad_ids'];ix={pid:i for i,pid in enumerate(ids)};weeks={pid:next(w for w in people[pid]['weeks']if w['gw']==gw)for pid in ids}
        points=np.asarray([weeks[pid]['scenarios']['points']for pid in ids],float).T;minutes=np.asarray([weeks[pid]['scenarios']['minutes']for pid in ids],float).T
        cap=next(r['id']for r in c['lineup']if r['role']=='C');vice=next(r['id']for r in c['lineup']if r['role']=='VC')
        full_bb=float((points.sum(axis=1)+points[:,ix[cap]]+np.where(minutes[:,ix[cap]]<=0,points[:,ix[vice]],0.)).mean())
        assert abs(full_bb-actions[gw]['normal_projected_manager_score']-c['incremental_xp'])<1e-7
    return len(actions)

def main():
    p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--private-result',type=Path,required=True);p.add_argument('--proof',type=Path,required=True);a=p.parse_args()
    f=json.loads(a.forecast.read_text());fixture=json.loads(a.fixture.read_text());assert fixture['state']['source']=='SYNTHETIC_DASHBOARD_UI_TEST_NOT_USER_TEAM'
    before=json.dumps(fixture['state'],sort_keys=True);t=time.monotonic();result=calculate(f,fixture['state'],snapshot_at=datetime.now(timezone.utc).isoformat());w=result['chip_assessment']['candidate_lineups']['wildcard'];follow=result['wildcard_followup']
    assert follow['schema']=='B-wildcard-followup-v1'
    assert [r['gw']for r in follow['path']]==f['gws'][1:]
    assert sorted(w['squad_ids'])==follow['squad_ids']
    bb=follow['bench_boost'];assert bb['schema']=='B-wildcard-BB-followup-v1'
    assert all(g>result['gw']for g in bb['selected_gws'])
    assert len({g<=19 for g in bb['selected_gws']})==len(bb['selected_gws'])
    assert abs(follow['six_gw_xp_after_hits']-follow['wc_without_bb_six_gw_xp_after_hits']-sum(c['incremental_xp']for c in bb['candidates']if c['decision']=='USE_BB_PLANNED'))<1e-9
    assert abs(w['expected_score']+sum(r['projected_manager_score']-r['official_hit_points']for r in follow['path'])-follow['six_gw_xp_after_hits'])<1e-9
    assert before==json.dumps(fixture['state'],sort_keys=True)
    verify_bb_score_identity(f,result)
    a.private_result.write_text(json.dumps(result,allow_nan=False))
    proof={'real_published_B_forecast':f['forecast_sha256'],'synthetic_manager_state_only':True,'original_shared_PM_scorer_and_TS_used':True,'WC_followup_GWs':f['gws'][1:],'total_matches_current_WC_plus_exported_actions':True,'original_state_unchanged':True,'no_new_search_for_export':True,'BB_status':bb['status'],'BB_selected_GWs':bb['selected_gws'],'BB_candidates_evaluated':len(bb['candidates']),'BB_gain_not_double_counted':True,'seconds':round(time.monotonic()-t,2)};a.proof.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
if __name__=='__main__':main()
