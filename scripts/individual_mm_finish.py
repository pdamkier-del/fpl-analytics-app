#!/usr/bin/env python3
"""Additional predeclared ablation summaries from completed chronological MM fits."""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from individual_mm_validation import predict,summarize,save
from audit_capture_io import write_frame
from audit_mm_components import metrics
OUT=ROOT/'analysis/results/individual-mm-20261015'

def main():
    report=json.loads((OUT/'report.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
    continuous=min((k for k,v in sel['grid'].items() if v['kind']=='continuous'),key=lambda k:sel['grid'][k]['start']['log_loss']);cfg=sel['grid'][continuous]
    r24=pd.read_csv(OUT/(continuous+'_development_predictions.csv.gz'),low_memory=False)
    features24=pd.read_csv(OUT/f"2024-25_roles_h{cfg['half']}.csv.gz",low_memory=False)
    for season in ['2024-25','2025-26']:
        f=pd.read_csv(OUT/f'{season}_candidates.csv.gz',low_memory=False);f=f[~f['mode'].eq('continuous_role_alternative')]
        selected=f[f['mode'].eq('role_start')].copy()
        if season=='2024-25':alternate=r24
        else:
            if cfg['half']!=sel['grid'][sel['selected']]['half']:raise ValueError('Alternative requires its own causal half-life features')
            alternate=predict(selected,features24,cfg['C'],'continuous')
        f=pd.concat([f,alternate.assign(mode='continuous_role_alternative')],ignore_index=True)
        write_frame(OUT/f'{season}_candidates.csv.gz',f)
        evaluated=f[f.gw.ge(22)] if season=='2024-25' else f
        modes={k:v for k,v in evaluated.groupby('mode')};result=summarize(modes)
        profile=selected.set_index(['fixture_uuid','player_uuid'])
        for mode,g in modes.items():
            r=profile.loc[pd.MultiIndex.from_frame(g[['fixture_uuid','player_uuid']])]
            mask=(r.role_logit.lt(0)&r.role_cameo.gt(.6)&r.role_exposure.gt(3)).to_numpy()
            result[mode]['groups']['prior_cameo_specialist']=metrics(g.loc[mask],p=g.loc[mask].p,s=g.loc[mask].s,q=g.loc[mask].q,c=g.loc[mask].c) if mask.any() else dict(rows=0)
        report['results'][season]=result
    report['continuous_alternative']=dict(selected_on_development=continuous,primary_model_unchanged=True)
    save(OUT/'report.json',report)
    print(json.dumps({s:{k:r['paired_vs_same_logistic_without_role'] for k,r in modes.items() if 'paired_vs_same_logistic_without_role' in r}for s,modes in report['results'].items()},indent=2))
if __name__=='__main__':main()
