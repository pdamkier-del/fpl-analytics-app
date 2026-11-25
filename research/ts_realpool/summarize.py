"""Read-only accounting of retained first-attempt results; never run a model."""
from pathlib import Path
import json
import math
import statistics
import sys


def summarize(doc):
    rows=doc.get('arms',[]);by={(r['id'],r['arm']):r for r in rows}
    complete=doc.get('states_generated')==12 and len(rows)==36 and all(r['status']=='completed'for r in rows)
    pairs=[]
    for i in range(1,13):
        a=by.get((i,'baseline'));b=by.get((i,'candidate'));k=by.get((i,'keep'))
        entry=dict(id=i,stratum=(i-1)//3,status='incomplete',baseline_status=a['status']if a else'not_run',candidate_status=b['status']if b else'not_run',keep_status=k['status']if k else'not_run')
        if a and b and a['status']==b['status']=='completed':
            entry.update(status='paired',baseline=a['objective'],candidate=b['objective'],delta=b['objective']-a['objective'],baseline_seconds=a['end_to_end_seconds'],candidate_seconds=b['end_to_end_seconds'],runtime_ratio=b['end_to_end_seconds']/a['end_to_end_seconds'])
            if k and k['status']=='completed':entry.update(keep=k['objective'],baseline_vs_keep=a['objective']-k['objective'],candidate_vs_keep=b['objective']-k['objective'])
        pairs.append(entry)
    supported=[p for p in pairs if p['status']=='paired'];deltas=[p['delta']for p in supported]
    complete_mean=statistics.mean(deltas)if len(supported)==12 else None
    p90=sorted(p['candidate_seconds']for p in supported)[math.ceil(.9*12)-1]if len(supported)==12 else None
    ratio=statistics.median(p['runtime_ratio']for p in supported)if len(supported)==12 else None
    good=sum(d>1e-8 for d in deltas);bad=sum(d< -1e-8 for d in deltas)
    positive_strata=sorted({p['stratum']for p in supported if p['delta']>1e-8})
    gates=dict(coverage_legality=complete and all(r.get('illegal')==0 and r.get('scorer_disagreements')==0 for r in rows),utility=complete_mean is not None and complete_mean>=.25 and good>=3 and len(positive_strata)>=2,non_regression=len(supported)==12 and bad==0,runtime=p90 is not None and p90<=30 and ratio<=2 and all(r['end_to_end_seconds']<=120 for r in rows)and doc.get('aggregate_budget_seconds_used',doc.get('elapsed_seconds',3601))<=3600)
    return dict(status='pass_feasibility_only'if all(gates.values())else'failed_or_inconclusive',all_gates_pass=all(gates.values()),gates=gates,complete_pairs=len(supported),gate_interpretation=dict(coverage='Failed: incomplete arms'if not complete else'Complete',utility='Unknown full12state primary when any pair missing; completed-pair observations do not replace it'if complete_mean is None else'Apply fixed thresholds',non_regression='No observed regression among completed pairs; full12non-regression unknown'if len(supported)<12 else'Apply fixed tolerance',runtime='Any timeout fails; missing-arm p90/ratio is not imputed'),mean_delta_primary=complete_mean,median_delta=statistics.median(deltas)if len(supported)==12 else None,range_delta=[min(deltas),max(deltas)]if len(supported)==12 else None,improved=good,worsened=bad,unchanged=sum(abs(d)<=1e-8 for d in deltas),positive_strata=positive_strata,candidate_p90_seconds=p90,median_runtime_ratio=ratio,aggregate_budget_seconds_used=doc.get('aggregate_budget_seconds_used',doc.get('elapsed_seconds')),max_completed_rss_kib=max([r['peak_rss_kib']for r in rows if r.get('status')=='completed'],default=None),pairs=pairs,interpretation='Finite synthetic states under one original forecast; no representative manager or realized FPL claim')
if __name__=='__main__':
    source=Path(sys.argv[1]);print(json.dumps(summarize(json.loads(source.read_text())),indent=2,allow_nan=False))
