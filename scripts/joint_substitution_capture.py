"""Optional exact-input recorder for research; never installed by app entry points."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,re
import numpy as np


def utc(value):
 result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if result.tzinfo is None:raise ValueError('Timezone required')
 return result.astimezone(timezone.utc)

def encoded(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=lambda x:x.item()if isinstance(x,np.generic)else str(x)).encode()

@contextmanager
def capture_inputs(directory,*,data_asof,deadline,gw,validation_only=False):
 """Record first primary-kernel construction per origin fixture, without changing it.

 Caller must wrap the existing role-enabled primary B run before any controls.
 The recorder is opt-in, single-process, and restores both hooks on exit.
 Raw target outcomes are rejected. Medical caps must come from source fields.
 This records inputs, not an independently published candidate forecast.
 """
 import run_joint_gk_preview as preview
 from fpl_v1_1_model import experimental_physical_timeline as timeline
 begin=datetime.now(timezone.utc);cut=utc(data_asof);end=utc(deadline)
 if not cut<=begin<end:raise ValueError('Capture must occur after source cutoff and before deadline')
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);old_make=preview.make_vfinal_input;old_kernel=timeline.PhysicalKernel;active={};records=[];seen=set()
 def make(frame):
  active.clear()
  if frame.target_gw.nunique()!=1 or frame.fixture_uuid.nunique()!=1:raise ValueError('One fixture required')
  if int(frame.target_gw.iloc[0])==gw:
   if {'actual_minutes','actual_start','actual_points','started','minutes','total_points'}&set(frame):raise ValueError('Target outcomes forbidden')
   if 'team_news_availability_cap'not in frame:raise ValueError('Explicit source availability caps missing')
   caps={str(r.player_uuid):float(r.team_news_availability_cap)for r in frame.itertuples()}
   if any(not np.isfinite(v)or not 0<=v<=1 for v in caps.values()):raise ValueError('Invalid source availability caps')
   if any(utc(v)>cut for v in frame.cutoff.unique()):raise ValueError('Frame is newer than declared source cutoff')
   active.update(fixture=str(frame.fixture_uuid.iloc[0]),medical_caps=caps)
  return old_make(frame)
 class Recorder(old_kernel):
  def __init__(self,inp,role_distributions=None,**kwargs):
   super().__init__(inp,role_distributions,**kwargs)
   if not active or active['fixture']in seen:return
   fx=active['fixture']
   if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',fx):raise ValueError('Unsafe fixture identity')
   now=datetime.now(timezone.utc)
   if not now<end:raise ValueError('Deadline crossed during capture')
   cap={p.player_id:active['medical_caps'][p.player_id]for p in inp.players if not p.is_keeper}
   if any(p.p_start>cap[p.player_id]+2e-6 for p in inp.players if not p.is_keeper):raise ValueError('Start probability exceeds captured availability')
   payload={'schema':'joint-substitution-input-capsule-v1','fixture':fx,'gw':gw,'data_asof':cut.isoformat(),'captured_at':now.isoformat(),'origin_deadline':end.isoformat(),'validation_only':validation_only,'baseline':asdict(inp),'medical_caps':cap,'dist':{str(k):[asdict(v)for v in values]for k,values in (role_distributions or {}).items()}}
   raw=encoded(payload);path=directory/(fx+'.json')
   with path.open('xb')as stream:stream.write(raw)
   records.append({'file':path.name,'sha256':hashlib.sha256(raw).hexdigest()});seen.add(fx)
 preview.make_vfinal_input=make;timeline.PhysicalKernel=Recorder
 try:
  yield records
 finally:
  preview.make_vfinal_input=old_make;timeline.PhysicalKernel=old_kernel
  if records:
   manifest={'schema':'joint-substitution-input-manifest-v1','gw':gw,'data_asof':cut.isoformat(),'origin_deadline':end.isoformat(),'captured_at':datetime.now(timezone.utc).isoformat(),'validation_only':validation_only,'records':records,'scope':'Exact baseline inputs only; not a candidate publication or independent validation'}
   with (directory/'manifest.json').open('xb')as stream:stream.write(encoded(manifest))
