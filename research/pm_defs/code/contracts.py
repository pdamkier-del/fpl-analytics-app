"""Research-only versioned PM data contracts. No production imports or models."""
from pathlib import Path
from math import isfinite,floor
from datetime import datetime
from collections import Counter
import json,re
S=Path(__file__).resolve().parents[1]
CAT=json.loads((S/'catalog.v1.json').read_text());BASE=tuple(CAT['canonical_additive_partition']);DEFS={r['id']:r for r in CAT['components']};POSITIONS=('GK','DEF','MID','FWD')
class ContractError(ValueError):pass
class Unidentified(ContractError):pass

def number(x):
 if isinstance(x,bool)or not isinstance(x,(int,float))or not isfinite(x):raise ContractError('Finite numeric value required; bool is not a count')
 return x

def count(x):
 number(x)
 if int(x)!=x or x<0:raise ContractError('Count must be a nonnegative integer')
 return int(x)

def validate_cell(field,cell,mode):
 if field not in DEFS:raise ContractError('Undefined catalog field: '+field)
 if not all(k in cell for k in ['status','value','unit']):raise ContractError('Status, value and unit required')
 if cell['unit']!=DEFS[field]['unit']:raise ContractError('Unit mismatch: '+field)
 status=cell['status'];value=cell['value']
 if status not in CAT['value_statuses']:raise ContractError('Unknown missingness state')
 if status in ('unknown','not_applicable','bounded'):
  if value is not None or not cell.get('reason'):raise ContractError('Unavailable values require null and reason, never numeric0')
  if status=='bounded':
   lo=number(cell.get('lower'));hi=number(cell.get('upper'))
   if lo>hi:raise ContractError('Reversed identification bounds')
  return
 number(value)
 if status=='derived'and not cell.get('derivation'):raise ContractError('Derived target needs its derivation/version')
 if mode=='actual'and field=='bps_score'and int(value)!=value:raise ContractError('Observed BPS must be signed integer')
 if mode=='actual'and DEFS[field]['unit']in ('goals','assists','actions','saves'):count(value)
 if field in ['team_clean_sheet','qualified_player_clean_sheet']and not 0<=value<=1:raise ContractError('Invalid probability/indicator')
 if field in ['negative_points','gc_points','penalty_miss_points']and value>0:raise ContractError('Negative component has positive sign')
 if field=='dc_points'and not 0<=value<=2:raise ContractError('DCpoint award is capped per fixture')
 if field=='appearance_points'and not 0<=value<=2:raise ContractError('Appearance points are per fixture')
 if field in ['bonus','expected_bonus','bonus_points']and not 0<=value<=3:raise ContractError('Invalid bonus award/mean')
 if field in ['saves_total','player_goals','fpl_assists','dc_count']and value<0:raise ContractError('Negative event count/mean')

def validate_ledger(row):
 required=['catalog_id',*CAT['required_identity'],'mode','fields']
 if any(k not in row for k in required):raise ContractError('Fixture identity or fields missing')
 if set(row)-set(required):raise ContractError('Unexpected ledger fields; use a versioned schema')
 if row['catalog_id']!=CAT['catalog_id']or row['mode']not in ('actual','forecast'):raise ContractError('Catalog/mode mismatch')
 rules=CAT['rulebooks'].get(row['season'])
 if not rules or row['rulebook']!=rules['id']:raise ContractError('Season/rulebook mismatch')
 for k in ['gw','fixture_id','player_code']:
  if count(row[k])<1:raise ContractError('Positive fixture/player/GW identity required')
 if row['gw']>38 or row['fpl_position_at_deadline']not in POSITIONS:raise ContractError('Invalid GW or FPL position')
 if not re.fullmatch('[0-9a-f]{64}',row['source_sha256']):raise ContractError('Invalid source checksum')
 for name,c in row['fields'].items():validate_cell(name,c,row['mode'])
 return True

def canonical_total(values,unit='fpl_points'):
 if unit!='fpl_points':raise ContractError('BPS or event counts cannot enter FPLpoint total')
 if any(k not in values or values[k]is None for k in BASE):raise Unidentified('Missing canonical component, not zero')
 allowed=set(BASE)|{'penalty_miss_points','penalty_goal_points','nonpenalty_goal_points'}
 if set(values)-allowed:raise ContractError('Unknown/additional additive component or bonus alias')
 for v in values.values():
  if v is not None:number(v)
 if values.get('penalty_miss_points')is not None:
  if not values['negative_points']<=values['penalty_miss_points']<=0:raise ContractError('Penalty miss diagnostic is not a negative_points subset')
 split=[values.get('penalty_goal_points'),values.get('nonpenalty_goal_points')]
 if any(v is not None for v in split):
  if any(v is None for v in split):raise Unidentified('Incomplete goal partition')
  if abs(sum(split)-values['goal_points'])>1e-9:raise ContractError('Penalty/nonpenalty partition does not conserve goal points')
 return sum(values[k]for k in BASE)

