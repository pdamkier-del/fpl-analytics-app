#!/usr/bin/env python3
"""Evidence-first live PM/vFinal readiness probe.

Never scores points, substitutes missing forecasts, or certifies the final
chain. Verify frozen model availability and actual 2026 data coverage.
"""
from __future__ import annotations
from pathlib import Path
import gzip,json,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_rolling_vfinal_gw6_38 import load_models
from fpl_v1_1_model.role_event_priors import QCOLS
WORK=ROOT/'work/live-final-model'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
OUT=WORK/'live_vfinal_readiness.json'

def main():
    models=load_models()
    mm=pd.read_csv(WORK/'mm_frozen_diagnostic_six_gw.csv.gz',low_memory=False)
    past=pd.read_csv(BASE/'player_fixture_observations.csv.gz',low_memory=False)
    fixtures=json.loads((WORK/'fixtures.json').read_text())
    events=[json.loads(x) for x in gzip.decompress((WORK/'player_match_events.jsonl.gz').read_bytes()).splitlines()]
    source=json.loads((WORK/'source_manifest.json').read_text())
    origin=int(source['target_gw'])
    raw_count=mm.groupby('target_gw').agg(player_rows=('fpl_element','size'),
          players=('fpl_element','nunique'),fixtures=('fixture_uuid','nunique')).reset_index().to_dict('records')
    required={'player_uuid','team_id','gw','pos','xmins','p_start','mm_q_sub',
         'mm_sub_minutes','expected_role','cutoff','max_history_known_at',*QCOLS}
    missing=sorted(required-set(mm.columns))
    histfields=['fixture_uuid','player_uuid','team_id','opponent_team_id','gw',
                'kickoff_at','minutes','xg','xa','defcon_count','yellow_cards',
                'fpl_red_cards','own_goals','goals','fpl_assists','saves','bps']
    actuals={}
    for key in histfields:
        if key not in past:actuals[key]={'rows':0,'issue':'column not provided'}
        else:
            v=past[key]
            actuals[key]={'rows':int(v.notna().sum()),'share':round(float(v.notna().mean()),4)}
    # Frozen rolling vFinal uses known team-xG, team-shots-on-target and
    # longitudinal penalty-taker states, not just a player-fixture table.
    raw_dir=ROOT/'data_v1_1/raw/all-competitions-2026-27'
    collected_files=sorted(p.name for p in raw_dir.glob('*.csv')) if raw_dir.exists() else []
    raws=[]
    for event in events:
        vals=event.get('stats') or {}
        if not isinstance(vals,dict):continue
        raws.append(vals)
    keys=('expected_goals','expected_assists','ShotsOnTarget','accurate_passes',
          'saves','tackles_won','matchstats.headers.tackles','rating_title')
    event_coverage={k:sum(k in s and s[k] is not None for s in raws) for k in keys}
    team_xg_usable=0
    if all(k in past for k in ('fixture_uuid','team_id','xg')):
        x=past[['fixture_uuid','team_id','xg']]
        team_xg_usable=int(x.groupby(['fixture_uuid','team_id']).xg.apply(
           lambda s:s.notna().sum()>=11).sum())
    official_games=[r for r in fixtures if r.get('event') is not None
                    and origin<=int(r['event'])<=min(38,origin+5)
                    and not r.get('finished')]
    blockers=[]
    if missing:blockers.append('MM source lacks '+', '.join(missing))
    if mm.target_gw.nunique()!=6:blockers.append('Missing some future GW forecasts')
    if not official_games:blockers.append('Official future fixture schedule unavailable')
    if 'team_fixture_observations.csv.gz' not in collected_files:
        blockers.append('Team xG / shots-on-target source layer not built; PM team latent and keeper-save inputs not certified')
    if 'penalty_taker_state.csv.gz' not in collected_files:
        blockers.append('2026/27 pre-cutoff penalty taker/team rate state not independently reconstructed')
    if 'bps_background_state.csv.gz' not in collected_files:
        blockers.append('Current-season BPS background distribution not reconstructed against original features')
    training=json.loads((WORK/'live_training_provenance.json').read_text())
    if not training.get('live_certified'):
        blockers.append('MM inherited reconstructed rather than verified historical predeadline rosters')
    result={'status':'PM_VFINAL_SOURCE_AUDIT_NOT_A_FINAL_FORECAST',
        'locked_model_active':False,'season':'2026-27','origin_gw':origin,
        'frozen_models_loaded':sorted(models),'full_frozen_models_load_success':True,
        'mm_six_gw_player_fixture_rows':len(mm),'mm_missing_input_columns':missing,
        'mm_by_gw':raw_count,
        'historical_player_fixture_rows':len(past),
        'historical_field_coverage':actuals,
        'historical_team_fixtures_with_at_least_11_player_xg':team_xg_usable,
        'observed_provider_events':len(events),'provider_field_coverage':event_coverage,
        'future_schedule_fixtures':len(official_games),
        'raw_current_competition_csvs':collected_files,
        'blockers':blockers,
        'vfinal_fixture_simulation_completed':False,
        'TS_and_chips_completed':False,
        'full_final_chain_certified':False}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('FROZEN VFINAL CURRENT SOURCE AUDIT:',json.dumps({
       'frozen_models':result['frozen_models_loaded'],
       'mm_rows':len(mm),'historic_rows':len(past),
       'future_games':len(official_games),
       'team_xg_sides_11_player_coverage':team_xg_usable,
       'blockers':blockers,
       'stat_coverage':actuals
    },ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':main()
