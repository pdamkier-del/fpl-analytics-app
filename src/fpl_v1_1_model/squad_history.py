"""Historical squad-selection evidence; not injury/medical availability labels."""
from collections import defaultdict
from math import log1p

SQUAD_FEATURES=[f'{name}_{speed}' for speed in ('fast','slow')
                for name in ('squad_rate','squad_evidence','bench_sub_rate','bench_evidence')]+['last_squad','last_bench']


def squad_label(listed,actual_started,minutes,complete,withdrawn=False):
    """Positive appearance proves membership; absence requires a complete list.

    None is unknown, never an inferred injured/unavailable label.
    """
    if actual_started or minutes>0:return 1
    if withdrawn:return None
    if listed:return 1
    return 0 if complete else None


class SquadHistory:
    def __init__(self):self.games=defaultdict(list)

    def add_game(self,team,known_at,fixture,players):
        self.games[int(team)].append({'known_at':known_at,'fixture':fixture,'players':players})

    def state(self,team,cutoff):
        games=sorted((g for g in self.games[int(team)] if g['known_at']<cutoff),key=lambda g:(g['known_at'],g['fixture']))
        people=set(p for g in games for p in g['players']);out={}
        for pid in sorted(people):
            features={};latest=None
            for speed,half in [('fast',3),('slow',10)]:
                squad=total=bench=apps=0.
                for lag,g in enumerate(reversed(games)):
                    p=g['players'].get(pid)
                    # No Core record means not registered at this team/fixture,
                    # not an inferred squad absence before registration/transfer.
                    if p is None or p['squad'] is None:continue
                    weight=2**(-lag/half);total+=weight;squad+=weight*p['squad']
                    if latest is None:latest=p
                    if p['squad'] and not p['started']:
                        bench+=weight;apps+=weight*(p['minutes']>0)
                features[f'squad_rate_{speed}']=(squad+1)/(total+2)
                features[f'squad_evidence_{speed}']=log1p(total)
                features[f'bench_sub_rate_{speed}']=(apps+1)/(bench+2)
                features[f'bench_evidence_{speed}']=log1p(bench)
            features['last_squad']=float(latest['squad']) if latest else .5
            features['last_bench']=float(latest['squad'] and not latest['started']) if latest else .5
            out[pid]=features
        return out,games[-1]['known_at'] if games else None


def unknown_state():
    return {f:0. if 'evidence' in f else .5 for f in SQUAD_FEATURES}
