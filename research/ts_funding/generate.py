"""New finite domains, generated only after protocol/candidate lock.

Independent integer synthetic payoffs, not calibrated football event simulations.
No import or read of the 42 development fixtures.
"""
import random

FAMILIES = ('independent', 'fixture_windows', 'club_exchange',
            'sale_rounding', 'correlated_absence', 'near_ties')
SEED = 202611220317


def cases():
    result = []
    positions = [1]*2 + [2]*5 + [3]*5 + [4]*3
    for family_index, family in enumerate(FAMILIES):
        for replicate in range(8):
            rng = random.Random(SEED + 1000*family_index + replicate)
            extra_positions = rng.sample([1, 2, 3, 4], 2)
            draws = 8 if family == 'correlated_absence' else 1
            players = []
            for i, position in enumerate(positions + extra_positions, 1):
                price = rng.randrange(4, 13)*10
                purchase = price
                if family == 'sale_rounding' and i <= 15:
                    purchase = price + rng.choice([-11, -5, -1, 0, 3, 9])
                base = rng.randint(1, 12)
                if family == 'near_ties':
                    base = rng.choice([4, 5])
                points, minutes = [], []
                for g in range(6):
                    level = base
                    if family == 'fixture_windows':
                        level = max(0, base + (5 if (g+i)%3 == 0 else -3))
                    ps, ms = [], []
                    for d in range(draws):
                        absent = family == 'correlated_absence' and (d + g + i%4)%4 == 0
                        ms.append(0 if absent else (59 if d%3 == 1 else 90))
                        ps.append(0 if absent else level)
                    points.append(ps); minutes.append(ms)
                # First XV has exactly three per club; extras can require a joint exchange.
                team = (i-1)//3 + 1 if family == 'club_exchange' else (i-1)%10 + 1
                if i > 15 and family == 'club_exchange':
                    team = rng.randint(1, 5)
                players.append(dict(id=i, position=position, team=team,
                                    price=price, purchase=purchase,
                                    points=points, minutes=minutes))
            result.append(dict(id=f'H{family_index+1}-{replicate+1:02}',
                               family=family, level='heldout', players=players,
                               initial_ids=list(range(1, 16)),
                               bank=rng.choice([0, 0, 5, 10, 20]),
                               free_transfers=replicate%6,
                               nomination_domain='frozen ScenarioScorer policy only'))
    return result
