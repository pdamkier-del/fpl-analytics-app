"""Protocol-defined states. Call only after execution registration/freeze."""
from collections import Counter
import numpy as np

def generate(f,eligible):
    players={p['id']:p for p in f['players']};seen=set();cases=[]
    pool={position:sorted(pid for pid in eligible if players[pid]['position']==position)for position in range(1,5)}
    for j,(ft,bank)in enumerate([(1,0),(1,10),(2,0),(2,10)]):
        for k in range(3):
            seed=202611230501+3*j+k;rng=np.random.Generator(np.random.PCG64(seed))
            record=dict(id=len(cases)+1,stratum=j,replicate=k,seed=seed,bank=bank,free_transfers=ft,chips_available=[],status='generation_failed')
            for attempt in range(1,10001):
                if any(len(pool[p])<n for p,n in [(1,2),(2,5),(3,5),(4,3)]):break
                ids=tuple(sorted(int(pid)for p,n in [(1,2),(2,5),(3,5),(4,3)]for pid in rng.choice(pool[p],size=n,replace=False)))
                if ids in seen or max(Counter(players[i]['team_id']for i in ids).values())>3 or sum(players[i]['price_tenths']for i in ids)+bank>1000:continue
                seen.add(ids);record.update(status='generated',initial_ids=list(ids),purchase_prices={str(i):players[i]['price_tenths']for i in ids},draws=attempt);break
            cases.append(record)
    return cases
