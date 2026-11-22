"""Pure FPL point accounting shared by match scoring and component exports.

Event generation, minutes and BPS/bonus remain owned by their existing models.
Penalty-miss points are a diagnostic subset of negative points, never an extra
charge. A nonappearance produces zero points for every component.
"""
from .keeper import save_points
from .negative_events import direct_negative_points

GOAL_POINTS={"GK":10,"GKP":10,"DEF":6,"MID":5,"FWD":4}
CS_POINTS={"GK":4,"GKP":4,"DEF":4,"MID":1,"FWD":0}


def point_components(position, is_keeper, events):
    """Return the existing aggregate component names for one sampled outcome."""
    components=dict(appearance_pts=0,goal_pts=0,assist_pts=0,cs_pts=0,
                    save_pts=0,penalty_save_pts=0,dc_pts=0,negative_pts=0,
                    gc_pts=0,penalty_miss_pts=0)
    if events.minutes<=0:
        return components
    components.update(
        appearance_pts=2 if events.minutes>=60 else 1,
        goal_pts=GOAL_POINTS[position]*events.goals,
        assist_pts=3*events.assists,
        cs_pts=CS_POINTS[position]*events.clean_sheet,
        save_pts=save_points(events.saves) if is_keeper else 0,
        penalty_save_pts=5*events.penalty_saves if is_keeper else 0,
        dc_pts=events.dc_points,
        negative_pts=direct_negative_points(yellow=events.yellow,red=events.red,
            own_goal=events.own_goal,penalty_miss=events.penalty_miss),
        gc_pts=-(events.goals_conceded_while_on_pitch//2) if position in ('GK','GKP','DEF') else 0,
        penalty_miss_pts=-2*events.penalty_miss)
    return components


def nonbonus_total(components):
    """Penalty misses already belong to negative_pts; bonus is awarded jointly."""
    return sum(value for name,value in components.items() if name!='penalty_miss_pts')
