"""Explicit B-GK preview: v1 joint minutes plus optional v2 role allocation.

Reuse B's start calibration and its strength-five empirical duration shrinkage.
The pooled unlisted keeper is a competing outcome, not a fabricated FPL player.
"""
from dataclasses import replace
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from fpl_v1_1_model.joint_simulator import PlayerSimInput, validate_joint_goalkeepers

VERSION = 'B-GK-role-aware-v2'
UNKNOWN = '__unlisted_goalkeeper__:'
SUPPORT = np.arange(91)


def observations(root):
    with sqlite3.connect(f'file:{root / "work/core.sqlite3"}?mode=ro', uri=True) as db:
        f = pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,fpl_position,started,minutes,kickoff_at FROM player_fixture_observations WHERE is_final=1 AND fpl_position IN ('GK','GKP','G')", db)
    f['known_at'] = pd.to_datetime(f.kickoff_at, utc=True, format='mixed') + pd.to_timedelta(np.where(f.season.eq('2024-25'),4,3),unit='h')
    live = root/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz'
    if live.exists():
        g = pd.read_csv(live, low_memory=False)
        g = g[g.fpl_position.isin(['GK','GKP','G'])].copy()
        g['known_at'] = pd.to_datetime(g.available_at, utc=True)
        if 'season' not in g: g['season'] = '2026-27'
        f = pd.concat([f,g[f.columns]],ignore_index=True)
    f = f.drop_duplicates(['season','fixture_uuid','player_uuid'])
    return f


class DurationHistory:
    def __init__(self, obs, cutoff):
        cutoff = pd.Timestamp(cutoff)
        self.cutoff = cutoff
        past = obs[pd.to_datetime(obs.known_at,utc=True,format='mixed').lt(cutoff) & obs.started.eq(1) & obs.minutes.between(1,90)].copy()
        if len(past) < 100: raise ValueError('Not Available: fewer than100 prior goalkeeper starts')
        age = (cutoff-pd.to_datetime(past.known_at,utc=True,format='mixed')).dt.total_seconds()/86400
        past['weight'] = np.exp2(-age/180.)
        self.prior = np.bincount(past.minutes.astype(int),weights=past.weight,minlength=91)
        self.prior /= self.prior.sum()
        self.personal = {(str(p),int(t)):g for (p,t),g in past.groupby(['player_uuid','team_id'])}
        self.latest = str(pd.to_datetime(past.known_at,utc=True,format='mixed').max())
        self.rows = len(past)

    def pmf(self, pid, team):
        past = self.personal.get((str(pid),int(team)))
        counts = np.zeros(91) if past is None else np.bincount(past.minutes.astype(int),weights=past.weight,minlength=91)
        mass = (5*self.prior+counts)/(5+counts.sum())
        mass[0] = 0
        return tuple(map(float,mass/mass.sum()))


def marginals(keepers):
    """Exact unconditional minute PMFs of the joint starter/replacement process."""
    answer = {p.player_id:np.zeros(91) for p in keepers}
    for starter in keepers:
        if starter.p_start == 0: continue
        mass = np.asarray(starter.goalkeeper_start_pmf)
        if mass.shape != (91,): raise ValueError('Missing empirical goalkeeper duration PMF')
        answer[starter.player_id] += starter.p_start*mass
        reserves = [p for p in keepers if p.player_id != starter.player_id and p.p_cameo_given_bench > 0]
        total = sum(p.p_cameo_given_bench for p in reserves)
        if mass[:90].sum() > 0 and not reserves: raise ValueError('Missing replacement coverage')
        for reserve in reserves:
            # A 90-minute starter creates no substitute appearance.
            answer[reserve.player_id][1:90] += starter.p_start*reserve.p_cameo_given_bench/total*mass[89:0:-1]
    for mass in answer.values():
        mass[0] = max(0.,1-mass[1:].sum())
        if not np.isclose(mass.sum(),1,atol=1e-9): raise ValueError('GK marginal is not normalized')
    if not np.isclose(sum(v@SUPPORT for v in answer.values()),90,atol=1e-8): raise ValueError('GK marginals do not conserve90')
    return answer


