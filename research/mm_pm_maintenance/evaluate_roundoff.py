"""Reviewed implementation correction only; original forecasts/scorer files untouched."""
from contextlib import contextmanager
import math
import evaluate
import metrics

TOLERANCE=1e-12


def canonical_probability(p):
    if isinstance(p,bool)or not isinstance(p,(int,float))or not math.isfinite(p):
        return metrics_original(p)
    if -TOLERANCE<=p<0:return 0.
    if 1<p<=1+TOLERANCE:return 1.
    return metrics_original(p)

metrics_original=metrics.probability


@contextmanager
def guarded_probabilities():
    """One serial evaluation process; restore both aliases even on failure."""
    old_metrics=metrics.probability;old_evaluate=evaluate.probability
    audit=dict(tolerance=TOLERANCE,normalized_calls=0,max_correction=0.)
    def checked(p):
        q=canonical_probability(p)
        if p!=q:
            audit['normalized_calls']+=1;audit['max_correction']=max(audit['max_correction'],abs(p-q))
        return q
    metrics.probability=checked;evaluate.probability=checked
    try:yield audit
    finally:metrics.probability=old_metrics;evaluate.probability=old_evaluate


def score(*args,**kwargs):
    with guarded_probabilities()as audit:
        result=evaluate.score(*args,**kwargs)
    result['numeric_implementation_audit']=audit
    return result
