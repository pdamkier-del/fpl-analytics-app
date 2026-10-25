"""Read-only data -> MM -> PM -> TS trace of one sealed B snapshot.

This explains and checks existing values; it never estimates new probabilities,
recalculates xP, changes a manager squad, or certifies predictive accuracy.
"""
import argparse,gzip,hashlib,json,math
from pathlib import Path
import pandas as pd
from b_chain_contract import validate_forecast
from fpl_v1_1_model.forecast_snapshot import require_snapshot
from run_live_vfinal_joint_simulation import POINT_COMPONENTS

INPUT_GROUPS={
    'source_clocks':('cutoff','evidence_at','max_history_known_at','history_latest_available_at','team_news_source_cutoff'),
    'match_environment':('lambda_home_goals','lambda_away_goals','assist_probability_per_goal'),
    'player_rate_inputs':('goal_rate90','assist_rate90','goal_mu','assist_mu','control_xmins'),
    'penalties':('lambda_pen','pen_weight','pen_conversion','team_pen_conversion'),
    'defensive_contributions':('mu_dc','dc_alpha'),
    'keeper_saves':('lambda_saves',),
    'discipline':('p_yellow','p_red','p_own_goal'),
    'bonus_background':('bg_mean_rate90','bg_sd90'),
    'role_context':('expected_role','xi_assigned_role','xi_formation','role_entropy_fast'),
    'workload_context':('work_minutes_7d','work_minutes_14d','work_team_nonpl_matches_7d','work_player_rest_days'),
    'availability':('team_news_state','team_news_source','team_news_effective_at','team_news_raw'),
}


def clean(value):
    return None if pd.isna(value) else value.item() if hasattr(value,'item') else value


def load_inputs(forecast,directory):
    for name,digest in forecast['input_sha256'].items():
        path=directory/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Snapshot input checksum mismatch: '+name)
    data=pd.read_csv(directory/'pm.csv.gz',low_memory=False,float_precision='round_trip')
    if data.duplicated(['fixture_uuid','player_uuid']).any():raise ValueError('Duplicate input identity')
    return data.set_index(['fixture_uuid','player_uuid'])


def build_trace(forecast,inputs,np_head=None):
    seal=require_snapshot(forecast);validate_forecast(forecast)
    if np_head is not None:
        expected=forecast.get('nonpenalty_goal_head',{}).get('goal_head_audit_sha256')
        if not expected or hashlib.sha256(np_head.read_bytes()).hexdigest()!=expected:
            raise ValueError('Selected nonpenalty head checksum mismatch')
        head=pd.read_csv(np_head,float_precision='round_trip')
        if head.duplicated(['fixture_uuid','player_uuid']).any():raise ValueError('Duplicate NP identity')
        head=head.set_index(['fixture_uuid','player_uuid'])
    else:head=None
    seen=set();rows=[]
    for player in forecast['players']:
        for week in player['weeks']:
            for match in week['fixtures']:
                key=(match['fixture_uuid'],player['player_uuid'])
                if key in seen:raise ValueError('Duplicate forecast identity')
                seen.add(key)
                if key not in inputs.index:raise ValueError('Missing source player/fixture')
                source=inputs.loc[key]
                if int(source.fpl_element)!=player['id'] or int(source.team_id)!=player['team_id']:
                    raise ValueError('Player/club identity mismatch')
                components=match['components']
                if set(components)!=set(POINT_COMPONENTS):raise ValueError('Missing/unknown point components')
                total=sum(components[k] for k in POINT_COMPONENTS)
                if not math.isclose(total,match['xpts'],abs_tol=1e-8,rel_tol=0):raise ValueError('Point components do not reconcile')
                subset=match['penalty_miss_points_subset_of_negative']
                if not subset<=0 or subset<components['negative_points']-1e-8:raise ValueError('Invalid penalty-miss subset')
                if head is not None and key not in head.index:raise ValueError('Missing selected NP allocation')
                rows.append(dict(player_id=player['id'],player_uuid=player['player_uuid'],name=player['name'],team=player['team'],gw=week['gw'],fixture_uuid=key[0],kickoff=match['kickoff'],forecast_sha256=seal,
                    upstream_PM_inputs={group:{name:clean(source[name]) for name in fields if name in source.index} for group,fields in INPUT_GROUPS.items()},
                    selected_NP_head=None if head is None else {name:clean(value)for name,value in head.loc[key].items()},
                    MM=dict(p_start=match['p_start'],p_60_plus=match['p_60_plus'],p_90=match['p_90'],xmins=match['xmins']),
                    PM=dict(analytic_minutes=match['pm_analytic_minutes'],sampled_minutes=match['simulated_minutes'],components=components,penalty_miss_subset_already_in_negative=subset,penalty=match.get('penalty'),xpts=match['xpts'],sample_distribution=match['distribution']),
                    TS=dict(gw=week['gw'],week_xpts=week['xpts'],shared_scenario_draws=len(week['scenarios']['points']),source_forecast_sha256=seal)))
    return dict(version='B-player-points-trace-v1',forecast_sha256=seal,data_asof=forecast['data_asof'],input_sha256=forecast['input_sha256'],component_source_asof=forecast.get('component_source_asof'),players=len(forecast['players']),fixture_rows=len(rows),source_inputs_verified=True,selected_NP_head_verified=head is not None,probabilities_reestimated=False,full_model_certification=False,notes=['Upstream PM goal_mu/control_xmins are frozen adapter inputs, not final expected goals. The selected NP head replaces ordinary weights separately.','Analytic MM means and finite-sample PM means are different representations; finite-sample fluctuation is not a second minute forecast.','TS consumes aligned weekly scenarios from this seal; it does not independently estimate player points.','Context fields show available source inputs, not causal feature contributions or implemented future-CL/coach-quote inference.'],rows=rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--forecast',type=Path,required=True);ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--np-head',type=Path);ap.add_argument('--player',type=int);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    forecast=json.loads(args.forecast.read_text());inputs=load_inputs(forecast,args.inputs);trace=build_trace(forecast,inputs,args.np_head)
    if args.player is not None:
        trace['rows']=[r for r in trace['rows'] if r['player_id']==args.player]
        if not trace['rows']:raise ValueError('Player not in verified snapshot')
        trace['selected_player_id']=args.player
    trace['rows_in_output']=len(trace['rows'])
    raw=(json.dumps(trace,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(gzip.compress(raw,mtime=0)if args.out.suffix=='.gz'else raw)
    print(json.dumps({k:v for k,v in trace.items() if k not in ('rows','input_sha256','notes','component_source_asof')}))

if __name__=='__main__':main()
