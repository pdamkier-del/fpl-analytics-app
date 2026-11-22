"""Reuse the existing tiny six-GW regression fixture; never refit or run a match model."""
import os,sys,copy
from pathlib import Path
import pytest
from test_ts_capture import store
from evaluation_ops import ts_capture as cap

def test_original_worker_output_can_be_archived_without_model_changes(store):
 ref=os.environ.get('FPL_FROZEN_REFERENCE')
 if not ref:pytest.skip('Set FPL_FROZEN_REFERENCE to the verified frozen runtime checkout')
 ref=Path(ref)
 for path in [ref,ref/'src',ref/'scripts',ref/'tests']:sys.path.append(str(path))
 from test_unified_b_chain import unified_fixture
 from service.preview_manager_job import calculate
 import fpl_xpts.transfer_planner as planner
 f,s=unified_fixture();s['bank_tenths']=50;before=copy.deepcopy(s);original=planner._fast_manager_score;result=calculate(f,s);saved=copy.deepcopy(result);assert result['current_team']['expected_score']==pytest.approx(47.6)
 reply=cap.after_success(f,s,result);assert reply['status']=='recorded_private',reply;assert result==saved and s==before and planner._fast_manager_score is original
 record=cap.ledger.json.loads(cap.ledger.gzip.decompress(next(store.glob('record-*')).read_bytes()));assert record['manager_decision']is None;assert len(record['recommendation']['plan']['path'])==6
