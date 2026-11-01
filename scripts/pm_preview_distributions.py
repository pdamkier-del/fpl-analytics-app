"""Preview probabilities and TS scenarios from the exact aggregate PM draws.

One match simulation feeds point means, probabilities and aligned samples.
The collector only records scalar outcomes and consumes no random numbers.
These are empirical predictive distributions, not independently certified
parameter uncertainty or calibration. Production deployment remains separate.
"""
import numpy as np
from fpl_v1_1_model import joint_simulator as simulator


def simulate_with_distributions(inp, *, n=400, seed=93000000, include_samples=False):
    draws={p.player_id:[] for p in inp.players}
    def collect(result):
        for pid in draws:
            r=result[pid]
            draws[pid].append((r.minutes,r.started,r.points,r.goals-r.penalty_goals,r.penalty_goals,r.penalty_miss))
    aggregate=simulator.simulate_many(inp,n=n,seed=seed,on_match=collect)
    separated=any(p.penalty_fallback_weight is not None for p in inp.players)
    team_probability={}
    if separated:
        for team in (inp.home_team,inp.away_team):
            counts=np.sum([np.asarray(draws[p.player_id])[:,4]+np.asarray(draws[p.player_id])[:,5]for p in inp.players if p.team==team],axis=0)
            team_probability[team]=float(np.mean(counts>0))
    player_teams={p.player_id:p.team for p in inp.players}
    for pid,values in draws.items():
        minutes,started,points,ordinary,penalties,misses=np.asarray(values).T
        row=aggregate[pid]
        if float(points.mean())!=row['xPts'] or float(minutes.mean())!=row['expected_minutes']:
            raise ValueError('Preview distributions do not reproduce locked PM draws')
        row['distribution']={
            'draws':n,'p_start':float(started.mean()),
            'p_zero':float(np.mean(minutes==0)),
            'p_cameo':float(np.mean((minutes>0)&(started==0))),
            'p_60_plus':float(np.mean(minutes>=60)),'p_90':float(np.mean(minutes==90)),
            'minute_bins':[float(np.mean(minutes==0)),float(np.mean((minutes>0)&(minutes<60))),float(np.mean((minutes>=60)&(minutes<90))),float(np.mean(minutes==90))],
            'p_2_plus':float(np.mean(points>=2)),'p_5_plus':float(np.mean(points>=5)),'p_10_plus':float(np.mean(points>=10)),
            'points_interval80':[float(np.quantile(points,.1)),float(np.quantile(points,.9))],
            'pm_expected_minutes':float(minutes.mean())}
        if separated:
            row['penalty_components']={'team_simulated_p_at_least_one':team_probability[player_teams[pid]],'expected_nonpenalty_goals':float(ordinary.mean()),'expected_penalty_goals':float(penalties.mean()),'expected_missed_penalties':float(misses.mean()),'p_takes_penalty':float(np.mean(penalties+misses>0)),'p_scores_penalty':float(np.mean(penalties>0))}
        if include_samples:
            row['scenarios']={'minutes':minutes.astype(int).tolist(),'points':points.astype(int).tolist()}
    return aggregate
