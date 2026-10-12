#!/usr/bin/env python3
"""Read-only experiment on conditional starter minutes after proven medical return.

FPL predeadline state and observed previous matches classify cohorts without
using target outcomes. Compare exact frozen conditional starter duration with
shrinkage toward established pre-absence starting minutes; tune GW22-28 only,
validate GW29-38 only. Captured training period and inference already reused:
no automatic final-MM promotion.
"""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from experiment_mm_absence_states import build
H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
OUT=ROOT/'work/live-final-model/mm_medical_return_conditional_duration_ab.json'

def met(g,c):
    s=g[g.y.eq(1)]
    if not len(s):return None
    err=s[c].to_numpy(float)-s.minutes.to_numpy(float)
    return dict(n=len(s),mae=round(float(np.abs(err).mean()),5),rmse=round(float(np.sqrt(np.mean(err*err))),5),
        predicted=round(float(s[c].mean()),4),observed=round(float(s.minutes.mean()),4),
        bias=round(float(err.mean()),4))

def main():
    a,_=build()
    hist=pd.read_csv(H,usecols=['gw','player_uuid','y','minutes'],low_memory=False)
    # Refuse ambiguous DGW target-history pairing.
    per={}
    for (pid,gw),g in hist.groupby(['player_uuid','gw']):
        if len(g)==1:per[(str(pid),int(gw))]=(int(g.y.iloc[0]),float(g.minutes.iloc[0]))
    records=[]
    for r in a[a.medical_recovered].itertuples(index=False):
        pid=str(r.player_uuid);gw=int(r.gw)
        pre=[per.get((pid,gw-d)) for d in (3,4,5,6)]
        healthy=[float(v[1]) for v in pre if v is not None and int(v[0])==1]
        if len(healthy)<2:continue
        returned=per.get((pid,gw-1))
        if returned is None or returned[0]!=1:continue
        records.append(dict(gw=gw,player=str(r.player),team=str(r.team),player_uuid=pid,
            orig_duration=float(r.start_mu),healthy_mean=float(np.mean(healthy)),
            returned_minutes=float(returned[1]),original_pstart=float(r.mm_p_start),
            y=int(r.y),minutes=float(r.minutes),pre_healthy_starts=len(healthy)))
    f=pd.DataFrame(records)
    print('RETURN_DURATION_ELIGIBILITY',json.dumps(dict(observed_matching=len(f),medically_recovered=len(a[a.medical_recovered]),earliest=int(f.gw.min()) if len(f) else None)),flush=True)
    assert len(f)>=20 and not f.duplicated(['player_uuid','gw']).any()
    # Pure returner-specific conditional start-duration repair. No changing
    # current P(start), q(sub), team lineup assignment or starting XI.
    specs={}
    for healthy_beta in [0.,.25,.5,.75,1.]:
        for last_beta in [0.,.25,.5]:
            if healthy_beta+last_beta>1.:continue
            name=f'h{healthy_beta:g}_r{last_beta:g}'
            f[name]=np.clip((1-healthy_beta-last_beta)*f.orig_duration
                             +healthy_beta*f.healthy_mean+last_beta*f.returned_minutes,0.,90.)
            specs[name]=dict(healthy=float(healthy_beta),return_game=float(last_beta))
    dev=f[f.gw.between(22,28)]
    test=f[f.gw.between(29,38)]
    assert dev.y.sum()>=7 and test.y.sum()>=7,(int(dev.y.sum()),int(test.y.sum()))
    metrics={name:dict(dev=met(dev,name),test=met(test,name)) for name in specs}
    ref=metrics['h0_r0']['dev']
    candidates=[name for name,z in metrics.items() if
        z['dev']['rmse']<ref['rmse'] and z['dev']['mae']<ref['mae']]
    selected=min(candidates,key=lambda k:(metrics[k]['dev']['rmse'],metrics[k]['dev']['mae'])) if candidates else 'h0_r0'
    jp=dict(last_healthy_starts=[90,90,90,90],last_return_minutes=71,
        original_conditional_start_duration=71.29,
        by_candidate={name:round(float((1-z['healthy']-z['return_game'])*71.29+
                                   z['healthy']*90+z['return_game']*71),3) for name,z in specs.items()})
    results=dict(classification='RESEARCH_MEDICAL_RECOVERY_START_DURATION_AB_NO_PRODUCTION_CHANGE',
        eligible_forecast_rows=len(f),scored_starts_development=int(dev.y.sum()),
        scored_starts_validation=int(test.y.sum()),chosen_on_development=selected,
        original_metrics=metrics['h0_r0'],chosen_metrics=metrics[selected],
        all_variants=metrics,formulas=specs,joao_example=jp,
        guardrails=['Pre-injury starter minutes use only GW-3..GW-6 confirmed past starts',
            'No future outcomes in feature computation','Conditional minutes and team P(start) must not be conflated',
            'Historical reused GW22-38 test not independent, no production promotion'],
        app_updated=False,model_locked=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
    print('RETURN_DURATION_COUNTS',json.dumps(dict(cohort=len(f),dev_starts=int(dev.y.sum()),test_starts=int(test.y.sum()))))
    print('RETURN_DURATION_SELECTED',json.dumps(dict(selected=selected,reference=results['original_metrics'],
        chosen=results['chosen_metrics'],jp_candidate_duration=jp['by_candidate'][selected])))
    print('RETURN_DURATION_CANDIDATES',json.dumps({k:v['dev'] for k,v in metrics.items()}))
if __name__=='__main__':main()
