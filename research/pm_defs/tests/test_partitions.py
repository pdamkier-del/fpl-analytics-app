from pathlib import Path
import sys,importlib.util
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'research/pm_defs/code'))
from contracts import ContractError,Unidentified,dc_award,canonical_total,BASE
from partition_contract import replace_same_target_residual

def kwargs():return dict(old_known=10,old_residual=8,explicit_value=3,term='ordinary_inside_saves',explicit_before=['goals'],residual_excludes_before=['goals'],old_rulebook='fpl-2026-27-v1',new_rulebook='fpl-2026-27-v1',unit='bps_units')
def test_same_target_replacement_conserves_and_marks_exclusion():
 r=replace_same_target_residual(**kwargs());assert r['known']+r['residual']==18
 assert 'ordinary_inside_saves'in r['residual_excludes_after']
 with pytest.raises(ContractError):replace_same_target_residual(**(kwargs()|dict(residual_excludes_before=r['residual_excludes_after'])))

def test_cross_rule_target_transport_and_unit_confusion_are_blocked():
 with pytest.raises(Unidentified):replace_same_target_residual(**(kwargs()|dict(old_rulebook='fpl-2025-26-archive-v1')))
 with pytest.raises(ContractError):replace_same_target_residual(**(kwargs()|dict(unit='fpl_points')))

def test_known_BPS_save_partition_matches_archived_rule_primitive():
 p=ROOT/'analysis/audits/2026-11-22/code/reference/bps.py';spec=importlib.util.spec_from_file_location('pm_contract_bps_boundary',p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
 # Every other field is explicitly0in this synthetic fixture, not imputed data.
 fields={k:0 for k in m.BPSComponents.__dataclass_fields__};fields.update(position='GK',minutes=60,clean_sheet=1,saves_total=1,saves_inside_box=1,big_chance_saves=1,penalty_saves=1)
 assert m.bps_2026_27(m.BPSComponents(**fields))==3+12+2+1+1+7
 fields['minutes']=61;assert m.bps_2026_27(m.BPSComponents(**fields))==6+12+2+1+1+7

def test_same_action_may_legitimately_affect_DC_and_bonus_different_channels():
 # DC2and bonus3can coexist; CBI BPSunits must not be added as another point term.
 assert dc_award('DEF',10,'2026-27')==2
 values=dict.fromkeys(BASE,0);values.update(dc_points=2,bonus_points=3);assert canonical_total(values)==5
 with pytest.raises(ContractError):canonical_total(values|dict(bps_score=10//3))
