from datetime import datetime,timedelta,timezone
import gzip,json
import numpy as np
import pytest
from joint_substitution_automation import bounds,pack,score,utc

def test_prospective_clocks_and_naive_clock_rejected():
 now=datetime.now(timezone.utc);bounds((now-timedelta(hours=1)).isoformat(),(now+timedelta(days=1)).isoformat(),now)
 with pytest.raises(ValueError):bounds((now-timedelta(days=2)).isoformat(),(now+timedelta(days=1)).isoformat(),now)
 with pytest.raises(ValueError):bounds((now-timedelta(days=1)).isoformat(),(now-timedelta(hours=1)).isoformat(),now)
 with pytest.raises(ValueError):utc('2026-01-01T00:00:00')
def test_pending_round_never_uses_results(tmp_path,monkeypatch):
 now=datetime.now(timezone.utc);folder=tmp_path/'2026-27/GW11';folder.mkdir(parents=True);data={'validation_only':False,'season':'2026-27','gw':11,'issued_at':now.isoformat(),'deadline':(now+timedelta(days=1)).isoformat(),'rows':[]};(folder/'capture.json.gz').write_bytes(pack(data))
 import requests
 class Response:
  def raise_for_status(self):pass
  def json(self):return {'events':[{'id':11,'finished':False,'data_checked':False}],'elements':[]}
 seen=[]
 def get(url,**kwargs):seen.append(url);return Response()
 monkeypatch.setattr(requests,'get',get);report=score(tmp_path);assert report['completed_gws']==0 and report['rounds'][0]['status']=='pending_results';assert len(seen)==1

def test_final_round_scored_from_immutable_draws_and_latest_eligible_capture(tmp_path,monkeypatch):
 now=datetime.now(timezone.utc);folder=tmp_path/'2026-27/GW10';folder.mkdir(parents=True)
 row={'id':1,'code':123,'fixture':'f','pstart':.8,'baseline_points':[0,0,4,4],'candidate_points':[0,2,2,4],'baseline_minutes':60,'candidate_minutes':65,'baseline_p90':.4,'candidate_p90':.3}
 data={'validation_only':False,'season':'2026-27','gw':10,'issued_at':(now-timedelta(days=3)).isoformat(),'deadline':(now-timedelta(days=2)).isoformat(),'rows':[row]};(folder/'valid.json.gz').write_bytes(pack(data));late=dict(data,issued_at=now.isoformat());(folder/'late.json.gz').write_bytes(pack(late))
 import requests
 class Response:
  def __init__(self,url):self.url=url
  def raise_for_status(self):pass
  def json(self):return {'events':[{'id':10,'finished':True,'data_checked':True}],'elements':[{'id':1,'code':123}]}if 'bootstrap' in self.url else {'elements':[{'id':1,'stats':{'minutes':60,'total_points':2}}]}
 monkeypatch.setattr(requests,'get',lambda url,**kwargs:Response(url));r=score(tmp_path);assert r['completed_gws']==1;assert r['rounds'][0]['source'].endswith('valid.json.gz');assert r['summary']['active']['candidate']['crps']<r['summary']['active']['baseline']['crps'];assert r['app_model_changed'] is False
