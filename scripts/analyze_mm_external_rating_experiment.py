#!/usr/bin/env python3
"""Fixed descriptive slices of existing MM predictions; no tuning/promotion."""
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_mm_unified_official_roles import SOURCE,full_mm
from run_v4_performance_rating_experiment import build_perf_ledger,add_features
from run_v4_three_state_sequence_experiment import add_sequence_features,metrics
from fpl_v1_1_model.role_classifier import ROLES


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='analysis/results/mm-v2-xi-rating-with-external-ratings-20261006-v1');a=ap.parse_args();out=ROOT/a.out
    f=add_features(add_sequence_features(pd.read_csv(SOURCE).reset_index(drop=True)),build_perf_ledger())
    test=f.gw.between(22,38).to_numpy();cut=pd.to_datetime(f.loc[test,'cutoff'],utc=True).min()
    train=(f.gw.between(6,21)&(pd.to_datetime(f.outcome_known_at,utc=True)<cut)).to_numpy()
    p,q,sub,x,_=full_mm(f.copy(),train)
    keys=['fixture_uuid','player_uuid','team_id']
    base=f.loc[test,keys+['cutoff','outcome_known_at','start_minutes_mean']+[c for c in f if c.startswith(('q_','H_'))]].copy()
    base['replayed_base_p_start']=p[test];base['p_sub_given_bench']=q[test];base['e_min_given_sub']=np.asarray(sub)[test];base['replayed_base_xmins']=x[test]
    pred=pd.read_csv(out/'reused_diagnostic_predictions.csv.gz').merge(base,on=keys,validate='one_to_one')
    if np.max(abs(pred.base_p_start-pred.replayed_base_p_start))>1e-5 or np.max(abs(pred.base_xmins-pred.replayed_base_xmins))>1e-4:raise ValueError('Base replay differs from experiment; refuse slice analysis')
    xi_dir=ROOT/'analysis/results/mm-v2-xi-rating-20261006-v1'
    xi=pd.read_csv(xi_dir/'reused_diagnostic_predictions.csv.gz')[keys+['v2_p_start','v2_xmins']].rename(columns={'v2_p_start':'xi_only_p_start','v2_xmins':'xi_only_xmins'})
    pred=pred.merge(xi,on=keys,validate='one_to_one')
    qcols=[f'q_{r}_slow' for r in ROLES if f'q_{r}_slow' in pred]
    pred['multi_role']=(pred[qcols]>=.20).sum(axis=1)>=2
    pred['uncertain_starter']=pred.base_p_start.between(.2,.8)
    pred['close_role_competition']=(pred.xi_role_competitors>=2)&(pred.xi_score_margin.abs()<=.25)
    pred['incumbent_nonstart_shock']=(pred.base_p_start>=.8)&(pred.y==0)
    pred['unexpected_start_shock']=(pred.base_p_start<=.2)&(pred.y==1)
    pred['observed_lineup_shock']=pred.incumbent_nonstart_shock|pred.unexpected_start_shock
    pred['rating_uptrend']=(pred.rating_hist_n>=2)&(pred.rating_trend>=.25)
    pred['rating_downtrend']=(pred.rating_hist_n>=2)&(pred.rating_trend<=-.25)
    pred['bad_form_incumbent_replacement']=False
    pairs=[]
    for _,g in pred.groupby(['fixture_uuid','team_id','expected_role'],dropna=False):
        inc=g[(g.base_p_start>=.8)&(g.y==0)&(g.rating_hist_n>=2)]
        challengers=g[(g.y==1)&(g.rating_hist_n>=2)]
        for i,r in inc.iterrows():
            for j,c in challengers[challengers.rating_recent>r.rating_recent].iterrows():
                pred.loc[[i,j],'bad_form_incumbent_replacement']=True
                pairs.append({'fixture_uuid':r.fixture_uuid,'team':r.team,'gw':int(r.gw),'role':r.expected_role,'incumbent_uuid':r.player_uuid,'incumbent':r.player,'competitor_uuid':c.player_uuid,'competitor':c.player,'incumbent_recent_rating':r.rating_recent,'competitor_recent_rating':c.rating_recent,'incumbent_rating_trend':r.rating_trend,'competitor_rating_trend':c.rating_trend,'incumbent_base_p_start':r.base_p_start,'incumbent_v2_p_start':r.v2_p_start,'competitor_base_p_start':c.base_p_start,'competitor_v2_p_start':c.v2_p_start,'incumbent_actual_minutes':r.minutes,'competitor_actual_minutes':c.minutes})
    rows=[]
    def report(dimension,label,mask):
        mask=np.asarray(mask,bool)
        if not mask.any():return
        for model,pc,xc in [('locked_MM','base_p_start','base_xmins'),('XI_only','xi_only_p_start','xi_only_xmins'),('XI_external_ratings','v2_p_start','v2_xmins')]:
            met=metrics(pred,mask,pred[pc].to_numpy(),pred.p_sub_given_bench.to_numpy(),pred[xc].to_numpy())
            y=pred.y.to_numpy()[mask];pp=np.clip(pred[pc].to_numpy()[mask],1e-12,1-1e-12)
            rows.append({'dimension':dimension,'slice':str(label),'model':model,**met,'start_brier':float(np.mean((pp-y)**2)),'start_log_loss':float(-np.mean(y*np.log(pp)+(1-y)*np.log(1-pp)))})
    report('all','GW22-38',np.ones(len(pred),bool))
    for col in ['uncertain_starter','multi_role','close_role_competition','rating_uptrend','rating_downtrend','observed_lineup_shock','incumbent_nonstart_shock','unexpected_start_shock','bad_form_incumbent_replacement']:
        report('case',col,pred[col]);report('case','not_'+col,~pred[col])
    report('case','rating_history_present',pred.rating_hist_n>0);report('case','rating_history_missing',pred.rating_hist_n==0)
    for column,dimension in [('gw','GW'),('team','team'),('expected_role','role')]:
        for label,g in pred.groupby(column):report(dimension,label,pred.index.isin(g.index))
    slices=pd.DataFrame(rows);slices.to_csv(out/'descriptive_slices.csv',index=False)
    pred.to_csv(out/'auditable_diagnostic_predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(pairs).to_csv(out/'incumbent_competitor_cases.csv',index=False)
    reference=json.loads((ROOT/'analysis/results/mm-final-20261006-v1/result.json').read_text())
    result=json.loads((out/'result.json').read_text());xi_result=json.loads((xi_dir/'result.json').read_text())
    audit={'scope':'MM only; existing ratings/XI math and minute-duration models unchanged','reused_diagnostic_only':True,'promotion':False,'fixed_slice_definitions':{'multi_role':'at least two q_role_slow >= .20','close_role_competition':'xi_role_competitors >=2 and abs(xi_score_margin) <= .25','rating_up_down':'at least two historical ratings and trend >= +.25 / <= -.25 on original scale','lineup_shock':'base P(start)>=.8 and no start OR <=.2 and start','incumbent_competitor':'same expected role/team/fixture; base>=.8 incumbent does not start; actual starter has higher prior recent rating; descriptive outcomes only'},'locked_reference':reference['reused_diagnostic_gw22_38'],'xi_only_reference':xi_result['reused_diagnostic'],'external_ratings':result['reused_diagnostic'],'incumbent_competitor_pairs':len(pairs),'input_sha256':hashlib.sha256((ROOT/'data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz').read_bytes()).hexdigest(),'warning':'Observational reused-data slices cannot establish causal performance-driven selection or independent OOS improvement.'}
    (out/'comparison_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(slices[slices.dimension.isin(['all','case'])].to_string(index=False))
if __name__=='__main__':main()
