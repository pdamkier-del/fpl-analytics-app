"""Prior-only evidence for the opt-in joint role assignment candidate.

No target lineups, names, outcomes or future competition participation are
inferred. A missing tactical history is reported and leaves B unchanged.
"""
from collections import defaultdict

import pandas as pd

from .role_history import RoleHistory
from .role_classifier import ROLES
from .xi_assignment import formation_slots
from .experimental_role_importance import competition_name,importance


class AssignmentHistory:
    def __init__(self, classified, *, clock_hours=3):
        required={'season','fixture_uuid','team_id','player_uuid','kickoff','formation','final_role','minutes'}
        if required-set(classified):
            raise ValueError('Missing classified role identity')
        self.history={}
        self.formations=defaultdict(list)
        self.excluded=[]
        pending=[]
        for (season,team,fixture),g in classified.groupby(['season','team_id','fixture_uuid'],sort=True):
            forms=g.formation.dropna().unique()
            if len(g)!=11 or g.player_uuid.duplicated().any() or len(forms)!=1:
                self.excluded.append((str(season),int(team),str(fixture),'incomplete XI'))
                continue
            form=str(forms[0])
            try:
                formation_slots(form)
            except (ValueError,AssertionError):
                self.excluded.append((str(season),int(team),str(fixture),'unsupported formation'))
                continue
            if not g.final_role.isin(ROLES).all() or (g.final_role=='GK').sum()!=1:
                raise ValueError('Invalid classified XI roles')
            if g.kickoff.nunique()!=1:
                raise ValueError('Conflicting role kickoff')
            # Keep actual receipts when supplied; proxies are explicit otherwise.
            if 'known_at' in g:
                clocks=pd.to_datetime(g.known_at,utc=True,format='mixed')
                if clocks.isna().any():
                    self.excluded.append((str(season),int(team),str(fixture),'unknown receipt clock'))
                    continue
                known=clocks.max()
            else:
                known=pd.Timestamp(g.kickoff.iloc[0])+pd.Timedelta(hours=clock_hours)
            if known<pd.Timestamp(g.kickoff.iloc[0]):
                raise ValueError('Role receipt precedes kickoff')
            imp=float(g.importance.iloc[0]) if 'importance' in g else 1.
            if not 0<=imp<=1 or ('importance' in g and g.importance.nunique()!=1):
                raise ValueError('Invalid historical match importance')
            if g.minutes.isna().any() or not g.minutes.between(0,130).all():
                self.excluded.append((str(season),int(team),str(fixture),'unknown/invalid minutes'))
                continue
            # Only observed starter minutes enter q; H counts confirmed starts.
            players=[dict(player_uuid=str(r.player_uuid),role=r.final_role,
                          started=True,minutes=float(r.minutes)) for r in g.itertuples()]
            comp=competition_name(g.competition.iloc[0])if 'competition'in g else None
            if comp is not None and (g.competition.nunique()!=1 or 'round_name'not in g or g.round_name.nunique(dropna=False)!=1):
                raise ValueError('Missing/conflicting role competition stage')
            pending.append((known,str(season),int(team),str(fixture),players,form,imp,comp,
                            g.round_name.iloc[0]if comp is not None else None,pd.Timestamp(g.kickoff.iloc[0]).month))
        active=defaultdict(lambda:{'prem','fa-cup','efl-cup'})
        for known,season,team,fixture,players,form,imp,comp,round_name,month in sorted(pending,key=lambda r:(r[0],r[1],r[2],r[3])):
            if comp is not None:
                active[season,team].add(comp)
                imp=importance(comp,round_name,month,active[season,team])
            hist=self.history.setdefault(season,RoleHistory())
            hist.add_game(team,known,fixture,players,importance=imp,competition=comp)
            self.formations[(season,team)].append((known,fixture,form))

    def evidence(self, season, team, cutoff):
        cut=pd.Timestamp(cutoff)
        hist=self.history.get(str(season))
        if hist is None:
            return None
        states,_,games=hist.state(int(team),cut,half_life=10,
                                  q_importance_scale=.25,h_importance_scale=1.)
        past=sorted((r for r in self.formations[(str(season),int(team))] if r[0]<cut))
        if not past:
            return None
        weights=defaultdict(float)
        for lag,(_,_,form) in enumerate(reversed(past[-12:])):
            weights[form]+=2**(-lag/5.)
        return dict(states=states,formations=dict(weights),games=len(games),
                    max_known_at=past[-1][0].isoformat(),
                    active_competitions=sorted({'prem','fa-cup','efl-cup'}|{g['competition']for g in games if g.get('competition')}))
