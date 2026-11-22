from pathlib import Path
import sys,copy,json,importlib.util
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'research/pm_defs/code'))
from contracts import *
def zero(**updates):return dict.fromkeys(BASE,0)|updates
def ledger(fixture=1,**values):
 return dict(catalog_id=CAT['catalog_id'],season='2026-27',gw=8,fixture_id=fixture,player_code=123,fpl_position_at_deadline='DEF',rulebook='fpl-2026-27-v1',source_sha256='a'*64,mode='actual',fields={k:dict(value=v,status='known',unit='fpl_points')for k,v in zero(**values).items()})
def test_catalog_is_complete_unique_partition_and_rule_versioned():
 assert len(DEFS)==len(CAT['components']);assert len(BASE)==10 and len(set(BASE))==10
 assert all(DEFS[k]['unit']=='fpl_points'and DEFS[k]['kind']=='additive_points'for k in BASE)
 assert 'bps_score'not in BASE and 'penalty_miss_points'not in BASE and 'expected_bonus'not in BASE
 assert CAT['rulebooks']['2026-27']['bps']['cbi_divisor']==3
 assert CAT['rulebooks']['2025-26']['bps']['cbi_divisor']==2
 assert not CAT['rulebooks']['2024-25']['dc_active']

def test_ledger_and_missingness_fail_closed():
 r=ledger();assert validate_ledger(r)
 r['fields']['save_points'].update(status='unknown',value=None,reason='not captured');assert validate_ledger(r)
 r['fields']['save_points']['value']=0
 with pytest.raises(ContractError,match='null'):validate_ledger(r)
 r=ledger();r['fields']['goal_points'].update(status='derived')
 with pytest.raises(ContractError,match='derivation'):validate_ledger(r)
 r=ledger();r['fields']['dc_points'].update(status='not_applicable',value=None)
 with pytest.raises(ContractError,match='reason'):validate_ledger(r)

def test_bounds_are_not_a_point_estimate():
 c=dict(status='bounded',value=None,unit='bps_units',reason='penalty-origin ambiguity',lower=-2,upper=0);validate_cell('background_bps',c,'actual')
 c['value']=-1
 with pytest.raises(ContractError):validate_cell('background_bps',c,'actual')
 c.update(value=None,lower=1)
 with pytest.raises(ContractError):validate_cell('background_bps',c,'actual')

def test_units_rule_season_identity_and_counts():
 r=ledger();r['season']='2025-26'
 with pytest.raises(ContractError,match='Season'):validate_ledger(r)
 r=ledger();r['fields']['goal_points']['unit']='bps_units'
 with pytest.raises(ContractError,match='Unit'):validate_ledger(r)
 r=ledger();r['player_code']=True
 with pytest.raises(ContractError):validate_ledger(r)
 with pytest.raises(ContractError):validate_cell('saves_total',dict(status='known',value=1.2,unit='saves'),'actual')
 validate_cell('bps_score',dict(status='known',value=-4,unit='bps_units'),'actual')
 with pytest.raises(ContractError):validate_cell('bps_score',dict(status='known',value=-4.2,unit='bps_units'),'actual')

def test_penalty_miss_and_goal_split_not_double_counted():
 assert canonical_total(zero(negative_points=-3)|dict(penalty_miss_points=-2))==-3
 assert canonical_total(zero(goal_points=10)|dict(penalty_goal_points=6,nonpenalty_goal_points=4))==10
 with pytest.raises(ContractError):canonical_total(zero()|dict(bps_score=6))
 with pytest.raises(ContractError):canonical_total(zero()|dict(expected_bonus=2))
 with pytest.raises(Unidentified):canonical_total(zero()|dict(goal_points=None))
 with pytest.raises(ContractError):canonical_total(zero(goal_points=10)|dict(penalty_goal_points=6,nonpenalty_goal_points=6))

def test_inclusive_penalty_saves_and_overlapping_subtypes():
 # Two total saves include one saved penalty: not3saves, so ordinary points0.
 assert save_points(2,save_scope='fpl_inclusive_including_penalty_saves')+5==5
 assert save_subtypes(1,1,1,1) # Inside/big overlap, no sum<=total restriction.
 assert save_bps_2026(1,1,1,1)==11 #2+1+1+7, BPS not FPLpoints.
 with pytest.raises(Unidentified):save_bps_2026(2,1,None,1)
 with pytest.raises(ContractError):save_subtypes(1,0,0,1)
 with pytest.raises(ContractError):save_points(2,save_scope='ordinary_only')

