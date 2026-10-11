"""Publish display-only fixture expectations and verified public TC scenarios.
No model input or mathematical operation is changed.
"""
import hashlib,json,shutil,re
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def version_frontend_assets(app):
    # Each published HTML references the exact deployed asset bytes. This avoids
    # a normal reload retaining an older planner UI in the Pages CDN/browser cache.
    for page in ('overview.html','manager-state.html'):
        path=app/page
        html=path.read_text()
        def version(match):
            asset=app/match.group(2)
            if not asset.is_file():return match.group(0)
            digest=hashlib.sha256(asset.read_bytes()).hexdigest()[:16]
            return match.group(1)+match.group(2)+'?v='+digest+match.group(3)
        html=re.sub(r'((?:src|href)=")([^"?]+\.(?:js|css))(?:\?[^" ]*)?(")',version,html)
        path.write_text(html)

def main():
    forecast=json.loads((ROOT/'app/vfinal-diagnostic.json').read_text())
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    source=base/'vfinal_live_full_simulator_input.csv.gz'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=forecast['checksums'][source.name]:raise ValueError('Fixture source checksum mismatch')
    df=pd.read_csv(source, usecols=['fpl_fixture_id','target_gw','home_team_id','away_team_id','lambda_home_goals','lambda_away_goals'])
    keys=['fpl_fixture_id','target_gw','home_team_id','away_team_id']
    if df.groupby(keys)[['lambda_home_goals','lambda_away_goals']].nunique().gt(1).any().any():raise ValueError('Inconsistent match goal expectations')
    rows=df.drop_duplicates(keys).rename(columns={'fpl_fixture_id':'id','target_gw':'gw','home_team_id':'home','away_team_id':'away','lambda_home_goals':'home_xg','lambda_away_goals':'away_xg'})
    (ROOT/'app/fixture-expectations.json').write_text(json.dumps(dict(cutoff=forecast['data_asof'],checksums=forecast['checksums'],fixtures=rows.to_dict('records')),allow_nan=False)+'\n')
    tc=ROOT/'work/live-manager-validation/tc_samples.csv.gz'
    if forecast.get('tc_scenarios') and tc.exists():
        if hashlib.sha256(tc.read_bytes()).hexdigest()!=forecast['tc_scenarios']['samples_sha256']:raise ValueError('TC checksum mismatch')
        shutil.copyfile(tc,ROOT/'app/tc-samples.csv.gz')
    version_frontend_assets(ROOT/'app')
if __name__=='__main__':main()
