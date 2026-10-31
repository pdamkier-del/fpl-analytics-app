"""Read-only private transfer audit; input/output paths must stay outside Git."""
import argparse,copy,json,math
from pathlib import Path
from datetime import datetime,timezone
from service.preview_manager_job import calculate
from scripts.run_live_locked_ts import project,parse_state
from scripts.b_preview_ts import preview_scoring
from scripts.run_joint_fh_wc_stopping_replay import cfg
from fpl_xpts.transfer_planner import _apply_selected_squad,next_free_transfers,transfer_penalties
from fpl_xpts.season_replay import valid_squad

def audit(forecast,raw):
    before=copy.deepcopy(raw);at=datetime.now(timezone.utc).isoformat()
    result=calculate(forecast,raw,snapshot_at=at)
    assert raw==before
    meta,origin=project(forecast);state=parse_state(raw,meta,result['gw'],at);names={p['id']:p['name']for p in forecast['players']}
    def path_check(start,path,weights,bb=False):
        state=copy.deepcopy(start);objective=0.
        from fpl_xpts.transfer_planner import projected_manager_score
        for action,weight in zip(path,weights):
            assert state.bank==action['bank_before']and state.free_transfers==action['free_transfers_before']
            selected=(set(state.squad)-set(action['outgoing']))|set(action['incoming'])
            after,outs,ins=_apply_selected_squad(state,selected,meta)
            assert set(outs)==set(action['outgoing'])and set(ins)==set(action['incoming'])
            assert after.bank==action['bank_after']and after.bank>=0 and valid_squad(meta,after.squad)
            hit,buffer=transfer_penalties(state.free_transfers,len(ins),cfg().hit_uncertainty_buffer)
            assert hit==action['official_hit_points']and buffer==action['uncertainty_penalty']
            score=projected_manager_score(origin,meta,after.squad,action['gw'])
            if action.get('chip')=='bench_boost':score+=action['bench_boost_incremental_xp']
            assert math.isclose(score,action['projected_manager_score'],abs_tol=1e-8)
            objective+=weight*score-hit-buffer
            after.free_transfers=next_free_transfers(state.free_transfers,len(ins));assert after.free_transfers==action['free_transfers_after'];state=after
        return objective
    with preview_scoring(forecast):
        normal=path_check(state,result['plan']['path'],cfg().weights)
        assert math.isclose(normal,result['plan']['objective'],abs_tol=1e-8)
        wc=result['chip_assessment']['candidate_lineups']['wildcard'];after,_,_=_apply_selected_squad(state,set(wc['squad_ids']),meta);after.free_transfers=state.free_transfers
        assert after.bank==wc['bank_after'];follow=result['wildcard_followup'];future=path_check(after,follow['path'],cfg().weights[1:])
        assert math.isclose(wc['expected_score']+future,follow['weighted_objective_before_chip_timing_threshold'],abs_tol=1e-8)
        assert math.isclose(follow['wc_without_bb_weighted_objective']-normal,result['chip_assessment']['wc_gain'],abs_tol=1e-8)
    result['readonly_audit']={'cash_prices_FT_hits_and_legal_squads_pass':True,'joint_PM_rescoring_pass':True,'WC_gain_matches_same_normal_plan':True,'original_state_unchanged':raw==before,'weights':cfg().weights,'optimality_proven':False,'source':'official GW8 ownership/cash and transfer ledger; browser-local state not accessible'}
    summary={'forecast':forecast['forecast_sha256'],'bank':raw['bank_tenths']/10,'FT':raw['free_transfers'],'normal_transfers':[(x['out'],x['in'])for x in result['transfers']],'current_score':result['current_team']['expected_score'],'normal_score':result['plan']['path'][0]['projected_manager_score'],'WC_score':wc['expected_score'],'WC_gain_weighted':result['chip_assessment']['wc_gain'],'choice':result['chip_assessment']['provisional_choice_without_missing_tc'],'WC_XI':[names[r['id']]for r in wc['rows']if r['role']in ['XI','C','VC']],'captain':next(names[r['id']]for r in wc['rows']if r['role']=='C'),'audit':result['readonly_audit']}
    return result,summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--forecast',required=True);p.add_argument('--state',required=True);p.add_argument('--out',required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1];assert not any(Path(x).resolve().is_relative_to(repo)for x in [a.state,a.out]), 'Private state/results must remain outside the repository';r,s=audit(json.loads(Path(a.forecast).read_text()),json.loads(Path(a.state).read_text()));Path(a.out).write_text(json.dumps(r,allow_nan=False));print(json.dumps(s,ensure_ascii=False,indent=2))