def prepare(inp, rows, duration, *, incomplete_teams=(), role_policy=None, season=None):
    """Add an explicit reserve/competitor pool and return exact MM marginals.

    B projected start probabilities remain for multiple represented viable GKs.
    For a lone viable keeper or known unlisted competitors, keep the original
    MM probability before available-roster projection. A B calibrator trained
    on already-normalized features cannot undo that missing-competitor bias.
    Historical capsules without that upstream field retain their stored raw B
    calibration; the replay records any marginal change.
    V2 optionally reallocates unsupported outsider mass when verified role
    history establishes one fully available candidate. Otherwise retain v1.
    Unlisted keepers are never attached to guessed individual FPL identities.
    """
    by = rows.set_index('player_uuid')
    output = [p for p in inp.players if not p.is_keeper]
    moments = {}; teams = []
    for team in (inp.home_team,inp.away_team):
        original = [p for p in inp.players if p.is_keeper and p.team == team]
        horizon_out={p.player_id for p in original if role_policy is not None and bool(by.loc[p.player_id].get('role_horizon_absence',False))}
        original=[replace(p,p_start=0.,p_cameo_given_bench=0.)if p.player_id in horizon_out else p for p in original]
        viable = [p for p in original if p.p_start > 0 or p.p_cameo_given_bench > 0]
        partial = len(viable) <= 1 or str(team) in set(map(str,incomplete_teams))
        weights = {}
        for p in original:
            raw = float(by.loc[p.player_id].get('new_p_start',by.loc[p.player_id].get('unprojected_p',p.p_start))) if partial else p.p_start
            if p not in viable: raw = 0.
            # Preserve explicit predeadline availability caps.
            cap = 0. if p.player_id in horizon_out else float(by.loc[p.player_id].get('availability_cap',1.))
            weights[p.player_id] = min(max(raw,0.),cap)
        total = sum(weights.values())
        if total > 1:
            weights = {pid:v/total for pid,v in weights.items()}
        missing = max(0.,1-sum(weights.values()))
        role_context={'applied':False,'reason':'v1_reference'}
        if role_policy is not None:
            team_rows=rows[rows.player_uuid.isin([p.player_id for p in original])].copy()
            role_context_rows=team_rows.copy()
            role_context_rows.loc[role_context_rows.player_uuid.isin(horizon_out),'availability_cap']=0.
            weights,missing,role_context=role_policy.allocate(season,team,role_context_rows,duration.cutoff,weights,missing)
        if not viable and missing != 1: raise ValueError('Invalid empty goalkeeper set')
        players = []
        for p in original:
            pmf = duration.pmf(p.player_id,int(team))
            # Selection weight, not independent bench appearance probability.
            reserve = max(p.p_cameo_given_bench,p.p_start) if p in viable else 0.
            players.append(replace(p,p_start=weights[p.player_id],start_minutes_mean=float(np.asarray(pmf)@SUPPORT),
                goalkeeper_start_pmf=pmf,p_cameo_given_bench=reserve))
        # Always retain a fallback for the physical position if a reserve is
        # unlisted. It has zero starter mass for a represented competitive set.
        # Its event rates reuse the existing team's keeper opportunity model.
        template = max(viable or original,key=lambda p:p.p_start) if original else None
        if template is None: raise ValueError('Not Available: no team keeper event rates')
        pool = replace(template,player_id=UNKNOWN+str(team),p_start=missing,
            p_cameo_given_bench=1. if len(viable)<2 else 0.,
            goalkeeper_start_pmf=duration.pmf('unlisted',int(team)),goal_weight=0.,assist_weight=0.,penalty_weight=0.)
        pool = replace(pool,start_minutes_mean=float(np.asarray(pool.goalkeeper_start_pmf)@SUPPORT))
        players.append(pool)
        validate_joint_goalkeepers(players,str(team),(str(team),))
        mass = marginals(players)
        for p in players:
            f = mass[p.player_id]; start = np.asarray(p.goalkeeper_start_pmf)
            appearance = float(1-f[0]); reserve_probability = max(0.,appearance-p.p_start)
            reserve_mean_total = float(f@SUPPORT-p.p_start*(start@SUPPORT))
            q = reserve_probability/(1-p.p_start) if p.p_start < 1 else 0.
            c = reserve_mean_total/reserve_probability if reserve_probability > 1e-12 else 1.
            moments[p.player_id] = dict(p=p.p_start,q=float(np.clip(q,0,1)),s=float(start@SUPPORT),c=max(1.,c),
                x=float(f@SUPPORT),p60=float(f[60:].sum()),p90=float(f[90]),p_play=appearance,pmf=f.tolist())
        teams.append(dict(team=str(team),known_viable=len(viable),unlisted_start_probability=missing,
            unlisted_expected_minutes=moments[pool.player_id]['x'],partial_roster=partial,start_source='verified_sole_candidate_role'if role_context.get('applied')else('original_MM_before_roster_projection' if partial and 'new_p_start' in rows else 'B_calibrated_marginals'),
            role_allocation=role_context,horizon_absent=sorted(horizon_out),analytic_gk_minutes=sum(moments[p.player_id]['x'] for p in players)))
        output.extend(players)
    return replace(inp,players=tuple(output),experimental_joint_goalkeepers=True,
        verified_goalkeeper_roster_teams=(inp.home_team,inp.away_team),experimental_joint_starters=True),moments,teams
