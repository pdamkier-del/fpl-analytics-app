"""Score fixed-policy retrospective B replays separately from archived forecasts."""
import gzip,hashlib,json,math
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'analysis/results/current-season-b-backtest-20261027'

def metrics(rows):
    n=len(rows)
    mean=lambda f:sum(f(r)for r in rows)/n if n else None
    return dict(scored_rows=n,minute_mae=mean(lambda r:abs(r['expected_minutes']-r['actual_minutes'])),minute_bias=mean(lambda r:r['expected_minutes']-r['actual_minutes']),xp_mae=mean(lambda r:abs(r['xp']-r['actual_points'])),xp_bias=mean(lambda r:r['xp']-r['actual_points']),start_brier=mean(lambda r:(r['p_start']-r['actual_starts'])**2),p0_brier=mean(lambda r:((1-r['p_play'])-(r['actual_minutes']==0))**2),p60_brier=mean(lambda r:(r['p60']-(r['actual_minutes']>=60))**2),p90_brier=mean(lambda r:(r['p90']-(r['actual_minutes']==90))**2))

def score_forecast(doc,history,catalogue,fixtures):
    import pandas as pd
    cut=pd.Timestamp(doc['cutoff']);deadline=pd.Timestamp(doc['origin_deadline']);gw=doc['gw']
    if doc.get('schema')!='B-current-season-backtest-v1'or doc.get('scope')!='retrospective_fixed_B_policy_not_original_forecast_not_independent_holdout':raise ValueError('Not a separately labelled backtest')
    if not cut<deadline or not pd.Timestamp(doc['generated_at'])>deadline:raise ValueError('Invalid retrospective/source clocks')
    codes={p['id']:p.get('code')for p in catalogue['players']};fx={f['id']:f for f in fixtures['fixtures']}
    match={(r['player_id'],r['fixture_id']):r for r in history['match_rows']};final={(r['player_id'],r['gw']):r for r in history['gw_rows']};seen=set();rows=[];pending=0;excluded=0
    for r in doc['players']:
        key=(r['fixture_uuid'],r['player_uuid'])
        if key in seen:raise ValueError('Duplicate replay prediction')
        seen.add(key);fid=int(r['fixture_uuid'].rsplit('-',1)[1]);f=fx.get(fid)
        if not r.get('fpl_code')or codes.get(r['player_id'])!=r['fpl_code']:excluded+=1;continue
        if not f or r['gw']!=gw or f['gw']!=gw or r['team_id']not in [f['home'],f['away']]or pd.Timestamp(r['kickoff'])!=pd.Timestamp(f['kickoff'])or cut>=pd.Timestamp(r['kickoff']):raise ValueError('Historical fixture identity mismatch')
        if not all(math.isfinite(r[k])for k in ['p_start','expected_minutes','pm_expected_minutes','p_play','p60','p90','xp']):raise ValueError('Invalid replay values')
        if not all(0<=r[k]<=1 for k in ['p_start','p_play','p60','p90'])or not 0<=r['expected_minutes']<=90 or not r['p90']<=r['p60']<=r['p_play']+1e-10:raise ValueError('Invalid replay probability law')
        if abs(r['expected_minutes']-r['pm_expected_minutes'])>1e-8:raise ValueError('MM/PM expectation mismatch')
        label=final.get((r['player_id'],gw));m=match.get((r['player_id'],fid));actual=None;basis=None
        if f.get('finished')and label and label['gw_complete']:
            if m and not m.get('provisional')and m['team_id']==r['team_id']:actual=m['stats'];basis='verified_final_fixture_history'
            elif all(label['stats'].get(k)==0 for k in ['minutes','starts','total_points']):actual=label['stats'];basis='official_final_GW_all_zero'
        if actual is None:pending+=1;continue
        if not all(math.isfinite(actual[k])for k in ['minutes','starts','total_points'])or not 0<=actual['minutes']<=90 or actual['starts']not in [0,1]:raise ValueError('Invalid actual labels')
        rows.append(dict(r,actual_minutes=actual['minutes'],actual_points=actual['total_points'],actual_starts=actual['starts'],label_basis=basis))
    return dict(gw=gw,status='complete'if rows and not pending else'pending_results',pending_rows=pending,excluded_rows=excluded,cutoff=doc['cutoff'],origin_deadline=doc['origin_deadline'],generated_at=doc['generated_at'],**metrics(rows)),rows

def attach(source,result,traces,folder=DATA):
    source,folder=Path(source),Path(folder);manifest=json.loads((folder/'manifest.json').read_text())
    if manifest['schema']!='B-current-season-backtest-index-v1':raise ValueError('Invalid backtest index')
    if manifest['season']!=result['season']:return
    # The caller has already verified the historical files against their index.
    history=json.loads((source/'history/match-results.json').read_text());catalogue=json.loads((source/'history/current-players.json').read_text());fixtures=json.loads((source/'history/live-fixtures.json').read_text())
    weeks=[];allrows=[];by=defaultdict(list);out=source/'weekly-review';out.mkdir(exist_ok=True)
    for entry in manifest['weeks']:
        if entry['status']=='unsupported_model_warmup':weeks.append(dict(entry,scored_rows=0));continue
        path=folder/entry['file']
        if path.name!=entry['file']or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Backtest archive checksum mismatch')
        doc=json.loads(gzip.decompress(path.read_bytes()))
        if doc['gw']!=entry['gw']or doc.get('season')!=manifest['season']or doc.get('model_source')!=manifest['model_source']:raise ValueError('Wrong backtest origin/season/model')
        week,rows=score_forecast(doc,history,catalogue,fixtures);weeks.append(dict(week,file=entry['file'],sha256=entry['sha256']));allrows.extend(rows);(out/entry['file']).write_bytes(path.read_bytes())
        grouped=defaultdict(list)
        for r in rows:grouped[r['player_id']].append(r)
        for pid,group in grouped.items():
            by[pid].append(dict(gw=entry['gw'],xp=sum(r['xp']for r in group),expected_minutes=sum(r['expected_minutes']for r in group),pm_expected_minutes=sum(r['pm_expected_minutes']for r in group),p_start=[r['p_start']for r in group],actual_minutes=sum(r['actual_minutes']for r in group),actual_points=sum(r['actual_points']for r in group),actual_starts=sum(r['actual_starts']for r in group),final=True,cutoff=doc['cutoff'],generated_at=doc['generated_at']))
    raw=(json.dumps(dict(observed_at=history['observed_at'],records=allrows),sort_keys=True,allow_nan=False)+'\n').encode();(out/'backtest-outcomes.json').write_bytes(raw)
    result['historical_backtest']=dict(schema=manifest['schema'],scope=manifest['scope'],model_source=manifest['model_source'],model_policy_selected_after_targets=True,weeks=weeks,summary=metrics(allrows),minimum_prior_team_matches=manifest['minimum_prior_team_matches'],outcomes_sha256=hashlib.sha256(raw).hexdigest(),manifest_sha256=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),completed_scored_gws=sum(w['status']=='complete'for w in weeks),unsupported_gws=[w['gw']for w in weeks if w['status']=='unsupported_model_warmup'],notes=manifest['notes'])
    for p in traces['players']:
        rows=by.get(p['id'],[]);p['backtest_weeks']=rows;n=len(rows)
        p['backtest_summary']=dict(scored_gws=n,minute_mae=sum(abs(r['expected_minutes']-r['actual_minutes'])for r in rows)/n if n else None,xp_mae=sum(abs(r['xp']-r['actual_points'])for r in rows)/n if n else None,xp_bias=sum(r['xp']-r['actual_points']for r in rows)/n if n else None)
