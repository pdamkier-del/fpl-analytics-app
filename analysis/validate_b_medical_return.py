"""Monthly walk-forward dated return validation; prior observations only."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from b_medical_return import episodes,probability

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);truth=episodes('.');cache={};rows=[]
    for r in truth.itertuples():
        seen=pd.Timestamp(r.report_known_at);train_cut=seen.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        key=train_cut.isoformat()
        if key not in cache:
            try:cache[key]=episodes('.',train_cut)
            except ValueError:cache[key]=pd.DataFrame(columns=truth.columns)
        train=cache[key]
        for days in [7,14,21,28]:
            target=seen+pd.Timedelta(days=days)
            if pd.Timestamp(r.outcome_known_at)<target and not r.event:continue # Censored before horizon.
            prob,receipt=probability(train,seen,r.expected_at,target)
            if prob is None:continue
            y=int(r.event and pd.Timestamp(r.end_at)<=target)
            rows.append(dict(season=r.season,player_uuid=r.player_uuid,source_id=r.source_id,report_known_at=seen.isoformat(),training_cutoff=key,horizon_days=days,probability=prob,returned=y,risk_set=receipt['risk_set']))
    d=pd.DataFrame(rows);d.to_csv(a.out/'walk-forward.csv.gz',index=False);metrics=[]
    for (season,days),g in d.groupby(['season','horizon_days']):
        metrics.append(dict(season=season,horizon_days=int(days),rows=len(g),Brier=float(((g.probability-g.returned)**2).mean()),unknown_available_baseline_Brier=float(((1-g.returned)**2).mean()),still_out_baseline_Brier=float((g.returned**2).mean()),mean_pred=float(g.probability.mean()),mean_actual=float(g.returned.mean())))
    result=dict(scope='Dated report to first recorded appearance; not medical clearance or start Brier',walk_forward='Fit only source/outcome observations before each report month; no target labels in fit',episodes=len(truth),forecasts=len(d),metrics=metrics,production_changed=False)
    (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
