"""Freeze a complete-fixture control/v4 cohort with deadline-batched common inputs.

Original minutes, adapter, simulator and transfer/chip strategy are retained.
Unverified roster fixtures are excluded in BOTH arms, never filled with zero.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

import numpy as np
import pandas as pd

from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline
from fpl_v1_1_model.paired_joint import read_frozen_table

ROOT=Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pack(folder,name,frame):
    raw=frame.to_csv(index=False,lineterminator='\n').encode();packed=gzip.compress(raw,mtime=0);parts=[]
    for i,start in enumerate(range(0,len(packed),32768)):
        data=packed[start:start+32768];path=f'{name}.csv.gz.part-{i:04d}'
        (folder/path).write_bytes(data);parts.append(dict(path=path,bytes=len(data),sha256=sha(data)))
    return dict(name=name,rows=len(frame),uncompressed_sha256=sha(raw),compressed_sha256=sha(packed),parts=parts)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',type=Path,default=ROOT/'work/core.sqlite3')
    ap.add_argument('--archives',type=Path,default=ROOT.parent/'recovery-inputs')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/results/deadline-joint-inputs-v1')
    a=ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Use a new immutable joint input directory')
    parent=ROOT/'analysis/results/deadline-player-components-v1'
    c=read_frozen_table(parent,'components');blocked=read_frozen_table(parent,'blocked_roster')
    blocked_fixtures=set(blocked.fixture_uuid)
    bpath=ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    vpath=ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    keys=['fixture_uuid','player_uuid']
    b=pd.read_csv(bpath,usecols=keys+['gw','team_id','pos','p_start_v2','expected_minutes_v2',
        'start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench'])
    b=b[b.gw>=22].rename(columns={'p_start_v2':'control_p_start','expected_minutes_v2':'control_xmins'})
    vcols=keys+['cutoff','workload_start_p_start','workload_start_xmins','start_minutes_mean','cameo_minutes_mean','p_cameo_given_bench']
    v=pd.read_csv(vpath,usecols=vcols).rename(columns={x:'v4_'+x for x in vcols if x not in keys+['cutoff']})
    f=b.merge(v,on=keys,validate='one_to_one')
    excluded=f[f.fixture_uuid.isin(blocked_fixtures)].copy()
    f=f[~f.fixture_uuid.isin(blocked_fixtures)].copy()
    expected=len(f)
    f=f.merge(c[keys+['goal_rate90','assist_rate90','mu_dc','dc_alpha','p_yellow','p_red','cold_start']],
        on=keys,how='left',validate='one_to_one')
    if len(f)!=expected or f.goal_rate90.isna().any():
        raise ValueError('Incomplete verified player component roster')
    low=f[f.control_xmins<.05].copy();f=f[f.control_xmins>=.05].copy()
    con=sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro',uri=True)
    fixtures=pd.read_sql_query("SELECT fixture_uuid,home_team_id,away_team_id FROM fixtures WHERE season='2025-26'",con)
    f=f.merge(fixtures,on='fixture_uuid',validate='many_to_one')
    # Selected latent model already uses only prior GWs. Preserve exact means;
    # verify the original source history's time boundary before accepting them.
    archive=a.archives/'FPL_v1_1_PHASE_5E_PATCH.zip'
    member='phase5e_patch/outputs/v1_1/phase5e_team_goal_candidates/latent_selected_predictions.csv'
    with zipfile.ZipFile(archive) as z:
        raw=z.read(member)
    latent=pd.read_csv(io.BytesIO(raw),usecols=['season','gw','fixture_uuid','team_id','lam'])
    latent=latent[latent.season=='2025-26']
    for side in ['home','away']:
        f=f.merge(latent[['fixture_uuid','team_id','lam']].rename(columns={
            'team_id':side+'_team_id','lam':'lambda_'+side+'_goals'}),
            on=['fixture_uuid',side+'_team_id'],how='left',validate='many_to_one')
    if f[['lambda_home_goals','lambda_away_goals']].isna().any().any():
        raise ValueError('Missing selected original team-goal mean')
    keeper_path=ROOT/'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json'
    fit=json.loads(keeper_path.read_text());keepers=[];time_audit=[];assist_ratios={}
    for (gw,cutoff),group in f.groupby(['gw','cutoff'],sort=True):
        prior=pd.read_sql_query("""SELECT gw,kickoff_at FROM team_fixture_observations
            WHERE season='2025-26' AND source_name='vaastav_historical_core' AND gw<?""",con,params=[int(gw)])
        violations=int((pd.to_datetime(prior.kickoff_at,utc=True)+pd.Timedelta(hours=3)>pd.Timestamp(cutoff)).sum())
        if violations:
            raise ValueError('Original prior-GW latent input has unavailable source outcomes')
        sot=pd.read_sql_query("""SELECT season,fixture_uuid,team_id,kickoff_at,shots_on_target,shots_on_target_conceded
            FROM team_fixture_observations WHERE season='2025-26' AND source_name='football_data_co_uk'
            AND julianday(kickoff_at)+3.0/24.0<=julianday(?)""",con,params=[cutoff])
        sot['available_at']=pd.to_datetime(sot.kickoff_at,utc=True)+pd.Timedelta(hours=3)
        sides=group[['fixture_uuid','team_id','home_team_id','away_team_id']].drop_duplicates()
        sides['opponent_team_id']=np.where(sides.team_id==sides.home_team_id,sides.away_team_id,sides.home_team_id)
        sides['was_home']=sides.team_id==sides.home_team_id
        keepers.append(keeper_saves_at_deadline(sot,sides,cutoff,fit))
        # Current-season ratio, fixed for all target fixtures in this deadline.
        assists=pd.read_sql_query("""SELECT DISTINCT fixture_uuid,player_uuid,goals,fpl_assists
            FROM player_fixture_observations WHERE season='2025-26'
            AND julianday(kickoff_at)+3.0/24.0<=julianday(?)""",con,params=[cutoff])
        if assists[['fixture_uuid','player_uuid']].duplicated().any():
            raise ValueError('Conflicting historical assist/goal totals')
        goals=float(assists.goals.sum())
        if goals<=0:
            raise ValueError('No current-season assist ratio exposure')
        assist_ratios[int(gw)]=min(1.0,max(.5,float(assists.fpl_assists.sum())/goals))
        time_audit.append(dict(gw=int(gw),cutoff=cutoff,prior_gw_team_rows=len(prior),
            unavailable_latent_source_rows=violations,keeper_source_rows=len(sot),
            latest_keeper_guard_available_at=sot.available_at.max().isoformat()))
    saves=pd.concat(keepers,ignore_index=True)
    f=f.merge(saves[['fixture_uuid','team_id','lambda_saves']],on=['fixture_uuid','team_id'],how='left',validate='many_to_one')
    if f.lambda_saves.isna().any():
        raise ValueError('Missing defending-team save opportunity')
    f['assist_probability_per_goal']=f.gw.map(assist_ratios)
    team_lambda=np.where(f.team_id==f.home_team_id,f.lambda_home_goals,f.lambda_away_goals)
    for kind in ['goal','assist']:
        prop=f.control_xmins/90.0*f[kind+'_rate90']
        total=prop.groupby([f.fixture_uuid,f.team_id]).transform('sum')
        if (total<=0).any():
            raise ValueError('No team '+kind+' propensity exposure')
        f[kind+'_mu']=team_lambda*prop/total*(f.assist_probability_per_goal if kind=='assist' else 1.0)
    f=f.sort_values(['gw','fixture_uuid','team_id','player_uuid']).reset_index(drop=True)
    a.out.mkdir(parents=True)
    outputs=[pack(a.out,'inputs',f)]
    # Evaluation targets are separate and loaded only after common inputs saved.
    targets=pd.read_sql_query("SELECT fixture_uuid,player_uuid,total_points,bonus FROM player_fixture_observations WHERE season='2025-26'",con)
    con.close()
    if targets.groupby(keys)[['total_points','bonus']].nunique(dropna=False).max().max()>1:
        raise ValueError('Conflicting evaluation targets')
    targets=targets.drop_duplicates(keys)
    target=f[keys].merge(targets,on=keys,how='left',validate='one_to_one')
    if target[['total_points','bonus']].isna().any().any():
        raise ValueError('Missing sequestered evaluation targets')
    outputs+=[pack(a.out,'targets',target),pack(a.out,'excluded_fixtures',excluded),
        pack(a.out,'low_exposure_exclusions',low),pack(a.out,'team_keeper_timing',pd.DataFrame(time_audit))]
    source_paths=[parent/'manifest.json',bpath,vpath,keeper_path,
        ROOT/'analysis/results/joint-team-keeper-recovery-v1/manifest.json',
        ROOT/'src/fpl_v1_1_model/deadline_keeper.py',Path(__file__)]
    manifest=dict(classification='reused_diagnostic_not_new_holdout',season='2025-26',
        paired_fixtures=int(f.fixture_uuid.nunique()),paired_rows=len(f),verified_first_entry_rows=int(f.cold_start.sum()),
        excluded_whole_fixtures=len(blocked_fixtures),unverified_roster_rows=len(blocked),
        low_exposure_exclusions=len(low),complete_fixture_cohort_available=True,
        full_roster_period_ready=False,full_season_replay_ready=False,parameters_refit=False,
        policy='Whole unverified-roster fixtures excluded in both arms. Original V2/v4 minutes unchanged. Common deadline player/keeper states; selected original latent team means preserved.',
        keeper_orientation='lambda_saves keyed by defending team; original source CSV team_id was attacking, opp defending',
        scoring='Inherited original simulator/scoring in both arms; 2025/26 rules audit still applies before full season replay',
        availability='Explicit kickoff+3h history guard; not authoritative publication timestamps',
        outputs=outputs,sources=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p.read_bytes())) for p in source_paths],
        latent_source=dict(archive=archive.name,archive_sha256=sha(archive.read_bytes()),member=member,member_sha256=sha(raw),
            library_file_id='libfile_c3536588fdf08191ba1dce9db4a79c9e'),
        unchanged='Original adapter/simulator, old forecasts/paired results, Core and transfer/chip strategy')
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:manifest[k] for k in ['paired_fixtures','paired_rows','verified_first_entry_rows','excluded_whole_fixtures','unverified_roster_rows','low_exposure_exclusions']},indent=2))


if __name__=='__main__':
    main()
