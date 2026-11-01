#!/usr/bin/env python3
"""Evaluate GK60/90 probabilities and interval coverage on the paired cohort."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from dataclasses import replace
from individual_mm_evidence import load_frame
from run_vfinal_integrated import build_final_frame,make_vfinal_input
from mm_locked_bridge import attach_mm
from gk_joint_bridge import observations,DurationHistory,prepare
from run_joint_gk_preview import ROOT,write

def main():
    source=ROOT/'work/joint-gk-historical';paired=pd.read_csv(source/'paired-gk.csv.gz')
    pm=build_final_frame();pm['season']='2025-26';pm=pm[pm.gw.between(22,38)]
    b=load_frame(ROOT/'analysis/results/individual-mm-refinement-20261016/predictions.npz');b=b[b.season.eq('2025-26')&b['mode'].eq('B')&b.gw.between(22,38)]
    b=b.merge(pm[['fixture_uuid','player_uuid']+(['pos']if 'pos'not in b else[])],on=['fixture_uuid','player_uuid'],validate='one_to_one')
    frame=attach_mm(pm,b);obs=observations(ROOT);cache={};rows=[]
    pair=paired.set_index(['fixture_uuid','player_uuid'])
    for fx,g in frame.groupby('fixture_uuid',sort=True):
        cut=str(g.cutoff.iloc[0])
        if cut not in cache:cache[cut]=DurationHistory(obs,cut)
        inp,_=make_vfinal_input(g);_,details,_=prepare(inp,b[b.fixture_uuid.eq(fx)],cache[cut])
        for pid,d in details.items():
            if(fx,pid)not in pair.index:continue
            p=pair.loc[(fx,pid)]
            if abs(p.after_p-d['p'])>1e-8:raise ValueError('Probability reconstruction differs from replay')
            mass=np.asarray(d['pmf']);cdf=np.cumsum(mass);lo=int(np.searchsorted(cdf,.1));hi=int(np.searchsorted(cdf,.9))
            rows.append(dict(p60=d['p60'],p90=d['p90'],actual60=int(p.actual_minutes>=60),actual90=int(p.actual_minutes==90),covered=int(lo<=p.actual_minutes<=hi)))
    f=pd.DataFrame(rows)
    write(source/'uncertainty.json',dict(rows=len(f),p60_brier=float(((f.p60-f.actual60)**2).mean()),p90_brier=float(((f.p90-f.actual90)**2).mean()),
        mean_p60=float(f.p60.mean()),actual_p60=float(f.actual60.mean()),mean_p90=float(f.p90.mean()),actual_p90=float(f.actual90.mean()),
        interval80_coverage=float(f.covered.mean()),note='Discrete model intervals; reused prequential cohort, not independent coverage certification'))
    print((source/'uncertainty.json').read_text())
if __name__=='__main__':main()
