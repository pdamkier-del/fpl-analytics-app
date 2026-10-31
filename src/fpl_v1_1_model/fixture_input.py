"""Single boundary from joined player/team/match data to existing mathematics.

No estimation or imputation happens here. All player features survive splitting
and joining; the established adapter still owns propensity conversion. The B
role/GK and NP stages subsequently refine this same MatchSimInput as before.
"""
from dataclasses import dataclass,replace
import numpy as np
import pandas as pd
from .paired_joint import build_pair
from .joint_simulator import MatchSimInput

KEY=('fixture_uuid','cutoff')
MATCH_FIELDS=('home_team_id','away_team_id','lambda_home_goals','lambda_away_goals','assist_probability_per_goal')
TEAM_FIELDS=('lambda_pen','team_pen_conversion')
PLAYER_NUMBERS=('control_p_start','control_xmins','start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench',
    'v4_workload_start_p_start','v4_workload_start_xmins','v4_start_minutes_mean','v4_cameo_minutes_mean','v4_p_cameo_given_bench',
    'goal_mu','assist_mu','mu_dc','dc_alpha','p_yellow','p_red','pen_weight','pen_conversion','bg_mean_rate90','bg_sd90')


@dataclass(frozen=True)
class FixtureTables:
    """Owned copies of source tables; no promise that DataFrames are immutable."""
    players: pd.DataFrame
    teams: pd.DataFrame
    match: pd.DataFrame


@dataclass(frozen=True)
class PreparedFixture:
    fixture_uuid: str
    cutoff: str
    tables: FixtureTables
    model_input: MatchSimInput
    own_goal_input_present: bool


def split_fixture_frame(frame):
    required=set(KEY+MATCH_FIELDS+TEAM_FIELDS+('player_uuid','team_id'))
    if required-set(frame):raise ValueError('Missing fixture contract fields: '+', '.join(sorted(required-set(frame))))
    if frame.empty:raise ValueError('Empty fixture input')
    excluded=set(MATCH_FIELDS+TEAM_FIELDS)
    players=frame[[c for c in frame if c not in excluded]].copy()
    teams=frame[list(KEY)+['team_id']+list(TEAM_FIELDS)].drop_duplicates().copy()
    match=frame[list(KEY)+list(MATCH_FIELDS)].drop_duplicates().copy()
    return FixtureTables(players,teams,match)


