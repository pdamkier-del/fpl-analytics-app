"""Canonical public diagnostics for the isolated B repair, no personal state."""
import gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/integrated-repair-20261031'

def main():
    d=pd.read_csv(OUT/'pm/predictions.csv.gz').sort_values(['season','fixture_uuid','player_uuid','arm']).reset_index(drop=True)
    report=json.loads((OUT/'pm/result.json').read_text());metrics=[];cal=[];paired=[]
    for(season,arm),g in d.groupby(['season','arm']):
        metrics.append(dict(season=season,arm=arm,rows=len(g),fixtures=int(g.fixture_uuid.nunique()),start_Brier=float(((g.p-g.started)**2).mean()),minute_MAE=float(abs(g.xmins-g.minutes).mean()),minute_bias=float((g.xmins-g.minutes).mean()),xp_MAE=float(abs(g.xp-g.total_points).mean()),xp_bias=float((g.xp-g.total_points).mean()),goal_bias=float((g.goals-g.goals_actual).mean()),assist_bias=float((g.assists-g.assists_actual).mean())))
        for name,actual in [('goals','goals_actual'),('assists','assists_actual')]:
            for lo,hi in [(0,.01),(.01,.05),(.05,.1),(.1,.2),(.2,.4),(.4,10)]:
                h=g[g[name].ge(lo)&g[name].lt(hi)]
                if len(h):cal.append(dict(season=season,arm=arm,event=name,lower=lo,upper=hi,rows=len(h),mean_pred=float(h[name].mean()),mean_actual=float(h[actual].mean()),MAE=float(abs(h[name]-h[actual]).mean())))
    rng=np.random.default_rng(20261031)
    for season in ['2024-25','2025-26']:
        base=d[d.season.eq(season)&d.arm.eq('frozen_B')]
        for arm in ['events_only','source_and_events']:
            p=d[d.season.eq(season)&d.arm.eq(arm)].merge(base,on=['fixture_uuid','player_uuid'],suffixes=('','_base'),validate='one_to_one');p['delta']=abs(p.xp-p.total_points)-abs(p.xp_base-p.total_points)
            blocks=p.groupby('fixture_uuid').delta.agg(['sum','size']).to_numpy();draw=blocks[rng.integers(len(blocks),size=(4000,len(blocks)))].sum(axis=1)
            paired.append(dict(season=season,arm=arm,xp_MAE_delta=float(p.delta.mean()),fixture_bootstrap95=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()))
    events=json.loads(gzip.decompress((OUT/'pm/event-receipts.json.gz').read_bytes()))
    counts=[r for r in events if r['arm']=='events_only']
    report['own_goal_accounting']=dict(previous_shared_own_goal_events=0,repaired_expected_shared_own_goals_per_fixture=sum(t['own_goal']for r in counts for t in r['events'].values())/(400*len(counts)),max_conditional_goal_budget_error=max(t['max_expected_budget_error']for r in counts for t in r['events'].values()),unattributed_events=sum(t['unattributed']for r in counts for t in r['events'].values()),special_assist_occurrence_rates='Not Available; attribution rules tested separately')
    report.update(metrics=metrics,paired_uncertainty=paired,known_limitations=['Reused historical research periods, not independent certification','Historical cup/UEFA coverage is a sourced subset and clocks retain documented proxies','Same seeds do not imply identical random-number pairing across event processes','Medical-return probability is separately validated against first appearance; not medical clearance or start probability','Special penalty-winner/own-goal assist occurrence rates and causal red-card removals not modeled'])
    d.to_csv(OUT/'pm/predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0});(OUT/'pm/result.json').write_text(json.dumps(report,indent=2)+'\n');pd.DataFrame(cal).to_csv(OUT/'pm/event-calibration.csv',index=False)
    before=json.loads((ROOT/'work/integrated-B-before/forecast.json').read_text());after=json.loads((ROOT/'work/integrated-B-final/forecast.json').read_text());b={p['id']:p for p in before['players']};rows=[]
    for p in after['players']:
        if p['name']not in ['Penders','E.Le Fée','Cherki','Sávio']:continue
        for arm,player in [('before',b[p['id']]),('after',p)]:
            w=player['weeks'][0];f=w['fixtures'][0];rows.append(dict(player=p['name'],arm=arm,gw=w['gw'],p_start=f['p_start'],xM=w['xmins'],PM_E_minutes=w['pm_analytic_minutes'],p60=f['p_60_plus'],p90=f['p_90'],xP=w['xpts']))
    (OUT/'current-player-comparison.json').write_text(json.dumps(dict(scope='Same official source/cutoff, prior B features/events vs repaired B; current GW10. Not a comparison across different weeks.',data_asof=after['data_asof'],players=rows),indent=2)+'\n')
    paths=['analysis/validate_b_team_goal_calibration.py','analysis/benchmark_b_search_limits.py','analysis/compare_current_b_repair.py','analysis/results/workload-recovered-v4/official_player_minutes.csv','checkpoints/season_2024_25_v1/manifest.json','scripts/b_horizon_eligibility.py','scripts/b_physical_workload.py','scripts/b_medical_return.py','scripts/build_current_b_inputs.py','scripts/mm_candidate_forecast.py','scripts/run_joint_gk_preview.py','src/fpl_v1_1_model/b_event_simulator.py','analysis/validate_b_integrated_repair.py','analysis/validate_b_workload_repair.py','analysis/validate_b_medical_return.py']
    proof=dict(source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in paths},evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(OUT.rglob('*'))if p.is_file()and p.name!='evidence.json'},production_changed=False)
    (OUT/'evidence.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(report,indent=2));print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
