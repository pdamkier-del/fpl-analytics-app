from pathlib import Path
import sys,pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'research/pm_defs/code'))
from identifiability import binary_award_probability
from contracts import ContractError,Unidentified

def test_DC_binary_event_identified_even_when_full_count_law_missing():
 assert binary_award_probability(.8,target='dc_hit',position='MID',season='2026-27')==.4
 assert binary_award_probability(1,target='qualified_player_CS',position='DEF',season='2026-27')==.25

def test_no_teamCS_bonus_or_old_DC_inversion_and_no_DGW_unit_confusion():
 for target,position,season in [('team_CS','DEF','2026-27'),('qualified_player_CS','FWD','2026-27'),('dc_hit','DEF','2024-25'),('bonus_any','DEF','2026-27')]:
  with pytest.raises(Unidentified):binary_award_probability(0,target=target,position=position,season=season)
 with pytest.raises(ContractError):binary_award_probability(3,target='dc_hit',position='MID',season='2026-27')
