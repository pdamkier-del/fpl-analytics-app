#!/usr/bin/env python3
"""Explicit prospective entry point for PR9 B; fail closed on missing inputs.

The current production pipeline does NOT supply this new feature contract yet.
Never substitute its legacy/vNext numbers for B. Historical replay uses frozen
prequential B outputs; this path learns exactly its regularized calibrator.
"""
from pathlib import Path
import argparse,hashlib,json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from research_individual_mm_refinement import design, project, NUM
from mm_candidate import FormationSelector, build_contract, VERSION, validate_frame


def infer_B(history, target, provenance):
    forbidden={'y','minutes','started','actual_formation','observed_minutes','outcome_known_at'}
    if forbidden & set(target):raise ValueError('Target outcomes forbidden')
    if target.empty or target.cutoff.nunique()!=1:raise ValueError('One nonempty origin required')
    cut=pd.to_datetime(target.cutoff.iloc[0],utc=True)
    if provenance.get('upstream_variant')!='role_chance_return_duration':
        raise ValueError('Need verified PR8 upstream role/chance/return-duration inputs')
    if not provenance.get('source_manifest_sha256') or provenance.get('features')!=NUM:
        raise ValueError('Missing feature/provenance version')
    for col in ['max_history_known_at','physical_last_known_at','news_effective_at']:
        if col not in target:raise ValueError('Missing source clock: '+col)
        clock=pd.to_datetime(target[col],utc=True,format='mixed')
        if not(clock.isna()|clock.lt(cut)).all():raise ValueError('Future target feature')
    # Pure fields, same fixed design as PR9. Actual labels only in past history.
    for col in NUM+['pos','news_eligible','news_state','news_chance']:
        if col not in target or (col in NUM+['pos'] and col not in history):
            raise ValueError('Missing B feature: '+col)
    h=history.copy();known=pd.to_datetime(h.known_at,utc=True)
    if not known.lt(cut).all():raise ValueError('Training has unknown/future labels')
    if set(h.fixture_uuid)&set(target.fixture_uuid):raise ValueError('Training/target overlap')
    eligible=h.p.gt(0)&h.p.lt(1)
    if eligible.sum()<200 or h.loc[eligible,'y'].nunique()<2:
        raise ValueError('Insufficient B calibration data; do not silently use baseline')
    g=validate_frame(target)
    model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,max_iter=3000,tol=1e-8))
    model.fit(design(h.loc[eligible]),h.loc[eligible,'y'])
    if model[-1].n_iter_[0]>=3000:raise ValueError('Calibration not converged')
    g['p']=model.predict_proba(design(g))[:,1]
    fixed=target.p.eq(0)&target.q.eq(0);g.loc[fixed,'p']=0.
    projected_p=project(g).p.to_numpy()
    # PR9 prequential() stores only the projected p, not its temporary q cap.
    # change(B) then projects that p against the ORIGINAL upstream q again.
    g=target.copy();g['p']=projected_p;g=project(g)
    return g,dict(alpha=10.,training_rows=int(eligible.sum()),last_label_known_at=str(known.max()),feature_columns=NUM,independently_validated=False)


def register(doc, directory, now=None):
    """Immutable local preregistration; never relabel a historical replay as live."""
    now=now or datetime.now(timezone.utc)
    if doc['scope']!='prospective_preview':raise ValueError('Not a prospective forecast')
    if any(pd.Timestamp(r['forecast_at'])<=pd.Timestamp(now) for r in doc['players']):
        raise ValueError('Cannot register after deadline')
    content=json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    digest=hashlib.sha256(content).hexdigest()
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    path=directory/(digest+'.json')
    with path.open('xb') as out:out.write(content)
    return dict(path=str(path),sha256=digest,registered_at=now.isoformat(),model_version=VERSION,deadline_correct=bool(doc.get('deadline_correct',False)))


def main():
    a=argparse.ArgumentParser();a.add_argument('--history',type=Path,required=True);a.add_argument('--target',type=Path,required=True);a.add_argument('--roles',type=Path,required=True);a.add_argument('--provenance',type=Path,required=True);a.add_argument('--register',type=Path,required=True);args=a.parse_args()
    history=pd.read_csv(args.history);target=pd.read_csv(args.target);provenance=json.loads(args.provenance.read_text())
    forecast,calibration=infer_B(history,target,provenance)
    selector=FormationSelector(pd.read_csv(args.roles))
    doc=build_contract(forecast,selector,scope='prospective_preview',source_hash=hashlib.sha256(args.target.read_bytes()).hexdigest(),model_data_at=provenance['data_at'])
    doc['calibration']=calibration;doc['deadline_correct']=False
    doc['provenance']=provenance
    # An immutable code identity accompanies every preregistered forecast.
    doc['code_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('mm_candidate.py'),Path(__file__).with_name('research_individual_mm_refinement.py')]}
    print(json.dumps(register(doc,args.register),indent=2))


if __name__=='__main__':main()