def join_fixture_tables(tables):
    """Reject ambiguous identity/clock/club joins; never fill missing features."""
    p,t,m=tables.players,tables.teams,tables.match
    for table in (p,t,m):
        if table.empty or set(KEY)-set(table):raise ValueError('Missing fixture identity/cutoff')
        if table.fixture_uuid.isna().any()or table.cutoff.isna().any():raise ValueError('Missing fixture identity/cutoff')
        if any(pd.Timestamp(v).tzinfo is None for v in table.cutoff):raise ValueError('Fixture cutoff must have timezone')
    if len(m)!=1 or p.fixture_uuid.nunique()!=1 or t.fixture_uuid.nunique()!=1:
        raise ValueError('One unique match context required')
    fixture=m.fixture_uuid.iloc[0];cut=pd.Timestamp(m.cutoff.iloc[0])
    if not p.fixture_uuid.eq(fixture).all()or not t.fixture_uuid.eq(fixture).all():raise ValueError('Fixture identity mismatch')
    for table in (p,t):
        if not pd.to_datetime(table.cutoff,utc=True,format='mixed').eq(cut).all():raise ValueError('Fixture cutoff mismatch')
    if set(MATCH_FIELDS)-set(m)or set(TEAM_FIELDS+('team_id',))-set(t)or {'player_uuid','team_id'}-set(p):
        raise ValueError('Incomplete player/team/match contract')
    if p.player_uuid.isna().any()or p.player_uuid.duplicated().any():raise ValueError('Duplicate/missing player identity')
    if t.team_id.isna().any()or t.team_id.duplicated().any():raise ValueError('Duplicate/missing team context')
    # Prevent an accidental second owner for any team/match feature.
    overlap=((set(p)&set(t))-set(KEY)-{'team_id'})|((set(p)&set(m))-set(KEY))|((set(t)&set(m))-set(KEY))
    if overlap or set(p)&set(MATCH_FIELDS+TEAM_FIELDS)or set(t)&set(MATCH_FIELDS):raise ValueError('Overlapping feature ownership')
    if set(PLAYER_NUMBERS+('pos','lambda_saves'))-set(p):raise ValueError('Incomplete player model features')
    if not p.pos.isin(['GK','GKP','DEF','MID','FWD']).all():raise ValueError('Unknown player position')
    if not np.isfinite(p[list(PLAYER_NUMBERS)].to_numpy(float)).all():raise ValueError('Unknown/nonfinite player feature')
    keeper=p.pos.isin(['GK','GKP'])
    if not np.isfinite(p.loc[keeper,'lambda_saves'].to_numpy(float)).all():raise ValueError('Unknown goalkeeper save input')
    if 'p_own_goal'in p and not np.isfinite(p.p_own_goal.to_numpy(float)).all():raise ValueError('Unknown own-goal input')
    home,away=m.home_team_id.iloc[0],m.away_team_id.iloc[0]
    if not np.isfinite([home,away]).all()or home!=int(home)or away!=int(away)or home==away:raise ValueError('Invalid match clubs')
    if p.team_id.isna().any()or not np.isfinite(t.team_id.to_numpy(float)).all():raise ValueError('Missing/invalid player club')
    if not np.equal(t.team_id.to_numpy(float),t.team_id.to_numpy(float).astype(int)).all():raise ValueError('Nonintegral club identity')
    if set(t.team_id)!={home,away}or set(p.team_id)!={home,away}:raise ValueError('Both exact match clubs required')
    values=np.r_[m[list(MATCH_FIELDS)].to_numpy(float).ravel(),t[list(TEAM_FIELDS)].to_numpy(float).ravel()]
    if not np.isfinite(values).all():raise ValueError('Unknown/nonfinite team or match value')
    if m[['lambda_home_goals','lambda_away_goals']].lt(0).any().any()or t.lambda_pen.lt(0).any():raise ValueError('Negative event intensity')
    if not m.assist_probability_per_goal.between(0,1).all()or not t.team_pen_conversion.between(0,1).all():raise ValueError('Invalid team probability')
    joined=p.merge(t.drop(columns='cutoff'),on=['fixture_uuid','team_id'],how='left',sort=False,validate='many_to_one',indicator=True)
    if not joined._merge.eq('both').all():raise ValueError('Missing player team context')
    joined=joined.drop(columns='_merge').merge(m.drop(columns='cutoff'),on='fixture_uuid',how='left',sort=False,validate='many_to_one')
    if joined.player_uuid.tolist()!=p.player_uuid.tolist():raise ValueError('Player ordering changed')
    return joined


def prepare_fixture_tables(tables,*,p_keeper_save_given_miss,bps_rules='2025-26'):
    frame=join_fixture_tables(tables)
    _,inp=build_pair(frame)
    by=frame.set_index('player_uuid');players=[];own_available='p_own_goal'in frame
    for p in inp.players:
        r=by.loc[p.player_id]
        kwargs=dict(penalty_weight=float(r.pen_weight),penalty_conversion=float(r.pen_conversion),
                    bps_background_mean=0.0,bps_background_sd=0.0,
                    bps_background_rate90=float(r.bg_mean_rate90),bps_background_sd90=float(r.bg_sd90))
        if own_available:kwargs['p_own_goal']=float(r.p_own_goal)
        players.append(replace(p,**kwargs))
    home=int(frame.home_team_id.iloc[0]);away=int(frame.away_team_id.iloc[0])
    h=frame[frame.team_id==home].iloc[0];a=frame[frame.team_id==away].iloc[0]
    model=replace(inp,players=tuple(players),lambda_home_penalties=float(h.lambda_pen),lambda_away_penalties=float(a.lambda_pen),
        home_penalty_conversion=float(h.team_pen_conversion),away_penalty_conversion=float(a.team_pen_conversion),
        p_penalty_save_given_miss=float(p_keeper_save_given_miss),bps_rules=bps_rules)
    return PreparedFixture(str(frame.fixture_uuid.iloc[0]),str(frame.cutoff.iloc[0]),tables,model,own_available)


def prepare_fixture(frame,*,p_keeper_save_given_miss,bps_rules='2025-26'):
    return prepare_fixture_tables(split_fixture_frame(frame),p_keeper_save_given_miss=p_keeper_save_given_miss,bps_rules=bps_rules)
