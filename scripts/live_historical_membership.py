"""Recover only explicit official zero outcomes at archived registration clubs.

No absent player payload or unknown minutes are converted to zero. The
archived FPL stable code must identify the same current-season player.
"""
def recover_zero_club(snapshot,identity,stats,fixture):
    if not snapshot or not identity:return None
    if snapshot.get('code')!=identity.get('fpl_code'):return None
    for key in ('minutes','starts'):
        value=stats.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or value!=0:return None
    team=snapshot.get('team')
    if team not in (fixture.get('team_h'),fixture.get('team_a')):return None
    return int(team)
