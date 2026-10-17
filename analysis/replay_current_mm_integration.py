"""Same-cutoff original-minute vs B-minute PM integration replay, no manager.

Restore the checksum-verified current-B-public-input-and-validation-evidence
artifact first. This compares forecasts, not realized predictive accuracy.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import numpy as np
import pandas as pd
from mm_locked_bridge import simulate_pair,KEY,code_identity
from mm_candidate_forecast import seal_document
from fpl_v1_1_model.forecast_snapshot import require_snapshot
from audit_capture_io import write_frame

def replay(evidence,out):
    evidence=Path(evidence);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    source=evidence/'current-B-inputs';result=evidence/'current-B-output'
    f=json.loads((result/'forecast.json').read_text());require_snapshot(f)
    doc=json.loads((result/'mm.json').read_text())
    if seal_document(doc)['content_sha256']!=doc['content_sha256']:raise ValueError('MM checksum mismatch')
    if f['minute_sampler_audit']['sampler']!='locked':raise ValueError('Locked sampler required')
    pm=pd.read_csv(source/'pm.csv.gz',low_memory=False)
    target=pd.read_csv(source/'target.csv.gz',low_memory=False)
    if not pd.to_datetime(pm.cutoff,utc=True).eq(pd.Timestamp(f['data_asof'])).all():raise ValueError('Cutoff mismatch')
    mm=pd.DataFrame([dict(fixture_uuid=r['fixture_id'],player_uuid=r['player_id'],p=r['p_start'],q=r['p_sub_given_not_start'],s=r['start_minutes'],c=r['sub_minutes'],x=r['xmins']) for r in doc['players']])
    mm=target.drop(columns=['p','q','s','c','x']).merge(mm,on=KEY,validate='one_to_one')
    before=code_identity(ROOT)
    pair=simulate_pair(pm,mm,season='2026-27')
    if before!=code_identity(ROOT):raise ValueError('Locked code changed')
    wide=pair[pair.arm.eq('B_minutes')].merge(pair[pair.arm.eq('production_minutes')],on=KEY+['gw'],suffixes=('_B','_original'),validate='one_to_one')
    for col in ['xpts','xmins','p_start','sampler_expected_minutes']:
        wide['delta_'+col]=wide[col+'_B']-wide[col+'_original']
    names={p['player_uuid']:p for p in f['players']}
    wide['name']=wide.player_uuid.map(lambda k:names[k]['name']);wide['club']=wide.player_uuid.map(lambda k:names[k]['team'])
    # Same random seeds and fixture ordering as the actual current run.
    published={(x['fixture_uuid'],p['player_uuid']):x['xpts'] for p in f['players'] for w in p['weeks'] for x in w['fixtures']}
    residual=max(abs(r.xpts_B-published[(r.fixture_uuid,r.player_uuid)]) for r in wide.itertuples())
    if residual>1e-12:raise ValueError('Replay does not reproduce published B xP')
    write_frame(out/'paired_forecasts.csv.gz',wide)
    origin=wide[wide.gw.eq(min(f['gws']))]
    examples=[]
    for r in origin[origin.name.isin(['Haaland','Saka','Palmer','João Pedro'])].itertuples():
        examples.append({k:getattr(r,k) for k in ['name','club','xmins_original','xmins_B','p_start_original','p_start_B','xpts_original','xpts_B','delta_xpts']})
    baseline_sets={k:set(g.loc[g.xi_selected_map.astype(bool),'player_uuid']) for k,g in pm.groupby(['fixture_uuid','team_id'])}
    selections=pd.DataFrame(doc['players']);changes=[]
    for (fixture,club),g in selections.groupby(['fixture_id','club_id']):
        old=baseline_sets[(fixture,club)];new=set(g.loc[g.expected_xi,'player_id'])
        changes.append(dict(fixture=fixture,club=int(club),original_count=len(old),B_count=len(new),shared=len(old&new)))
    report=dict(scope='same_cutoff_forecast_comparison_not_accuracy_validation',cutoff=f['data_asof'],gws=f['gws'],players=len(f['players']),fixtures=f['fixtures'],matched_rows=len(wide),locked_model_active=False,minute_sampler='locked',PM_parameters_changed=False,TS_parameters_changed=False,code_sha256=before,published_B_xP_max_residual=residual,examples=examples,mean_delta_xM=float(wide.delta_xmins.mean()),mean_delta_xP=float(wide.delta_xpts.mean()),max_abs_delta_xP=float(wide.delta_xpts.abs().max()),origin_leading_xP_original=origin.sort_values('xpts_original',ascending=False)[['name','club','xpts_original']].head(5).to_dict('records'),origin_leading_xP_B=origin.sort_values('xpts_B',ascending=False)[['name','club','xpts_B']].head(5).to_dict('records'),XI_changes=changes,manager_TS='Not Available: no actual manager record in this environment',limitations=['Forecast differences are not observed accuracy gains.','Independent validation is unavailable.','Unchanged locked sampler retains the disclosed MM/PM expectation gap.'])
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['code_sha256','XI_changes']},indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();replay(a.evidence,a.out)
