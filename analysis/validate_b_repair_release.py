"""Release checks for the isolated source/event repair; no production activation."""
import argparse,hashlib,json
from pathlib import Path
import pandas as pd
from b_chain_contract import validate_forecast

def check(source,inputs,historical):
    forecast=json.loads((source/'forecast.json').read_text());validate_forecast(forecast)
    if forecast.get('model_revision')!='B-integrated-source-event-repair-v2':raise ValueError('Wrong B repair revision')
    for name,digest in forecast['input_sha256'].items():
        if hashlib.sha256((inputs/name).read_bytes()).hexdigest()!=digest:raise ValueError('Changed current input: '+name)
    for name,digest in forecast['code_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Changed numerical source: '+name)
    bootstrap=json.loads((inputs/'bootstrap.json').read_text());unavailable={p['id']for p in bootstrap['elements']if p['status']=='u'}
    selected=[p for p in forecast['players']if p['id']in unavailable]
    if not selected or any(w['xmins']!=0 or w['xpts']!=0 for p in selected for w in p['weeks']):raise ValueError('Unavailable player consumes future minutes/points')
    rows=[dict(team_id=p['team_id'],pos=p['position'],fixture_uuid=f['fixture_uuid'],x=f['xmins'])for p in forecast['players']for w in p['weeks']for f in w['fixtures']]
    frame=pd.DataFrame(rows);budget=frame[frame.pos.ne(1)].groupby(['team_id','fixture_uuid']).x.sum();error=float(abs(budget-900).max())
    if error>1e-6:raise ValueError('Outfield minute budget mismatch')
    events=[r['event_conservation']for r in forecast['gk_team_fixtures']]
    if not events or any(r['draws']!=400 or r['team_goals']!=r['ordinary']+r['penalty']+r['own_goal']or r['unattributed']or r['assists_without_eligible_event']or r['max_expected_budget_error']>1e-9 for r in events):raise ValueError('Event conservation audit failed')
    evidence=json.loads((historical/'evidence.json').read_text())
    for group in ['source_sha256','evidence_sha256']:
        for name,digest in evidence[group].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Stale repair validation: '+name)
    historical_report=json.loads((historical/'pm/result.json').read_text())
    if historical_report['fixtures']!=341 or historical_report.get('baseline_max_xp_error',1)>1e-9:raise ValueError('Historical baseline not reproduced')
    ts=json.loads((historical/'ts/result.json').read_text())
    if ts['live_activated']:raise ValueError('Unvalidated TS search activated')
    result=dict(passed=True,forecast_sha256=forecast['forecast_sha256'],gws=forecast['gws'],unavailable_players_zero_minutes=len(selected),max_outfield_900_error=error,team_fixture_event_receipts=len(events),max_event_budget_error=max(r['max_expected_budget_error']for r in events),historical=historical_report,ts_unchanged=True,production_activation=False)
    (source/'repair-release-validation.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('work/joint-gk-current'));p.add_argument('--inputs',type=Path,default=Path('work/current-B-inputs'));p.add_argument('--historical',type=Path,default=Path('analysis/results/integrated-repair-20261031'));a=p.parse_args();print(json.dumps(check(a.source,a.inputs,a.historical),indent=2))
if __name__=='__main__':main()
