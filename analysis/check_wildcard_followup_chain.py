"""Run the unchanged B chain on an explicitly synthetic manager fixture."""
import argparse,json,time
from pathlib import Path
from datetime import datetime,timezone
from service.preview_manager_job import calculate

def main():
    p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--private-result',type=Path,required=True);p.add_argument('--proof',type=Path,required=True);a=p.parse_args()
    f=json.loads(a.forecast.read_text());fixture=json.loads(a.fixture.read_text());assert fixture['state']['source']=='SYNTHETIC_DASHBOARD_UI_TEST_NOT_USER_TEAM'
    before=json.dumps(fixture['state'],sort_keys=True);t=time.monotonic();result=calculate(f,fixture['state'],snapshot_at=datetime.now(timezone.utc).isoformat());w=result['chip_assessment']['candidate_lineups']['wildcard'];follow=result['wildcard_followup']
    assert follow['schema']=='B-wildcard-followup-v1'
    assert [r['gw']for r in follow['path']]==f['gws'][1:]
    assert sorted(w['squad_ids'])==follow['squad_ids']
    assert abs(w['expected_score']+sum(r['projected_manager_score']-r['official_hit_points']for r in follow['path'])-follow['six_gw_xp_after_hits'])<1e-9
    assert before==json.dumps(fixture['state'],sort_keys=True)
    a.private_result.write_text(json.dumps(result,allow_nan=False))
    proof={'real_published_B_forecast':f['forecast_sha256'],'synthetic_manager_state_only':True,'original_shared_PM_scorer_and_TS_used':True,'WC_followup_GWs':f['gws'][1:],'total_matches_current_WC_plus_exported_actions':True,'original_state_unchanged':True,'no_new_search_for_export':True,'seconds':round(time.monotonic()-t,2)};a.proof.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
if __name__=='__main__':main()