def test_expected_buckets_and_thresholds_require_distribution():
 ep=sum(save_points(x,save_scope='fpl_inclusive_including_penalty_saves')for x in [2,4])/2
 assert ep==.5 and floor(((2+4)/2)/3)==1
 assert sum(dc_award('DEF',x,'2026-27')for x in [0,20])/2==1
 assert dc_award('DEF',10,'2026-27')==2
 assert dc_award('DEF',20,'2026-27')==2 and dc_award('MID',11,'2026-27')==0
 assert dc_award('GK',None,'2026-27')==0 and dc_award('DEF',None,'2024-25')==0

def test_CS_clock_scope_and_joint_probability():
 assert qualify_cs(59,0,liability_scope='fpl_liability',red_card=False)==0
 assert qualify_cs(60,0,liability_scope='fpl_liability',red_card=False)==1
 with pytest.raises(Unidentified):qualify_cs(60,0,liability_scope='on_pitch_only',red_card=True)
 with pytest.raises(Unidentified):qualify_cs(60,0,liability_scope='on_pitch_only',red_card=None)
 assert qualify_cs(60,1,liability_scope='fpl_liability',red_card=True)==0
 assert 4*sum(q*z for q,z in [(0,0),(1,1)])/2==2
 assert 4*(.5*.5)==1 # Product of marginals fails under dependence.

def test_background_retargeting_conserves_BPS_and_rejects_second_subtraction():
 k,r=retarget_background(10,8,3,residual_excludes_new=False);assert (k,r)==(13,5)and k+r==18
 with pytest.raises(ContractError):retarget_background(10,8,3,residual_excludes_new=True)

def test_bonus_ties_negative_BPS_and_mean_not_rank():
 assert complete_fixture_bonus({'a':0,'b':0,'c':-2},{'a':True,'b':True,'c':True},complete=True)=={'a':3,'b':3,'c':1}
 with pytest.raises(Unidentified):complete_fixture_bonus({'a':5},{'a':True},complete=False)
 x=complete_fixture_bonus({'a':10,'b':0,'c':-1},dict(a=True,b=True,c=True),complete=True)
 y=complete_fixture_bonus({'a':0,'b':10,'c':-1},dict(a=True,b=True,c=True),complete=True)
 means=complete_fixture_bonus({'a':5,'b':5,'c':-1},dict(a=True,b=True,c=True),complete=True)
 assert (x['a']+y['a'])/2==2.5 and means['a']==3
 # Reuse the archived pure tie primitive on synthetic contract examples only.
 spec=importlib.util.spec_from_file_location('pm_defs_archived_bps',ROOT/'analysis/audits/2026-11-22/code/reference/bps.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
 assert m.allocate_bonus_points({'a':0,'b':0,'c':-2})=={'a':3,'b':3,'c':1}

def test_goal_categories_own_goal_and_assist_identity():
 assert goal_identity(3,2,1,0)
 with pytest.raises(Unidentified):goal_identity(3,2,1,None)
 with pytest.raises(ContractError):goal_identity(3,3,1,0)
 assert validate_goal_events([dict(event_id='g1',category='penalty',scorer_id=1,assist_id=2),dict(event_id='g2',category='own_goal',scorer_id=3,assist_id=2)])
 with pytest.raises(ContractError):validate_goal_events([dict(event_id='g1',category='ordinary',scorer_id=1,assist_id=1)])
 with pytest.raises(ContractError):validate_goal_events([dict(event_id='g1',category='own_goal'),dict(event_id='g1',category='own_goal')])

def test_zero_reported_minutes_does_not_erase_card_points():
 r=ledger(negative_points=-3);assert validate_ledger(r);assert aggregate_fixture_ledgers([r])==-3
 # No minutes gate forces all components to0. Actual official awards govern.

def test_DGW_aggregation_per_fixture_not_pooled_counts_and_no_duplicates():
 assert dc_award('DEF',6,'2026-27')+dc_award('DEF',6,'2026-27')==0
 a=ledger(1,appearance_points=1);b=ledger(2,appearance_points=1)
 assert aggregate_fixture_ledgers([a,b])==2
 with pytest.raises(ContractError):aggregate_fixture_ledgers([a,a])
 b['player_code']=124
 with pytest.raises(ContractError):aggregate_fixture_ledgers([a,b])
 with pytest.raises(Unidentified):aggregate_fixture_ledgers([])

def test_original_issue_clock_is_strict_and_timezone_aware():
 assert validate_forecast_clock('2026-11-01T10:00:00Z','2026-11-01T11:00:00Z','2026-11-01T12:00:00Z')
 with pytest.raises(ContractError):validate_forecast_clock('2026-11-01T10:00:00Z','2026-11-01T12:00:00Z','2026-11-01T12:00:00Z')
 with pytest.raises(ContractError):validate_forecast_clock('2026-11-01T10:00:00','2026-11-01T11:00:00','2026-11-01T12:00:00')
