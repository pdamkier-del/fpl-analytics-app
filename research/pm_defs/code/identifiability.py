"""Exact target identifiability from fixed binary point awards, not a model fit."""
from contracts import CAT,ContractError,Unidentified,number

def binary_award_probability(expected_points,*,target,position,season):
 if season not in CAT['rulebooks']:raise ContractError('Unknown rulebook')
 if target=='dc_hit':
  if season=='2024-25'or position=='GK':raise Unidentified('DCaward is not applicable; do not invent an event probability')
  if position not in ('DEF','MID','FWD'):raise ContractError('Unknown position')
  award=2
 elif target=='qualified_player_CS'and season=='2026-27':
  award=CAT['rulebooks'][season]['cs_points'].get(position)
  if not award:raise Unidentified('Zero positional award cannot identify CSprobability')
 else:raise Unidentified('This target is not an identified fixed binary award; teamCS/bonus/save-count inference is invalid')
 value=number(expected_points)
 if not 0<=value<=award:raise ContractError('Expected binary award outside support; check per-fixture vs DGWunits')
 return value/award
