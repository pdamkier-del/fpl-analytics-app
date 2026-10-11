#!/usr/bin/env python3
"""External private manager smoke with an explicitly SYNTHETIC legal squad."""
import json,time,urllib.request,urllib.error,os,hashlib
APP='https://pdamkier-del.github.io/fpl-analytics-app/'
API='https://fpl-analytics-private-manager.onrender.com'
ORIGIN='https://pdamkier-del.github.io'

def http(url,method='GET',body=None,key=None,timeout=110):
    headers={'User-Agent':'FPLSyntheticManagerE2E/1','Cache-Control':'no-cache'}
    if url.startswith(API):headers['Origin']=ORIGIN
    if body is not None:headers['Content-Type']='application/json'
    if key:headers['X-Plan-Key']=key
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as err:return err.code,json.loads(err.read())

def main():
    status,forecast=http(APP+'vfinal-diagnostic.json')
    assert status==200 and forecast['model']=='original_locked_vFinal_diagnostic'
    status,official=http(APP+'current-players.json')
    assert status==200 and forecast['gws'][0]==official['next_gw'],'Mismatch with official GW'
    assert forecast['locked_model_active'] is False
    clubs={};picked=[]
    for pos,count in [(1,2),(2,5),(3,5),(4,3)]:
        candidates=sorted((p for p in forecast['players'] if p['position']==pos),key=lambda p:(p['price_tenths'],p['id']))
        for p in candidates:
            if clubs.get(p['team_id'],0)>=3:continue
            picked.append(p);clubs[p['team_id']]=clubs.get(p['team_id'],0)+1;count-=1
            if count==0:break
        assert count==0,'Unable to create synthetic legal squad'
    cost=sum(p['price_tenths'] for p in picked)
    assert cost<=1000,'Synthetic fixture exceeds budget'
    squad={'season':forecast['season'],'gw':forecast['gws'][0],
        'source':'SYNTHETIC_HTTP_SMOKE_NOT_AN_ACTUAL_FPL_MANAGER',
        'observed_at':forecast['data_asof'],'bank_tenths':1000-cost,'free_transfers':2,
        'squad':[{'id':p['id'],'purchase_price_tenths':p['price_tenths']} for p in picked],
        'chips_used':{k:[] for k in ('wildcard','free_hit','bench_boost','triple_captain')}}
    status,response=http(API+'/plans',method='POST',body={'state':squad,'forecast_cutoff':forecast['data_asof']})
    assert status==202,(status,response)
    identifier=response['id'];key=response['key']
    assert identifier and key
    print('External synthetic legal manager job accepted (no user data)',flush=True)
    for attempt in range(180):
        time.sleep(10)
        status,reply=http(API+'/plans/'+identifier,key=key)
        if status!=200:raise RuntimeError('External manager job failed: HTTP '+str(status)+' '+str(reply.get('error','')))
        if reply['status']=='failed':raise RuntimeError('Original TS/chip worker failed: '+str(reply.get('error','')))
        if reply['status']=='completed':
            plan=reply['plan']
            assert plan['ts_ran'] and not plan.get('validation_only')
            assert plan['locked_model_active'] is False
            assert plan['forecast_cutoff']==forecast['data_asof']
            assert plan['gw']==forecast['gws'][0]
            assert len(plan['plan']['path'])==len(forecast['gws'])
            assert len(plan['lineup'])==15
            assert plan['calculation_runtime']=='original_locked_python'
            print('PASS: original Python TS, legal synthetic lineup and private response through external Render API',flush=True)
            print('chips_ran:',plan.get('chips_ran'),'chips_status:',plan.get('chips_status'),flush=True)
            return
        if attempt%6==5:print('Synthetic job still running at minute', (attempt+1)//6,flush=True)
    raise TimeoutError('Private manager job did not finish within 30 minutes')

if __name__=='__main__':main()