def qualify_cs(fpl_minutes,liability_goals,*,liability_scope,red_card):
 count(fpl_minutes);count(liability_goals)
 if liability_scope not in ['fpl_liability','on_pitch_only']:raise ContractError('Unknown concession clock/scope')
 if red_card is not False and liability_scope=='on_pitch_only':raise Unidentified('Post-dismissal concession liability not observed')
 return int(fpl_minutes>=60 and liability_goals==0)

def dc_award(position,value,season):
 if position not in POSITIONS or season not in CAT['rulebooks']:raise ContractError('Unknown position/season')
 if season=='2024-25':return 0 # Structural absence of rule, not an imputed action count.
 t={'GK':None,'DEF':10,'MID':12,'FWD':12}[position]
 if t is None:return 0
 return 2*int(count(value)>=t)

def save_points(total_saves,*,save_scope):
 if save_scope!='fpl_inclusive_including_penalty_saves':raise ContractError('Save target must be inclusive, not ordinary-only')
 return count(total_saves)//3

def save_subtypes(total,inside,big,penalty):
 total=count(total);penalty=count(penalty)
 if penalty>total:raise ContractError('Penalty saves exceed inclusive total')
 for name,v in [('inside',inside),('big_chance',big)]:
  if v is None:raise Unidentified('Missing save subtype: '+name)
  if count(v)>total:raise ContractError('Save subtype exceeds total')
 if inside<penalty or big<penalty:raise ContractError('Standardized saved penalties belong to inside/big-chance subsets')
 # Inside and big-chance sets overlap; never require inside+big<=total.
 return True

def save_bps_2026(total,inside,big,penalty):
 save_subtypes(total,inside,big,penalty)
 return 2*total+inside+big+7*penalty

def retarget_background(old_known,old_residual,new_explicit,*,residual_excludes_new):
 for x in [old_known,old_residual,new_explicit]:number(x)
 if residual_excludes_new:raise ContractError('Term was already excluded from residual; cannot subtract it again')
 return old_known+new_explicit,old_residual-new_explicit

def complete_fixture_bonus(bps,participants,*,complete):
 if not bps or not complete or set(bps)!=set(participants)or not all(participants.values()):raise Unidentified('Complete actual-participant fixture roster is required, not fantasy XV')
 for value in bps.values():
  number(value)
  if int(value)!=value:raise ContractError('Observed BPS must be integer; negative is allowed')
 # Competition ranking including ties; no positive-only BPS filter or sum6assumption.
 return {p:(3-sum(v>score for v in bps.values())if sum(v>score for v in bps.values())<3 else 0)for p,score in bps.items()}

def goal_identity(team_goals,credited,opponent_own,unattributed):
 if any(v is None for v in [team_goals,credited,opponent_own,unattributed]):raise Unidentified('Incomplete goal categories')
 for v in [team_goals,credited,opponent_own,unattributed]:count(v)
 if team_goals!=credited+opponent_own+unattributed:raise ContractError('Inclusive team goal conservation failed')
 return True

def aggregate_fixture_ledgers(rows):
 rows=list(rows)
 if not rows:raise Unidentified('No fixture labels is not proof of a blank or zero')
 seen=set();total=0.;group=None
 for r in rows:
  validate_ledger(r);current=(r['season'],r['gw'],r['player_code'],r['mode'],r['rulebook'],r['fpl_position_at_deadline'])
  if group is None:group=current
  elif current!=group:raise ContractError('Do not aggregate different players/GWs/rulebooks')
  key=(r['season'],r['fixture_id'],r['player_code'])
  if key in seen:raise ContractError('Duplicate fixture/player labels or revisions; choose one explicit label version')
  seen.add(key);values={k:c['value']for k,c in r['fields'].items()};total+=canonical_total(values)
 return total

def validate_forecast_clock(cutoff,published,deadline):
 values=[datetime.fromisoformat(s.replace('Z','+00:00'))for s in [cutoff,published,deadline]]
 if any(v.tzinfo is None for v in values):raise ContractError('Timezone-aware issue/publication/deadline required')
 if not values[0]<=values[1]<values[2]:raise ContractError('Forecast is not an original before-deadline issue')
 return True

def validate_goal_events(events):
 seen=set()
 for e in events:
  if not e.get('event_id')or e['event_id']in seen:raise ContractError('Duplicate or missing goal event identity')
  seen.add(e['event_id'])
  if e.get('category')not in ['ordinary','penalty','own_goal','unattributed']:raise ContractError('Unknown goal category, not an ordinary-goal default')
  if e.get('assist_id')is not None and e.get('assist_id')==e.get('scorer_id'):raise ContractError('No self-assist')
  if e['category']in ['ordinary','penalty']and e.get('scorer_id')is None:raise Unidentified('Unattributed goal requires its explicit category')
 return True
