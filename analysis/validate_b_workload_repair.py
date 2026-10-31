"""Walk-forward original vs versioned physical features; frozen labels/roles."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from build_current_b_inputs import historical_B_training
from b_physical_workload import historical_ledger,features,VERSION
from mm_candidate_forecast import infer_B
from research_individual_mm_refinement import NUM

def main():
    out=Path('analysis/results/integrated-repair-20261031/workload');out.mkdir(parents=True,exist_ok=True)
    old=historical_B_training();ledger,coverage=historical_ledger('.');new=features(old,ledger);rows=[]
    for season in ['2024-25','2025-26']:
        for gw in range(22,39):
            select=old.season.eq(season)&old.gw.eq(gw)
            if not select.any():continue
            cut=pd.to_datetime(old.loc[select,'cutoff'],utc=True,format='mixed').iloc[0]
            actual=old[select].set_index(['fixture_uuid','player_uuid'])
            for arm,history in [('frozen',old),('all_comp_workload',new)]:
                train=history[pd.to_datetime(history.known_at,utc=True,format='mixed').lt(cut)].copy();target=history[select].drop(columns=[c for c in ['y','minutes','started','observed_minutes','actual_formation','outcome_known_at']if c in history]).copy();prov=dict(upstream_variant='role_chance_return_duration',source_manifest_sha256='historical-immutable-source-replay',features=NUM)
                if arm!='frozen':prov['physical_feature_version']=VERSION
                pred,receipt=infer_B(train,target,prov)
                for r in pred.itertuples():
                    y=actual.loc[(r.fixture_uuid,r.player_uuid)];rows.append(dict(season=season,gw=gw,fixture_uuid=r.fixture_uuid,player_uuid=r.player_uuid,team_id=r.team_id,pos=r.pos,cutoff=str(cut),arm=arm,p=r.p,q=r.q,s=r.s,c=r.c,x=r.x,actual_start=int(y.y),actual_minutes=float(y.minutes)))
            print('Workload replay',season,gw,flush=True)
    df=pd.DataFrame(rows);df.to_csv(out/'predictions.csv.gz',index=False);metrics=[]
    for (season,arm),g in df.groupby(['season','arm']):metrics.append(dict(season=season,arm=arm,rows=len(g),start_Brier=float(((g.p-g.actual_start)**2).mean()),minute_MAE=float(abs(g.x-g.actual_minutes).mean()),minute_RMSE=float(np.sqrt(((g.x-g.actual_minutes)**2).mean())),minute_bias=float((g.x-g.actual_minutes).mean())))
    result=dict(scope='Raw B marginal stage before tactical/physical kernel; same chronological fit and sources, no fresh holdout',coverage=coverage,metrics=metrics,production_changed=False);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
