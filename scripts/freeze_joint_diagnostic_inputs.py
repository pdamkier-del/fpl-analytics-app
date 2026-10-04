"""Freeze a paired diagnostic cohort from original archived component forecasts.

No fitting. Missing non-GK components exclude the entire fixture from both arms.
Original raw member hashes and archive identities are retained; targets are separate.
"""
import argparse
import gzip
import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACKS = [
    ('FPL_v1_1_PHASE_3C_PATCH(1).zip', 'libfile_061ad5768f948191aa62d1046ee97ad2',
     [('outputs/v1_1/phase3c_player_attack/goal_holdout_predictions.csv', 'goal'),
      ('outputs/v1_1/phase3c_player_attack/assist_holdout_predictions.csv', 'assist')]),
    ('FPL_v1_1_PHASE_3D_PATCH(1).zip', 'libfile_958917b4bc788191986e80c848eded7a',
     [('outputs/v1_1/phase3d_defcon/defcon_validation_predictions.csv', 'dc')]),
    ('FPL_v1_1_PHASE_3E_PATCH(1).zip', 'libfile_97e5194933588191b3932d7738512101',
     [('outputs/v1_1/phase3e_negative_events/negative_events_holdout_predictions.csv', 'negative')]),
    ('FPL_v1_1_PHASE_3G_PATCH(1).zip', 'libfile_45ecef7701a08191b049035a1cdf1b21',
     [('outputs/v1_1/phase3g_keeper/keeper_holdout_predictions_2025_26.csv', 'keeper')]),
    ('FPL_v1_1_PHASE_5E_PATCH.zip', 'libfile_c3536588fdf08191ba1dce9db4a79c9e',
     [('phase5e_patch/outputs/v1_1/phase5e_team_goal_candidates/latent_selected_predictions.csv', 'latent')]),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive-directory', type=Path, required=True)
    ap.add_argument('--db', type=Path, default=ROOT/'work/core.sqlite3')
    ap.add_argument('--out', type=Path, default=ROOT/'analysis/results/joint-paired-inputs-v1')
    a = ap.parse_args()
    if a.out.exists():
        raise FileExistsError('Use a new output directory; frozen inputs are immutable')
    sources = []; frames = {}
    for filename, lid, members in PACKS:
        path = a.archive_directory/filename
        with zipfile.ZipFile(path) as archive:
            for member, name in members:
                raw = archive.read(member)
                sources.append(dict(archive=filename, library_file_id=lid,
                                    archive_sha256=sha(path.read_bytes()), member=member,
                                    member_sha256=sha(raw), bytes=len(raw)))
                frames[name] = pd.read_csv(io.BytesIO(raw))
    keys = ['fixture_uuid', 'player_uuid']
    baseline_path = ROOT/'analysis/results/v2-reproduced/pstart_v2_fixture_holdout_2025_26.csv'
    v4_path = ROOT/'analysis/results/workload-recovered-minutes-v4/reused_holdout_diagnostic_predictions.csv.gz'
    b = pd.read_csv(baseline_path); b = b[b.gw >= 22].copy()
    v4 = pd.read_csv(v4_path)
    f = b[keys+['gw', 'team_id', 'pos', 'p_start_v2', 'expected_minutes_v2',
                'start_minutes_mean', 'cameo_minutes_mean', 'p_cameo_given_bench']].rename(
        columns={'p_start_v2':'control_p_start', 'expected_minutes_v2':'control_xmins'})
    vcols = keys+['cutoff', 'workload_start_p_start', 'workload_start_xmins',
                  'start_minutes_mean', 'cameo_minutes_mean', 'p_cameo_given_bench']
    f = f.merge(v4[vcols].rename(columns={c:'v4_'+c for c in vcols if c not in keys+['cutoff']}),
                on=keys, how='outer', validate='one_to_one', indicator=True)
    if (f._merge != 'both').any():
        raise ValueError('Baseline/v4 roster differs')
    f = f.drop(columns='_merge')
    for name, cols, rename in [
        ('goal', ['mu'], {'mu':'goal_mu'}), ('assist', ['mu'], {'mu':'assist_mu'}),
        ('dc', ['mu_dc'], {}), ('negative', ['p_yellow', 'p_red'], {})]:
        f = f.merge(frames[name][keys+cols].rename(columns=rename), on=keys,
                    how='left', validate='one_to_one')
    # GK defensive-contribution points are structurally zero, not missing data.
    f.loc[f.pos.isin(['GK', 'GKP']), 'mu_dc'] = 0.0
    con = sqlite3.connect(a.db.resolve().as_uri()+'?mode=ro', uri=True)
    fixtures = pd.read_sql_query("select fixture_uuid, home_team_id, away_team_id from fixtures where season='2025-26'", con)
    targets = pd.read_sql_query("select fixture_uuid, player_uuid, total_points, bonus from player_fixture_observations where season='2025-26'", con)
    # Raw Core contains exact logical duplicates; conflicting targets are rejected.
    if targets.groupby(keys)[['total_points','bonus']].nunique(dropna=False).max().max() > 1:
        raise ValueError('Conflicting target observations')
    targets = targets.drop_duplicates(keys)
    assist = con.execute("select sum(fpl_assists),sum(goals) from player_fixture_observations where season in ('2023-24','2024-25')").fetchone()
    f = f.merge(fixtures, on='fixture_uuid', validate='many_to_one')
    keeper = frames['keeper']
    f = f.merge(keeper[['fixture_uuid','team_id','lambda_saves']], on=['fixture_uuid','team_id'],
                how='left', validate='many_to_one')
    latent = frames['latent']; latent = latent[latent.season == '2025-26']
    for side in ['home','away']:
        f = f.merge(latent[['fixture_uuid','team_id','lam']].rename(columns={
            'team_id':side+'_team_id','lam':'lambda_'+side+'_goals'}),
            on=['fixture_uuid',side+'_team_id'], how='left', validate='many_to_one')
    required = ['goal_mu','assist_mu','mu_dc','p_yellow','p_red','lambda_saves',
                'lambda_home_goals','lambda_away_goals']
    missing = f[f[required].isna().any(axis=1)].copy()
    missing['missing_components'] = missing.apply(lambda r: '|'.join(c for c in required if pd.isna(r[c])), axis=1)
    blocked = set(missing.fixture_uuid)
    complete = f[~f.fixture_uuid.isin(blocked)].copy()
    # Preserve the inherited original control's minimum-exposure roster filter.
    low = complete[complete.control_xmins < .05].copy()
    complete = complete[complete.control_xmins >= .05].copy()
    complete['assist_probability_per_goal'] = float(assist[0]/assist[1])
    complete['dc_alpha'] = complete.pos.map({'DEF':1.6136326854524488,'MID':.9017026562284318,
                                          'FWD':.7194052759354805,'GK':0.0,'GKP':0.0})
    complete = complete.sort_values(['gw','fixture_uuid','team_id','player_uuid']).reset_index(drop=True)
    target = complete[keys].merge(targets, on=keys, how='left', validate='one_to_one')
    if target[['total_points','bonus']].isna().any().any():
        raise ValueError('Missing evaluation targets')
    a.out.mkdir(parents=True)
    outputs = []
    for name, frame in [('inputs',complete), ('targets',target), ('missing_components',missing[keys+['gw','team_id','pos','missing_components']]), ('low_exposure_exclusions',low[keys+['gw','control_xmins']])]:
        raw = frame.to_csv(index=False,lineterminator='\n').encode()
        compressed = gzip.compress(raw, mtime=0)
        parts=[]
        for i, start in enumerate(range(0,len(compressed),32768)):
            part = f'{name}.csv.gz.part-{i:04d}'; data=compressed[start:start+32768]
            (a.out/part).write_bytes(data);parts.append(dict(path=part,sha256=sha(data),bytes=len(data)))
        outputs.append(dict(name=name,rows=len(frame),uncompressed_sha256=sha(raw),compressed_sha256=sha(compressed),parts=parts))
    manifest = dict(sources=sources, tracked_inputs=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p.read_bytes())) for p in [baseline_path,v4_path]],
                    code_sha256=sha(Path(__file__).read_bytes()), outputs=outputs,
                    season='2025-26', classification='reused_diagnostic_not_new_holdout',
                    control='unchanged frozen PSTART_V2 comparator; original Phase4B/4C adapter and simulator',
                    candidate='selected v4 workload_start, old conditional duration/cameo',
                    total_roster_rows=len(f),total_fixtures=int(f.fixture_uuid.nunique()),
                    missing_component_rows=len(missing),blocked_fixtures=len(blocked),
                    complete_fixtures=int(complete.fixture_uuid.nunique()), paired_rows=len(complete),
                    low_exposure_exclusions=len(low),
                    policy='Whole missing-component fixtures excluded in both arms; no default zero; inherited control exposure filter fixed in both arms',
                    full_roster_diagnostic_ready=not blocked, full_season_replay_ready=False)
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['sources','tracked_inputs','outputs']},indent=2))


if __name__ == '__main__':
    main()
