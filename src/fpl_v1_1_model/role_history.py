"""Reproducible role q/H using only completed team games before cutoff.

The core standing model's role-minute masses, start-led H and learned capacities
are retained. Explicit unknown substitute roles never enter starter-role history.
Half-lives are fixed before evaluation; no tuning against final holdout metrics.
"""
from collections import defaultdict
from math import log
from .role_classifier import ROLES


class RoleHistory:
    def __init__(self):
        self.games=defaultdict(list)

    def add_game(self,team,known_at,fixture,players):
        self.games[int(team)].append({'known_at':known_at,'fixture':fixture,'players':players})

    def before(self,team,cutoff):
        return sorted((g for g in self.games[int(team)] if g['known_at']<cutoff),
                      key=lambda g:(g['known_at'],g['fixture']))

    def state(self,team,cutoff,half_life=10):
        games=self.before(team,cutoff)
        minutes=defaultdict(lambda:defaultdict(float));starts=defaultdict(lambda:defaultdict(float))
        totals=defaultdict(float);cap_mass=defaultdict(float);den=0.;players=set()
        disagreements=defaultdict(float);appearance_evidence=defaultdict(float)
        for lag,g in enumerate(reversed(games)):
            weight=2**(-lag/half_life);den+=weight
            for p in g['players']:
                pid=str(p['player_uuid']);role=p.get('role')
                players.add(pid)
                if role not in ROLES or not p.get('started'): continue
                minutes[pid][role]+=weight*min(1.35,max(0,float(p['minutes']))/90)
                starts[pid][role]+=weight;totals[role]+=weight;cap_mass[role]+=weight
                disagreements[pid]+=weight*bool(p.get('disagreement'))
                appearance_evidence[pid]+=weight
        capacities={r:cap_mass[r]/den if den else 0. for r in ROLES}
        states={}
        for pid in players:
            mass=minutes[pid];seen=[r for r in mass if mass[r]>0]
            if not seen:
                states[pid]={'q':{},'H':{},'evidence':0.,'disagreement_share':0.};continue
            allowed=['GK'] if seen==['GK'] else [r for r in ROLES if r!='GK']
            qden=sum(mass.get(r,0)+.05 for r in allowed)
            q={r:(mass.get(r,0)+.05)/qden for r in allowed}
            H={}
            for role in allowed:
                candidates=sum(1 for other in players if starts[other].get(role,0)>0)
                hden=totals[role]+.1*max(1,candidates)
                H[role]=min(.995,capacities[role]*(starts[pid].get(role,0)+.1)/hden) if starts[pid].get(role,0)>0 and hden else 0.
            states[pid]={'q':q,'H':H,'evidence':sum(mass.values()),
                         'disagreement_share':disagreements[pid]/appearance_evidence[pid] if appearance_evidence[pid] else 0.}
        return states,capacities,games


def summarize_state(state,capacities):
    q=state.get('q',{});H=state.get('H',{})
    return {'role_fit':sum(v*min(1,capacities.get(r,0)) for r,v in q.items()),
            'role_h':sum(v*H.get(r,0) for r,v in q.items()),
            'role_qmax':max(q.values()) if q else 0.,
            'role_evidence':log(1+state.get('evidence',0)),
            'role_entropy':-sum(v*log(v) for v in q.values() if v>0),
            'history_disagreement_share':state.get('disagreement_share',0)}
