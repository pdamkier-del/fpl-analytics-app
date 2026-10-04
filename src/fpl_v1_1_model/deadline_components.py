"""Versioned player component state at one common deadline, without refitting.

History availability is supplied explicitly by the caller. First entrants use
current-season position priors only after roster evidence has been verified.
This is an input-contract extension, not a replacement for archived forecasts.
"""
import numpy as np
import pandas as pd

from .attack import shrunk_rate_per90
from .negative_events import competing_card_probabilities


def weighted_totals(frame, event, half_life):
    if frame.empty:
        return 0.0, 0.0
    w=2.0**(-np.arange(len(frame)-1,-1,-1)/float(half_life))
    return float(np.dot(w,frame[event])),float(np.dot(w,frame.minutes))


def player_components_at_deadline(history, roster, cutoff, *, attack, dc, discipline, season='2025-26'):
    """Return common event rates and control-exposure DC/card predictions.

Required roster: fixture_uuid, player_uuid, team_id, opponent_team_id, pos,
expected_minutes, evidence_at. No candidate minutes or targets are read.
Required history: current-season completed rows with explicit available_at.
"""
    cutoff=pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError('Timezone-aware cutoff required')
    r=roster.copy();h=history.copy()
    if r.empty or r[['fixture_uuid','player_uuid']].duplicated().any():
        raise ValueError('Unique nonempty target roster required')
    evidence=pd.to_datetime(r.evidence_at,utc=True,errors='raise')
    if evidence.isna().any() or (evidence>cutoff).any():
        raise ValueError('Predeadline roster evidence required for every target')
    if not r.pos.isin(['GK','GKP','DEF','MID','FWD']).all():
        raise ValueError('Verified FPL positions required')
    minutes=r.expected_minutes.to_numpy(float)
    if not np.isfinite(minutes).all() or ((minutes<0)|(minutes>90+1e-8)).any():
        raise ValueError('Invalid target expected minutes')
    h['available_at']=pd.to_datetime(h.available_at,utc=True,errors='raise')
    h['kickoff_at']=pd.to_datetime(h.kickoff_at,utc=True,errors='raise')
    if h.available_at.isna().any() or h.kickoff_at.isna().any() or (h.available_at<h.kickoff_at).any():
        raise ValueError('Valid history availability time required')
    h=h[(h.available_at<=cutoff)&(h.season==season)].copy()
    h['fpl_position']=h.fpl_position.replace({'GKP':'GK'})
    if discipline['opponent_yellow_factor'] is not False:
        raise ValueError('This contract preserves the original no-opponent discipline candidate')
    if h[['fixture_uuid','player_uuid']].duplicated().any():
        raise ValueError('Logically deduplicated history required')
    if set(r.fixture_uuid)&set(h.fixture_uuid):
        raise ValueError('Target fixture outcomes cannot enter component history')
    fields=['minutes','xg','xa','defcon_count','yellow_cards','fpl_red_cards']
    values=h[fields].to_numpy(float)
    if not np.isfinite(values).all() or (values<0).any():
        raise ValueError('Missing/invalid historical events must not become zero')
    h=h.sort_values(['kickoff_at','fixture_uuid','team_id','player_uuid'])
    population={p:g for p,g in h.groupby('fpl_position',sort=False)}
    players={p:g for p,g in h.groupby('player_uuid',sort=False)}
    # Each team/position side induces DC actions from its opponent.
    sides=h.groupby(['kickoff_at','fixture_uuid','team_id','opponent_team_id','fpl_position'],sort=True).defcon_count.sum().reset_index()
    induced={}
    league_induced={}
    decay=2.0**(-1.0/float(dc['opponent_induced_half_life']))
    for s in sides.itertuples(index=False):
        key=(int(s.opponent_team_id),s.fpl_position)
        weight,total=induced.get(key,(0.0,0.0))
        induced[key]=(weight*decay+1.0,total*decay+s.defcon_count)
        total,count=league_induced.get(s.fpl_position,(0.0,0))
        league_induced[s.fpl_position]=(total+s.defcon_count,count+1)
    out=[]
    for row in r.itertuples(index=False):
        pos='GK' if row.pos=='GKP' else row.pos
        group=population.get(pos,h.iloc[:0]);individual=players.get(row.player_uuid,h.iloc[:0])
        exposure=float(group.minutes.sum())
        if exposure<=0:
            raise ValueError('No observed current-season position exposure for '+pos)
        rates={}
        for kind,event in [('goal','xg'),('assist','xa')]:
            p=attack[kind];num,den=weighted_totals(individual,event,p['recency_half_life'])
            prior=90.0*float(group[event].sum())/exposure
            rates[kind]=shrunk_rate_per90(num,den,prior,p['current_season_position_prior_minutes_tau'])
        if pos=='GK':
            dc_rate=0.0;factor=1.0;alpha=0.0
        else:
            num,den=weighted_totals(individual,'defcon_count',dc['player_dc_half_life'])
            prior=90.0*float(group.defcon_count.sum())/exposure
            dc_rate=shrunk_rate_per90(num,den,prior,dc['position_prior_minutes_tau'])
            weight,total=induced.get((int(row.opponent_team_id),pos),(0.0,0.0))
            lt,ln=league_induced.get(pos,(0.0,0));league=lt/ln if ln else 1.0
            opponent=total/weight if weight else league
            factor=max(.25,min(4.0,opponent/max(.1,league)))**dc['opponent_factor_exponent_gamma']
            alpha=dc['nb2_dispersion_alpha'][pos]
        # Preserve the original recommended joint discipline specification:
        # yellow shrunk to position; red effectively position-only; no opponent factor.
        pm=float(individual.minutes.sum())
        yr=max(1e-10,shrunk_rate_per90(float(individual.yellow_cards.sum()),pm,
            90.0*float(group.yellow_cards.sum())/exposure,discipline['yellow_prior_minutes_tau']))
        rr=max(1e-10,shrunk_rate_per90(float(individual.fpl_red_cards.sum()),pm,
            90.0*float(group.fpl_red_cards.sum())/exposure,1e9))
        cards=competing_card_probabilities(row.expected_minutes,yr,rr)
        out.append(dict(fixture_uuid=row.fixture_uuid,player_uuid=row.player_uuid,
            cutoff=cutoff.isoformat(),goal_rate90=rates['goal'],assist_rate90=rates['assist'],
            dc_rate90=dc_rate,dc_opponent_factor=factor,
            mu_dc=row.expected_minutes/90.0*dc_rate*factor,dc_alpha=alpha,
            yellow_rate90=yr,red_rate90=rr,p_yellow=cards.yellow,p_red=cards.red,
            cold_start=individual.empty,history_rows=len(individual),
            history_latest_available_at=h.available_at.max().isoformat() if len(h) else None))
    return pd.DataFrame(out)
