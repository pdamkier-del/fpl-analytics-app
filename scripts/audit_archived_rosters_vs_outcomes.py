#!/usr/bin/env python3
"""Audit actual historical gameweek observations against archived predeadline FPL rosters.

Genuine predeadline snapshot is separate from postmatch observation and
must NOT be assumed equivalent. Never silently use unmatched players/teams.
"""
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/live-final-model'
ARCH=WORK/'predeadline_2026_archives'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'

def audit():
    hist=pd.read_csv(BASE/'player_fixture_observations.csv.gz')
    groups=[]
    for gw in range(1,6):
        data=json.loads((ARCH/f'gw{gw}.json').read_text())
        snap={int(p['id']):p for p in data['players']}
        rows=hist[hist.gw.eq(gw)]
        if rows.empty:raise ValueError('No GW'+str(gw)+' historic outcomes')
        matched=rows[rows.fpl_element.isin(snap)].copy()
        matched['archived_team']=[int(snap[int(x)]['team']) for x in matched.fpl_element]
        matched['archived_position']=[int(snap[int(x)]['position']) for x in matched.fpl_element]
        team_errors=matched[matched.team_id.ne(matched.archived_team)]
        pos_map={1:'GK',2:'DEF',3:'MID',4:'FWD'}
        position_errors=matched[[str(pos_map[int(p)])!=str(v) for p,v in zip(matched.archived_position,matched.fpl_position)]]
        missing=rows[~rows.fpl_element.isin(snap)]
        item={'gw':gw,'historic_outcome_rows':len(rows),'archived_roster_players':len(snap),
              'matched_outcomes':len(matched),'missing_archived_players':len(missing),
              'missing_player_ids':missing.fpl_element.astype(int).tolist()[:20],
              'team_discrepancies':len(team_errors),
              'team_discrepancy_player_ids':team_errors.fpl_element.astype(int).tolist()[:20],
              'position_discrepancies':len(position_errors),
              'position_discrepancy_player_ids':position_errors.fpl_element.astype(int).tolist()[:20],
              'archive_asof':data['evidence']['snapshot_at_utc']}
        groups.append(item)
    obj={'classification':'REAL_PREDEADLINE_FPL_ROSTER_VS_POSTMATCH_COVERAGE_AUDIT',
         'all_gws':5,'total_historical_rows':len(hist),
         'matching_rows':sum(g['matched_outcomes'] for g in groups),
         'unmatched_rows':sum(g['missing_archived_players'] for g in groups),
         'team_mismatch_rows':sum(g['team_discrepancies'] for g in groups),
         'position_mismatch_rows':sum(g['position_discrepancies'] for g in groups),
         'all_historical_rosters_predeadline_certified':False,
         'model_retrained':False,'gw_reports':groups}
    (ARCH/'roster_coverage_audit.json').write_text(json.dumps(obj,indent=2))
    print('ARCHIVED REAL FPL ROSTER COVERAGE',json.dumps(obj))
    return obj
if __name__=='__main__':audit()
