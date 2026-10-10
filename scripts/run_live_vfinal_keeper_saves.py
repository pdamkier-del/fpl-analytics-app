#!/usr/bin/env python3
"""Run frozen keeper-save model on archived FotMob source-defined team SOT.

Requires all 50 completed league match SOT pairs. No approximated shots,
fallback to FPL player saves, or model refits. Target output is source
feature evidence, not a completed PM/vFinal player xP prediction.
"""
from __future__ import annotations
from pathlib import Path
import gzip,json,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline

WORK=ROOT/'work/live-final-model'
BASE=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
OUT=BASE/'keeper_lambda_saves_by_fixture_team.csv.gz'
AUDIT=WORK/'live_vfinal_keeper_saves.json'

def read_games():
    return [json.loads(z) for z in gzip.decompress((WORK/'match_actuals.jsonl.gz').read_bytes()).splitlines()]

def sot_pair(o):
    groups=o.get('content',{}).get('stats',{}).get('Periods',{}).get('All',{}).get('stats',[])
    found=[]
    for group in groups:
        for item in group.get('stats',[]):
            if item.get('key')!='ShotsOnTarget':continue
            val=item.get('rawStats') or item.get('stats')
            if not isinstance(val,list) or len(val)!=2:raise ValueError('Unexpected source SOT shape')
            pair=tuple(int(x.get('value') if isinstance(x,dict) else x) for x in val)
            if min(pair)<0:raise ValueError('Negative source SOT')
            found.append(pair)
    if not found or len(set(found))!=1:raise ValueError('Missing/ambiguous official provider shots-on-target')
    return found[0]

def build():
    manifest=json.loads((WORK/'source_manifest.json').read_text())
    origin=int(manifest['target_gw'])
    cutoff=pd.Timestamp(manifest['observed_at'])
    bootstrap=json.loads((WORK/'bootstrap.json').read_text())
    code_to_id={int(t['code']):int(t['id']) for t in bootstrap['teams']}
    by_file={}
    for f in sorted((ROOT/'data_v1_1/raw/live-captures').glob('*/fotmob/details/*.json')):
        mid=f.stem
        if mid in by_file:
            # Append-only capture folders can contain the same immutable
            # payload. A conflicting revision still needs explicit review.
            if f.read_bytes()!=by_file[mid].read_bytes():raise ValueError('Conflicting provider match evidence '+mid)
            continue
        by_file[mid]=f
    sides=[];captured=[]
    for g in read_games():
        if g.get('tournament')!='prem' or g.get('gameweek') is None or int(g['gameweek'])>=origin:
            continue
        available=pd.Timestamp(g['available_at'])
        if available>=cutoff:continue
        match_id=str(g['provider_match_id'])
        if match_id not in by_file:raise ValueError('Missing archived match facts: '+match_id)
        provider=json.loads(by_file[match_id].read_text())
        if str(provider['general']['matchId'])!=match_id:
            raise ValueError('Provider source match id mismatch')
        home,away=sot_pair(provider)
        ht=code_to_id[int(g['home_team'])];at=code_to_id[int(g['away_team'])]
        if ht==at:raise ValueError('Invalid fixture team identities')
        for team,opp,for_shots,against,is_home in [
            (ht,at,home,away,True),(at,ht,away,home,False)]:
            sides.append(dict(season='2026-27',
                fixture_uuid='historic-2026-27-provider-'+match_id,
                team_id=team,opponent_team_id=opp,was_home=is_home,
                kickoff_at=g['kickoff_time'],available_at=g['available_at'],
                shots_on_target=for_shots,shots_on_target_conceded=against))
        captured.append(match_id)
    h=pd.DataFrame(sides)
    if len(set(captured))!=50 or len(h)!=100 or h.groupby('team_id').size().min()<5:
        raise ValueError(f'Missing complete 5-match per-team observed SOT history: {len(captured)} games')
    if h[['fixture_uuid','team_id']].duplicated().any():
        raise ValueError('Duplicate provider SOT team side')
    t=pd.read_csv(BASE/'future_team_goal_lambdas.csv.gz')
    side_rows=[]
    for r in t.itertuples(index=False):
        fid='live-2026-27-fpl-'+str(int(r.fpl_fixture_id))
        side_rows.extend([
            dict(fixture_uuid=fid,team_id=int(r.home_team_id),
                 opponent_team_id=int(r.away_team_id),was_home=True),
            dict(fixture_uuid=fid,team_id=int(r.away_team_id),
                 opponent_team_id=int(r.home_team_id),was_home=False)])
    target=pd.DataFrame(side_rows)
    model=json.loads((ROOT/'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json').read_text())
    pred=keeper_saves_at_deadline(h,target,cutoff,model,season='2026-27')
    if len(pred)!=len(target) or pred.lambda_saves.isna().any():
        raise ValueError('Missing expected keeper saves for future target')
    if not np.isfinite(pred.lambda_saves.to_numpy(float)).all():
        raise ValueError('Invalid predicted saves')
    pred.to_csv(OUT,index=False,compression='gzip')
    report={'classification':'FROZEN_KEEPER_SAVE_COMPONENT_ON_ARCHIVED_2026_SOT_NOT_FULL_PM',
       'origin_gw':origin,'archived_pl_matches':len(captured),
       'training_team_fixture_sides':len(h),'team_ids':int(h.team_id.nunique()),
       'future_fixture_sides':len(pred),'future_fixtures':int(pred.fixture_uuid.nunique()),
       'frozen_model_source':'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json',
       'SOT_source':'archived FotMob 2026 match team statistics',
       'source_definition':'ShotsOnTarget for attacking team, conceded same fixture for defending team',
       'frozen_math_unchanged':True,'live_pm_certified':False}
    AUDIT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('FROZEN VFINAL CURRENT KEEPER SAVES:',json.dumps(report))
    return pred
if __name__=='__main__':build()

