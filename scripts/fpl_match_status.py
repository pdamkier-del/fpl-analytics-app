"""Official completed-match evidence, including provisional full-time results.
Keeps the existing kickoff + four hours availability proxy for model inputs.
"""
from datetime import datetime, timedelta, timezone

def played(fixture):
    return fixture.get('finished') is True or (fixture.get('finished_provisional') is True and fixture.get('started') is True and fixture.get('minutes') == 90)

def cutoff_safe(fixture, cutoff):
    if not played(fixture):
        return False
    kickoff=fixture.get('kickoff_time') or fixture.get('kickoff')
    if not kickoff:
        return False
    ko=datetime.fromisoformat(kickoff.replace('Z','+00:00'))
    at=datetime.fromisoformat(cutoff.replace('Z','+00:00')) if isinstance(cutoff,str) else cutoff
    if ko.tzinfo is None or at.tzinfo is None:
        raise ValueError('Naive match availability timestamp')
    return ko.astimezone(timezone.utc)+timedelta(hours=4)<at.astimezone(timezone.utc)
