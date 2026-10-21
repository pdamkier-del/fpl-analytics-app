"""One explicitly synthetic, private remote B regression; never a user team.

Receipts and full results stay in /tmp, never in public artifacts. Requires
--submit for the single opt-in POST; reruns resume the same idempotent receipt.
"""
import argparse,hashlib,json,secrets,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timedelta
import pandas as pd
from b_chain_contract import VERSION,validate_forecast
from b_preview_ts import ScenarioScorer
from fpl_v1_1_model.forecast_snapshot import require_snapshot
from fpl_xpts.optimize import optimize_squad_milp
from run_live_locked_ts import project

PUBLIC='https://pdamkier-del.github.io/fpl-analytics-app/'
API='https://fpl-analytics-private-manager.onrender.com'


def request(url,body=None,key=None):
    headers={'Origin':'https://pdamkier-del.github.io','Cache-Control':'no-cache'}
    if body is not None:headers['Content-Type']='application/json'
    if key:headers['X-Plan-Key']=key
    req=urllib.request.Request(url,data=json.dumps(body).encode()if body is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=90)as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        return e.code,json.load(e)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--submit',action='store_true');ap.add_argument('--receipt',type=Path,default=Path('/tmp/fpl-unified-private-service-receipt.json'))
    ap.add_argument('--out',type=Path,default=Path('/tmp/fpl-unified-private-service-proof.json'));args=ap.parse_args()
    _,f=request(PUBLIC+'mm-preview/current/forecast.json');require_snapshot(f);validate_forecast(f)
    _,health=request(API+'/health');assert health.get('supports_unified_B_chain')is True
    expected_worker=hashlib.sha256((Path(__file__).resolve().parents[1]/'service/preview_manager_job.py').read_bytes()).hexdigest()
    if health.get('preview_worker_sha256')!=expected_worker:
        raise SystemExit('Expected standalone B worker is not deployed; no validation job submitted')
    _,documents=request(PUBLIC+'mm-preview/current/existing-app-data.json')
    assert documents['forecast_sha256']==f['forecast_sha256']
    _,official=request('https://fantasy.premierleague.com/api/bootstrap-static/')
    baseline={p['id']:p for p in documents['documents']['current-players.json']['players']}
    assert set(baseline)=={p['id']for p in official['elements']}
    for player in official['elements']:
        old=baseline[player['id']]
        if any(old.get(k)!=player.get(k)for k in ['team','status','news','news_added','chance_of_playing_next_round','chance_of_playing_this_round']):
            raise SystemExit('Official player availability differs from forecast; refresh before submitting validation')
    if args.receipt.exists():
        saved=json.loads(args.receipt.read_text());body=saved['body']
        if body['forecast_sha256']!=f['forecast_sha256']:raise SystemExit('Saved validation receipt belongs to another forecast; no new job submitted')
    else:
        meta,origin=project(f);meta['price']=meta.price_tenths/10.;meta['status']='a'
        squad=optimize_squad_milp(origin,meta,f['gws'],budget=100.)
        if not squad.get('success'):raise ValueError('Cannot construct affordable synthetic validation fixture')
        prices=meta.set_index('id').price_tenths.to_dict();ids=squad['squad_ids'];gw=f['gws'][0]
        state=dict(season=f['season'],gw=gw,source='SYNTHETIC_REMOTE_REGRESSION_NOT_USER_TEAM',validation_only=True,
            observed_at=(datetime.fromisoformat(f['data_asof'].replace('Z','+00:00'))-timedelta(seconds=1)).isoformat(),
            bank_tenths=1000-sum(int(prices[i])for i in ids),free_transfers=0,
            squad=[dict(id=int(i),purchase_price_tenths=int(prices[i]))for i in ids],
            chips_used={c:[n]for c,n in zip(['wildcard','free_hit','bench_boost','triple_captain'],range(1,5))})
        if gw<=4:raise ValueError('Synthetic spent-chip history needs GW >4')
        body=dict(state=state,forecast_cutoff=f['data_asof'],forecast_sha256=f['forecast_sha256'],request_id=secrets.token_hex(16),request_key=secrets.token_urlsafe(32))
        saved={'body':body,'accepted':False};args.receipt.write_text(json.dumps(saved));args.receipt.chmod(0o600)
    if not saved['accepted']:
        if not args.submit:raise SystemExit('Fixture prepared locally; --submit is required for the single remote validation job')
        code,response=request(API+'/preview/plans',body)
        if code in (429,503):raise SystemExit('Private worker busy/unavailable; no job accepted and no existing computation interrupted')
        assert code==202,response
        assert response['id']==body['request_id']and response['key']==body['request_key']
        saved['accepted']=True;args.receipt.write_text(json.dumps(saved))
        print('One synthetic validation job accepted; no real manager state used',flush=True)
    endpoint=API+'/plans/'+body['request_id']
    code,_=request(endpoint);assert code==404,'Private result accessible without its key'
    deadline=time.monotonic()+1800
    while time.monotonic()<deadline:
        code,response=request(endpoint,key=body['request_key'])
        if code!=200:raise RuntimeError('Remote validation failed: '+str(response.get('error',code)))
        if response['status']=='completed':break
        print('Synthetic private B job running',flush=True);time.sleep(15)
    else:raise SystemExit('Validation job still pending; receipt retained for an idempotent resume')
    result=response['plan'];args.receipt.with_suffix('.result.json').write_text(json.dumps(result));args.receipt.with_suffix('.result.json').chmod(0o600)
    assert result['validation_only']is True and result['forecast_sha256']==f['forecast_sha256']
    assert result['calculation_runtime']=='B_unified_python'and result['chain_version']==VERSION
    assert len(result['plan']['path'])==len(f['gws'])and len(result['lineup'])==15
    assert sum(r['role']=='C'for r in result['lineup'])==sum(r['role']=='VC'for r in result['lineup'])==1
    scorer=ScenarioScorer(f)
    ids=tuple(sorted(r['id']for r in result['lineup']));decision=scorer.decision(f['gws'][0],ids)
    assert abs(decision[-1]-result['plan']['path'][0]['projected_manager_score'])<1e-8
    assert next(r['id']for r in result['lineup']if r['role']=='C')==decision[2]
    assert next(r['id']for r in result['lineup']if r['role']=='VC')==decision[3]
    own=tuple(sorted(r['id']for r in body['state']['squad']))
    assert abs(scorer.decision(f['gws'][0],own)[-1]-result['current_team']['expected_score'])<1e-8
    proof=dict(scope='SYNTHETIC_REMOTE_REGRESSION_NOT_USER_TEAM',actual_user_plan=False,validation_only=True,
        verified_at=datetime.now().astimezone().isoformat(),
        model=VERSION,forecast_sha256=f['forecast_sha256'],data_asof=f['data_asof'],six_GW_TS_completed=True,
        lineup_players=15,captain_and_vice_verified=True,score_matches_shared_PM_scenarios=True,
        private_key_required=True,official_FPL_actions=False,production_model_changed=False,
        private_receipt_or_state_published=False)
    args.out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2),flush=True)


if __name__=='__main__':main()
