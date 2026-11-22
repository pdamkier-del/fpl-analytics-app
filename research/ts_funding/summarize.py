"""Offline descriptive summaries; does not invoke models or alter locked endpoints."""
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'research/results/EXP-TS-FUNDING-001'


def summarize(phase):
    data = json.loads((OUT/phase/'results.json').read_text())
    rows = data['rows']
    groups = defaultdict(list)
    for row in rows:
        groups[row['family']].append(row)
    def stats(rs):
        effects = [r['improvement'] for r in rs]
        return dict(cases=len(rs), improved=sum(x>1e-9 for x in effects),
                    worsened=sum(x< -1e-9 for x in effects),
                    mean_improvement=statistics.mean(effects),
                    median_improvement=statistics.median(effects),
                    min_improvement=min(effects), max_improvement=max(effects),
                    baseline_gap_sum=sum(r['arms']['baseline']['gap'] for r in rs),
                    candidate_gap_sum=sum(r['arms']['candidate']['gap'] for r in rs))
    summary = dict(phase=phase, execution_status=data['status'],
                   elapsed_seconds=data['elapsed_seconds'], not_run=data['not_run'],
                   overall=stats(rows), families={k:stats(v) for k,v in groups.items()},
                   errors=[dict(id=r['id'],errors=r.get('errors'),error=r.get('error'))
                           for r in rows if r['status']!='completed'],
                   nomination_audits=sum(r.get('audits',0) for r in rows))
    times={}
    for arm in ['baseline','candidate']:
        ts=[r['arms'][arm]['seconds'] for r in rows if r['arms'][arm]['seconds']is not None]
        times[arm]=dict(total=sum(ts),mean=statistics.mean(ts),maximum=max(ts)) if ts else None
    summary['planner_seconds']=times
    if phase=='holdout':
        summary['gates']=dict(
            all48_complete=len(rows)==48 and not summary['errors'] and not data['not_run'],
            no_regression=summary['overall']['worsened']==0,
            improvement_in_two_families=sum(v['mean_improvement']>1e-9 for v in summary['families'].values())>=2,
            total_runtime_ratio=times['candidate']['total']/times['baseline']['total'],
            runtime_ratio_pass=times['candidate']['total']<=2*times['baseline']['total'],
            candidate_mean_under_two_seconds=times['candidate']['mean']<=2)
        summary['practical_gate_pass']=all(v for k,v in summary['gates'].items()if k!='total_runtime_ratio')
    (OUT/(phase+'-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/(phase+'-cases.csv')).open('w') as f:
        writer=csv.writer(f);writer.writerow(['id','family','status','baseline_gap','candidate_gap','improvement','baseline_seconds','candidate_seconds'])
        for r in rows:
            writer.writerow([r['id'],r['family'],r['status'],r['arms']['baseline']['gap'],r['arms']['candidate']['gap'],r['improvement'],r['arms']['baseline']['seconds'],r['arms']['candidate']['seconds']])
    return summary


if __name__=='__main__':
    for phase in ['development','holdout']:
        print(json.dumps(summarize(phase)))
