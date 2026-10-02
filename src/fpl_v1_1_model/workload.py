"""Observed official-match workload, separate from Match Importance.

Minutes may include extra time (0..120). Unknown/missing observations are not
zero-minute outcomes. Historical reconstruction uses an explicit available_at;
live callers must supply their real publication timestamp instead.
"""
from collections import defaultdict
from datetime import datetime
import math

WORKLOAD_FEATURES = [
    'work_minutes_7d', 'work_minutes_14d', 'work_minutes_28d',
    'work_starts_7d', 'work_starts_14d', 'work_decay_3d', 'work_decay_7d',
    'work_player_rest_days', 'work_player_history_missing',
    'work_team_matches_7d', 'work_team_matches_14d',
    'work_team_nonpl_matches_7d', 'work_team_rest_days',
    'work_missing_player_stats_14d',
]


def timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Workload timestamps must be timezone aware')
    return value


class WorkloadHistory:
    def __init__(self):
        self.games = defaultdict(list)
        self.keys = set()

    def add_game(self, team, match, kickoff, available_at, competition, players,
                 player_stats_complete):
        kickoff, available_at = timestamp(kickoff), timestamp(available_at)
        if available_at < kickoff:
            raise ValueError('Outcome cannot be available before kickoff')
        key = (int(team), str(match))
        if key in self.keys:
            raise ValueError('Duplicate team-match workload record')
        for p in players.values():
            m = float(p['minutes'])
            if not math.isfinite(m) or not 0 <= m <= 120:
                raise ValueError('Invalid workload minutes')
            if p['started'] is not None and p['started'] not in (True, False):
                raise ValueError('Invalid start label')
        self.keys.add(key)
        self.games[int(team)].append((kickoff, available_at, str(match),
                                     competition, players, bool(player_stats_complete)))

    def state(self, team, cutoff):
        cutoff = timestamp(cutoff)
        games = sorted((g for g in self.games[int(team)] if g[1] < cutoff),
                       key=lambda g: (g[0], g[2]))
        team_values = {k: 0. for k in WORKLOAD_FEATURES}
        team_values['work_player_rest_days'] = 28.
        team_values['work_player_history_missing'] = 1.
        team_values['work_team_rest_days'] = 28.
        for ko, known, match, comp, players, complete in games:
            age = (cutoff-ko).total_seconds()/86400
            if age < 0:
                raise ValueError('Available future outcome')
            for window in (7, 14):
                if age <= window:
                    team_values[f'work_team_matches_{window}d'] += 1
            if age <= 7 and comp != 'prem':
                team_values['work_team_nonpl_matches_7d'] += 1
            if age <= 14 and not complete:
                team_values['work_missing_player_stats_14d'] += 1
            team_values['work_team_rest_days'] = min(team_values['work_team_rest_days'], age)
        state = {}
        for ko, known, match, comp, players, complete in games:
            age = (cutoff-ko).total_seconds()/86400
            for pid, observation in players.items():
                values = state.setdefault(pid, team_values.copy())
                minutes = float(observation['minutes'])
                for window in (7, 14, 28):
                    if age <= window:
                        values[f'work_minutes_{window}d'] += minutes
                for window in (7, 14):
                    if age <= window and observation['started'] is True:
                        values[f'work_starts_{window}d'] += 1
                for half in (3, 7):
                    values[f'work_decay_{half}d'] += minutes * 2**(-age/half)
                if minutes > 0:
                    values['work_player_history_missing'] = 0.
                    values['work_player_rest_days'] = min(values['work_player_rest_days'], age)
        return state, team_values, max((g[1] for g in games), default=None)
