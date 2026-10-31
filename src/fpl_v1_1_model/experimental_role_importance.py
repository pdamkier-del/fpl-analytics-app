"""B-only provider competition normalization for existing importance math.

No completed-season future calendar or knockout progress is reconstructed.
Known past participation supplies competition context; missing opponent Elo
remains neutral. The original production normalizer is unchanged.
"""
from .match_importance import (BASE_COMPETITION_VALUES,canonical_competition,
    premier_league_stage_strength,knockout_stage_strength)
from .pstart_v2 import match_importance

ALIASES={'cl':'champions-league','el':'europa-league','conf':'conference-league',
         'conf_qual':'conference-league','fa':'fa-cup','efl':'efl-cup'}


def competition_name(value):
    key=str(value or '').strip().lower()
    result=canonical_competition(ALIASES.get(key,key))
    if result not in BASE_COMPETITION_VALUES:raise ValueError('Unknown role competition: '+key)
    return result


def stage_strength(competition,round_name,month):
    comp=competition_name(competition)
    if comp=='prem':return premier_league_stage_strength(int(round_name))
    # The shared legacy helper checks substring "final" before "semi" and
    # "quarter". Resolve the more specific stages before reusing its fallback.
    label=str(round_name or '').lower()
    if 'semi' in label:return .88
    if 'quarter' in label:return .76
    return knockout_stage_strength(round_name,month)


def importance(competition,round_name,month,active):
    comp=competition_name(competition)
    return match_importance(competition=comp,active_competitions=sorted({competition_name(c)for c in active}|{comp}),
        round_strength=stage_strength(comp,round_name,month),opponent_strength=.5,
        base_values=BASE_COMPETITION_VALUES)
