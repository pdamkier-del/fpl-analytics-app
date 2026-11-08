from dataclasses import asdict
from datetime import datetime,timedelta,timezone
import hashlib,json
import pandas as pd
import pytest
from test_physical_timeline import fixture
from joint_substitution_capture import capture_inputs
from fpl_v1_1_model import experimental_physical_timeline as timeline
import run_joint_gk_preview as preview

def args():
 now=datetime.now(timezone.utc)
 return dict(data_asof=(now-timedelta(minutes=1)).isoformat(),deadline=(now+timedelta(days=1)).isoformat(),gw=12,validation_only=True)
def frame(inp,a):
 return pd.DataFrame([dict(target_gw=12,fixture_uuid='synthetic-capture',cutoff=a['data_asof'],player_uuid=p.player_id,team_news_availability_cap=0. if 'unavailable'in p.player_id else 1.)for p in inp.players])
def test_exact_capture_and_hook_restoration(tmp_path,monkeypatch):
 inp=fixture();a=args();f=frame(inp,a);monkeypatch.setattr(preview,'make_vfinal_input',lambda _: (inp,False));old_make=preview.make_vfinal_input;old_kernel=timeline.PhysicalKernel
 with capture_inputs(tmp_path,**a)as records:
  preview.make_vfinal_input(f);k=timeline.PhysicalKernel(inp);assert len(records)==1
  timeline.PhysicalKernel(inp);assert len(records)==1
 assert preview.make_vfinal_input is old_make and timeline.PhysicalKernel is old_kernel
 m=json.loads((tmp_path/'manifest.json').read_text());r=m['records'][0];raw=(tmp_path/r['file']).read_bytes();p=json.loads(raw);assert p['baseline']==json.loads(json.dumps(asdict(inp)));assert hashlib.sha256(raw).hexdigest()==r['sha256'];assert p['validation_only']
def test_target_labels_rejected_and_hooks_restored(tmp_path,monkeypatch):
 inp=fixture();a=args();f=frame(inp,a);f['actual_minutes']=90;monkeypatch.setattr(preview,'make_vfinal_input',lambda _:(inp,False));old=timeline.PhysicalKernel
 with pytest.raises(ValueError,match='outcomes'):
  with capture_inputs(tmp_path,**a):preview.make_vfinal_input(f)
 assert timeline.PhysicalKernel is old
def test_expired_capture_refused(tmp_path):
 a=args();a['deadline']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
 with pytest.raises(ValueError,match='before deadline'):
  with capture_inputs(tmp_path,**a):pass
